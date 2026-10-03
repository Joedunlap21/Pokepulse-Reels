"""
PokePulse "Drop Alert" Reel - octarips-style format for the DROPS topic.

Look (copied from the drop-alert pages):
  * store / set logo big at the top, pops in when the store changes
  * karaoke captions mid-screen: 2-3 words, white Montserrat Black with a thick black
    outline, the word being spoken turns YELLOW
  * product pictures in the bottom half (cut out when the photo has a plain background,
    otherwise a clean rounded card), green slanted price tags
  * products whip in from the side with motion blur, slow moving background + drifting petals
  * voiceover (free edge-tts) on top of a quiet music bed, ends on the newsletter CTA slide

Accuracy: the script is written ONLY from the article. Every price, number, month and
store named in a line is checked against the article text; a line that fails is thrown
away and the plain facts from the article are used instead.

main.py calls compile_drop_reel(story) for the drops topic. If anything in here fails,
main.py falls back to the normal reel so a post is never skipped.
"""
import os
import re
import json
import math
import glob
import random
import subprocess
import tempfile

import numpy as np
import cv2
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30

# ---- look & feel (matched to the reference reels) ----
CAPTION_Y = 0.405          # caption block centre (fraction of height)
CAPTION_SIZE = 94
CAPTION_MAX_W = 900
WORDS_PER_CHUNK = 3
YELLOW = (255, 232, 20)
WHITE = (255, 255, 255)
PRICE_GREEN = (52, 230, 64)
LOGO_Y = 0.185
LOGO_MAX_W = 0.72 * W
LOGO_MAX_H = 0.17 * H
PRODUCT_CY = 0.675
PRODUCT_BOX = (0.94 * W, 0.42 * H)
WHIP = 0.24                # seconds for whip-in transitions
MUSIC_VOLUME = 0.14

FONT_FILE = "Montserrat-Black.ttf"
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf"

# store badge colours (bg, text). Put a real logo PNG in assets/logos/<name>.png to use that instead,
# e.g. assets/logos/target.png, assets/logos/best-buy.png, assets/logos/pokemon-center.png
STORE_STYLE = {
    "Target": ((204, 0, 0), WHITE), "Walmart": ((0, 113, 220), (255, 194, 32)),
    "Best Buy": ((0, 70, 190), (255, 224, 0)), "Costco": ((227, 24, 55), WHITE),
    "Pokemon Center": ((226, 35, 26), WHITE), "GameStop": ((20, 20, 20), (235, 30, 40)),
    "Amazon": ((20, 20, 20), (255, 153, 0)), "Sam's Club": ((0, 103, 160), WHITE),
}


# ================================================================ fonts
_font_cache = {}


def ensure_font():
    if not os.path.exists(FONT_FILE):
        r = requests.get(FONT_URL, timeout=30)
        r.raise_for_status()
        with open(FONT_FILE, "wb") as f:
            f.write(r.content)


def font(size):
    if size not in _font_cache:
        f = ImageFont.truetype(FONT_FILE, size)
        try:
            f.set_variation_by_name("Black")
        except Exception:
            pass
        _font_cache[size] = f
    return _font_cache[size]


# ================================================================ drawing helpers
def ease_out_back(x):
    c1, c3 = 1.70158, 2.70158
    x = min(max(x, 0), 1)
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x):
    x = min(max(x, 0), 1)
    return 1 - (1 - x) ** 3


def fit(im, maxw, maxh):
    s = min(maxw / im.width, maxh / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def with_shadow(im, blur=18, off=(0, 14), alpha=150):
    pad = blur * 3
    canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(im.split()[3].point(lambda v: v * alpha // 255))
    canvas.alpha_composite(sh, (pad + off[0], pad + off[1]))
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(im, (pad, pad))
    return canvas


def stroked_text(txt, size, fill, stroke=9, shadow=True, italic=0.0):
    f = font(size)
    l, t, r, b = f.getbbox(txt, stroke_width=stroke)
    pad = 24
    im = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - l + 3, pad - t + 7), txt, font=f, fill=(0, 0, 0, 200),
                                stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    ImageDraw.Draw(im).text((pad - l, pad - t), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
    if italic:
        im = im.transform((im.width + int(im.height * italic), im.height), Image.AFFINE,
                          (1, italic, -im.height * italic, 0, 1, 0), Image.BICUBIC)
    return im


def price_tag(price, size=58):
    return stroked_text(price, size, PRICE_GREEN, stroke=7, italic=0.12).rotate(9, resample=Image.BICUBIC, expand=True)


def store_badge(name, out_path):
    """Bold store-name badge (used when there's no logo PNG in assets/logos)."""
    bg, fg = STORE_STYLE.get(name, ((229, 9, 20), WHITE))
    label = name.upper()
    size = 130 if len(label) <= 8 else 104
    txt = stroked_text(label, size, fg, stroke=0, shadow=False)
    pw, ph = txt.width + 70, txt.height + 30
    im = Image.new("RGBA", (pw + 24, ph + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, pw + 23, ph + 23], radius=40, fill=WHITE)
    d.rounded_rectangle([12, 12, pw + 11, ph + 11], radius=32, fill=bg)
    im.alpha_composite(txt, (12 + (pw - txt.width) // 2, 12 + (ph - txt.height) // 2))
    im.rotate(3, resample=Image.BICUBIC, expand=True).save(out_path)
    return out_path


# ================================================================ captions
def chunk_words(words):
    """words: [(text,start,end)] -> chunks of ~3 words, breaking on punctuation."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= WORDS_PER_CHUNK or re.search(r"[.,!?;:]$", w[0]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    # never leave one word hanging on its own: 3+1 -> 2+2
    for i in range(1, len(chunks)):
        if len(chunks[i]) == 1 and len(chunks[i - 1]) == 3 and not re.search(r"[.,!?;:]$", chunks[i - 1][-1][0]):
            chunks[i] = [chunks[i - 1].pop()] + chunks[i]
    out = []
    for i, c in enumerate(chunks):
        end = chunks[i + 1][0][1] if i + 1 < len(chunks) else c[-1][2] + 0.25
        out.append({"words": c, "start": c[0][1], "end": end})
    return out


_cap_cache = {}


def render_caption(chunk, active_idx):
    key = (tuple(w[0] for w in chunk), active_idx)
    if key in _cap_cache:
        return _cap_cache[key]
    toks = [re.sub(r"[^\w$%'.&+-]", "", w[0]).strip(".").upper() or w[0].upper() for w in chunk]
    space = -36  # glyph images carry padding
    for size in (CAPTION_SIZE, 80, 68):      # shrink long words so it stays on 2 lines
        imgs = [stroked_text(t, size, YELLOW if i == active_idx else WHITE) for i, t in enumerate(toks)]
        lines, line, lw = [], [], 0
        for im in imgs:
            add = im.width + (space if line else 0)
            if line and lw + add > CAPTION_MAX_W + 48:
                lines.append(line)
                line, lw, add = [], 0, im.width
            line.append(im)
            lw += add
        if line:
            lines.append(line)
        if len(lines) <= 2:
            break
    lh = max(i.height for i in imgs) - 40
    tw = max(sum(i.width for i in l) + space * (len(l) - 1) for l in lines)
    canvas = Image.new("RGBA", (tw, lh * len(lines) + 40), (0, 0, 0, 0))
    y = 0
    for l in lines:
        x = (tw - (sum(i.width for i in l) + space * (len(l) - 1))) // 2
        for im in l:
            canvas.alpha_composite(im, (x, y))
            x += im.width + space
        y += lh
    _cap_cache[key] = canvas
    return canvas


# ================================================================ products
def product_layer(products):
    """1 = big hero, 2 = staggered overlap, 3-4 = 2x2, 5-9 = 3x3 wall. Price tags always on top."""
    bw, bh = PRODUCT_BOX
    n = len(products)
    layer = Image.new("RGBA", (W, int(bh) + 160), (0, 0, 0, 0))
    if n == 0:
        return layer
    if n == 1:
        cells = [(0.5, 0.5, 0.80, 1.0)]
    elif n == 2:
        cells = [(0.32, 0.36, 0.58, 0.74), (0.66, 0.62, 0.58, 0.74)]
    elif n <= 4:
        cells = [(0.27, 0.26, 0.50, 0.52), (0.73, 0.26, 0.50, 0.52),
                 (0.27, 0.76, 0.50, 0.52), (0.73, 0.76, 0.50, 0.52)][:n]
    else:
        cells = [((c + 0.5) / 3, (r + 0.5) / 3, 0.31, 0.32) for r in range(3) for c in range(3)][:n]
    ox = (W - bw) / 2
    tags = []
    for k, (p, (cx, cy, fw, fh)) in enumerate(zip(products, cells)):
        im = fit(Image.open(p["img"]).convert("RGBA"), bw * fw, bh * fh)
        im = with_shadow(im, blur=16, off=(0, 12), alpha=170)
        x = int(ox + bw * cx - im.width / 2)
        y = int(80 + bh * cy - im.height / 2)
        layer.alpha_composite(im, (max(0, x), max(0, y)))
        if p.get("price"):
            tag = price_tag(p["price"], 64 if n <= 2 else 50)
            tx = int(x + im.width - tag.width * 0.85 - 40)
            ty = int(y + im.height - tag.height * 0.95 - 30)
            if n == 2 and k == 0:
                tx = int(x + 30)
            tags.append((tag, (max(0, min(W - tag.width, tx)), max(0, ty))))
    for tag, pos in tags:
        layer.alpha_composite(tag, pos)
    return layer


def hblur(arr, k):
    k = int(k)
    if k < 3:
        return arr
    return cv2.filter2D(arr, -1, np.ones((1, k), np.float32) / k, borderType=cv2.BORDER_CONSTANT)


# ================================================================ background
class Background:
    def __init__(self, src, blur=0):
        self.cap = None
        if src.lower().endswith((".mp4", ".mov", ".webm")):
            self.cap = cv2.VideoCapture(src)
        else:
            im = Image.open(src).convert("RGB")
            s = max(W * 1.22 / im.width, H * 1.22 / im.height)
            im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            if blur:
                im = im.filter(ImageFilter.GaussianBlur(blur))
            self.img = np.array(im)

    def frame(self, t):
        if self.cap is not None:
            ok, fr = self.cap.read()
            if not ok:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, fr = self.cap.read()
            fr = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
            h, w = fr.shape[:2]
            s = max(W / w, H / h)
            fr = cv2.resize(fr, (int(w * s) + 1, int(h * s) + 1))
            y0, x0 = (fr.shape[0] - H) // 2, (fr.shape[1] - W) // 2
            return fr[y0:y0 + H, x0:x0 + W]
        ih, iw = self.img.shape[:2]          # slow Ken Burns push + drift
        z = 1.0 + 0.10 * (0.5 - 0.5 * math.cos(min(t / 14, 1) * math.pi))
        cw, ch = int(iw / z / 1.22), int(ih / z / 1.22)
        cx = iw / 2 + math.sin(t * 0.25) * (iw - cw) * 0.25
        cy = ih / 2 + math.cos(t * 0.21) * (ih - ch) * 0.2
        x0 = int(np.clip(cx - cw / 2, 0, iw - cw))
        y0 = int(np.clip(cy - ch / 2, 0, ih - ch))
        return cv2.resize(self.img[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_LINEAR)


class Particles:
    """Drifting petals / sparkles over the background."""
    def __init__(self, n=26, seed=3):
        r = random.Random(seed)
        self.p = [dict(x=r.uniform(0, W), y=r.uniform(-H, H), s=r.uniform(8, 20), vx=r.uniform(-40, -10),
                       vy=r.uniform(60, 140), ph=r.uniform(0, 6.28),
                       c=r.choice([(255, 255, 255), (255, 214, 232), (186, 230, 140), (255, 240, 170)]))
                  for _ in range(n)]

    def draw(self, layer, t):
        d = ImageDraw.Draw(layer)
        for q in self.p:
            x = (q["x"] + q["vx"] * t + 30 * math.sin(t * 1.3 + q["ph"])) % (W + 60) - 30
            y = (q["y"] + q["vy"] * t) % (H + 60) - 30
            s = q["s"] * (0.7 + 0.3 * math.sin(t * 2 + q["ph"]))
            d.ellipse([x - s, y - s * 0.55, x + s, y + s * 0.55], fill=(*q["c"], 190))


# ================================================================ generic renderer
def render_video(shots, out_path, end_card=None, end_secs=2.2, vo_clips=(), music=None,
                 music_volume=MUSIC_VOLUME, bg_blur=9):
    """shots: [{start, end, chunks, logo, bg, products:[{img, price}]}] (times in seconds)."""
    ensure_font()
    total = shots[-1]["end"]
    total_all = total + (end_secs if end_card else 0)
    bgs, logos, prods = {}, {}, {}
    for s in shots:
        if s.get("bg") and s["bg"] not in bgs:
            bgs[s["bg"]] = Background(s["bg"], 0 if s["bg"].lower().endswith((".mp4", ".mov")) else bg_blur)
        if s.get("logo") and s["logo"] not in logos:
            logos[s["logo"]] = with_shadow(fit(Image.open(s["logo"]).convert("RGBA"), LOGO_MAX_W, LOGO_MAX_H),
                                           blur=12, off=(0, 8), alpha=140)
        s["pkey"] = json.dumps(s.get("products", []), sort_keys=True)
        if s["pkey"] not in prods:
            prods[s["pkey"]] = product_layer(s.get("products", []))
    prev = {"logo": None, "pkey": None, "bg": None}
    for i, s in enumerate(shots):   # only animate a layer when it actually changes
        for k, key in (("logo_in", "logo"), ("prod_in", "pkey"), ("bg_in", "bg")):
            s[k] = s["start"] if (i == 0 or s.get(key) != prev[key]) else shots[i - 1][k]
            prev[key] = s.get(key)

    particles = Particles()
    endimg = np.array(Image.open(end_card).convert("RGB").resize((W, H), Image.LANCZOS)) if end_card else None
    tmpdir = tempfile.mkdtemp(prefix="drop_")
    silent = os.path.join(tmpdir, "video.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "19", "-pix_fmt", "yuv420p", silent], stdin=subprocess.PIPE)
    nframes = int(total_all * FPS)
    for fi in range(nframes):
        t = fi / FPS
        if t >= total and endimg is not None:
            k = min(1, (t - total) / 0.2)
            z = 1.0 + 0.04 * (t - total) / max(end_secs, 0.1)
            fr = cv2.resize(endimg, None, fx=z, fy=z)
            y0, x0 = (fr.shape[0] - H) // 2, (fr.shape[1] - W) // 2
            fr = fr[y0:y0 + H, x0:x0 + W]
            if k < 1:
                fr = hblur(fr, 80 * (1 - k))
            ff.stdin.write(np.ascontiguousarray(fr, dtype=np.uint8).tobytes())
            continue
        s = next((x for x in shots if x["start"] <= t < x["end"]), shots[-1])
        bgarr = bgs[s["bg"]].frame(t) if s.get("bg") else np.full((H, W, 3), 18, np.uint8)
        if t - s["bg_in"] < WHIP and s["bg_in"] > 0:
            bgarr = hblur(bgarr, 90 * (1 - (t - s["bg_in"]) / WHIP))
        frame = Image.fromarray(bgarr).convert("RGBA")
        over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        particles.draw(over, t)
        frame.alpha_composite(over)
        # products: whip in from the right with motion blur, then a gentle bob
        pl = prods[s["pkey"]]
        dtp = t - s["prod_in"]
        py = int(H * PRODUCT_CY - pl.height / 2 + math.sin(t * 2.2) * 6)
        if dtp < WHIP:
            k = ease_out(dtp / WHIP)
            plx = int((1 - k) * W * 0.9)
            if plx < W:
                frame.alpha_composite(Image.fromarray(hblur(np.array(pl), 120 * (1 - k))), (plx, py))
        else:
            frame.alpha_composite(pl, (0, py))
        # logo: pop with overshoot
        if s.get("logo"):
            lg = logos[s["logo"]]
            k = ease_out_back((t - s["logo_in"]) / 0.32)
            sc = max(0.05, 0.55 + 0.45 * k) * (1 + 0.012 * math.sin(t * 3))
            lgs = lg.resize((max(1, int(lg.width * sc)), max(1, int(lg.height * sc))), Image.BICUBIC)
            frame.alpha_composite(lgs, (int(W / 2 - lgs.width / 2), int(H * LOGO_Y - lgs.height / 2)))
        # karaoke caption
        ch = next((c for c in s["chunks"] if c["start"] <= t < c["end"]), None)
        if ch:
            ai = 0
            for i, w in enumerate(ch["words"]):
                if t >= w[1]:
                    ai = i
            cap = render_caption(ch["words"], ai)
            sc = 0.82 + 0.18 * ease_out_back((t - ch["start"]) / 0.14)
            if sc != 1:
                cap = cap.resize((max(1, int(cap.width * sc)), max(1, int(cap.height * sc))), Image.BICUBIC)
            frame.alpha_composite(cap, (int(W / 2 - cap.width / 2), int(H * CAPTION_Y - cap.height / 2)))
        ff.stdin.write(np.array(frame.convert("RGB")).tobytes())
        if fi % 90 == 0:
            print(f"  drop reel frame {fi}/{nframes}")
    ff.stdin.close()
    ff.wait()

    # audio: voice on top, music bed underneath
    inputs, filt, labels, n_in = ["-i", silent], [], [], 1
    if music:
        inputs += ["-stream_loop", "-1", "-i", music]
        n_in += 1
        vol = music_volume if vo_clips else 0.9
        filt.append(f"[1:a]volume={vol},atrim=0:{total_all:.2f},afade=t=out:st={max(0, total_all - 1.2):.2f}:d=1.2[m]")
        labels.append("[m]")
    for j, (mp3, st) in enumerate(vo_clips):
        inputs += ["-i", mp3]
        ms = int(st * 1000)
        filt.append(f"[{n_in + j}:a]adelay={ms}|{ms},volume=1.5[v{j}]")
        labels.append(f"[v{j}]")
    if not labels:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        filt.append("[1:a]anull[a0]")
        labels.append("[a0]")
    filt.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
                f"atrim=0:{total_all:.2f},alimiter=limit=0.95[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{total_all:.3f}", "-movflags", "+faststart", out_path], check=True)
    return out_path


# ================================================================ accuracy checks
NUM_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
             "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15",
             "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50", "hundred": "100"}
MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
               "october", "november", "december"]


def _norm(s):
    return s.lower().replace("pokémon", "pokemon").replace(",", "")


def line_is_true(line, source):
    """Every number / price / month / store in the line must be in the article."""
    src, low = _norm(source), _norm(line)
    for num in re.findall(r"\d+(?:\.\d+)?", low):
        if num not in src:
            return False, f"number {num}"
    for w, d in NUM_WORDS.items():
        if re.search(rf"\b{w}\b", low) and not (re.search(rf"\b{w}\b", src) or re.search(rf"\b{d}\b", src)):
            return False, f"number word {w}"
    for m in MONTH_NAMES:
        if re.search(rf"\b{m}\b", low) and m not in src and m[:3] not in src:
            return False, f"month {m}"
    from main import RETAILERS
    for r in RETAILERS:
        if _norm(r) in low and _norm(r) not in src:
            return False, f"store {r}"
    return True, ""


# ================================================================ script
def ai_drop_script(story, source):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    from reel_v2 import gemini_models
    import time
    if story.get("topic") == "inside":
        return ai_inside_script(story, source, key)
    prompt = (
        "You write the voiceover for a 15-20 second Pokemon TCG DROP ALERT Reel, in the style of restock/drop-alert "
        "pages (fast, hyped, urgent, like telling collectors where to go right now). Short spoken lines, contractions, "
        "plain words, no emojis, no hashtags, no news-anchor phrases.\n"
        "Write 5 or 6 lines, each 5-13 words:\n"
        "  1: the hook, e.g. 'Huge drop alert for Pokemon collectors!' or 'Target just confirmed a huge Pokemon drop!'\n"
        "  middle: WHAT is dropping, WHERE (store names), WHEN (date), PRICE, WHAT'S INSIDE - only the ones in the source\n"
        "  last: 'Follow so you never miss a drop!' style\n"
        "RULES: use ONLY facts from the source. Never invent a store, date, price, quantity or product. "
        "Write prices exactly like the source with digits, e.g. $26.94. One price per line max. "
        "Name the store in the line when you talk about a store.\n"
        "Also write \"thumb\": 2-5 word ALL CAPS cover text, true to the source.\n"
        'Reply JSON only: {"thumb": "...", "lines": ["...", "..."]}\n\n'
        f"SOURCE:\n{source[:3500]}"
    )
    for model in gemini_models(key)[:3]:
        for attempt in range(3):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  params={"key": key},
                                  json={"contents": [{"parts": [{"text": prompt}]}],
                                        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}},
                                  timeout=60)
                if r.status_code in (429, 500, 503):
                    time.sleep(6 * (attempt + 1))
                    continue
                if r.status_code != 200:
                    break
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
                lines = [re.sub(r"\s+", " ", str(x)).strip() for x in data.get("lines", []) if str(x).strip()]
                bad = [(l, why) for l in lines for ok, why in [line_is_true(l, source)] if not ok]
                if bad or not 4 <= len(lines) <= 7 or any(len(l.split()) > 16 for l in lines):
                    print(f"Drop script: {model} rejected ({bad[:2] or len(lines)}), retrying...")
                    continue
                thumb = re.sub(r"\s+", " ", str(data.get("thumb", ""))).strip().upper()
                if thumb and len(thumb.split()) <= 6 and line_is_true(thumb, source)[0]:
                    story["thumb_text"] = thumb
                print(f"Drop script: {model}")
                return lines
            except Exception as e:
                print(f"Drop script: {model} error ({e})")
                time.sleep(3)
    return None


def ai_inside_script(story, source, key):
    """Upcoming product - WHAT'S INSIDE version of the script."""
    prompt = (
        "You write the voiceover for a 15-20 second Pokemon TCG 'WHAT'S INSIDE' Reel about an UPCOMING product, "
        "in the style of drop-alert pages (fast, hyped, collectors talking to collectors). Short spoken lines, "
        "contractions, plain words, no emojis, no hashtags, no news-anchor phrases.\n"
        "Write 5 or 6 lines, each 5-13 words:\n"
        "  1: hook naming the product, e.g. 'Here's what's inside the new 30th Celebration Booster Bundle!'\n"
        "  next 2-3 lines: EXACTLY what's inside - number of packs, promo cards, sleeves, dice, etc.\n"
        "  then: release date and price - only if in the source\n"
        "  last: 'Follow so you never miss a drop!' style\n"
        "RULES: use ONLY facts from the source. Never invent contents, quantities, dates, prices or stores. "
        "Write numbers and prices with digits exactly like the source, e.g. 6 booster packs, $26.94. "
        "One price per line max.\n"
        "Also write \"thumb\": 2-5 word ALL CAPS cover text, true to the source.\n"
        'Reply JSON only: {"thumb": "...", "lines": ["...", "..."]}\n\n'
        f"SOURCE:\n{source[:3500]}"
    )
    return _gemini_lines(story, source, key, prompt)


def _gemini_lines(story, source, key, prompt):
    from reel_v2 import gemini_models
    import time
    for model in gemini_models(key)[:3]:
        for attempt in range(3):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  params={"key": key},
                                  json={"contents": [{"parts": [{"text": prompt}]}],
                                        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}},
                                  timeout=60)
                if r.status_code in (429, 500, 503):
                    time.sleep(6 * (attempt + 1))
                    continue
                if r.status_code != 200:
                    break
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
                lines = [re.sub(r"\s+", " ", str(x)).strip() for x in data.get("lines", []) if str(x).strip()]
                bad = [(l, why) for l in lines for ok, why in [line_is_true(l, source)] if not ok]
                if bad or not 4 <= len(lines) <= 7 or any(len(l.split()) > 16 for l in lines):
                    print(f"Script: {model} rejected ({bad[:2] or len(lines)}), retrying...")
                    continue
                thumb = re.sub(r"\s+", " ", str(data.get("thumb", ""))).strip().upper()
                if thumb and len(thumb.split()) <= 6 and line_is_true(thumb, source)[0]:
                    story["thumb_text"] = thumb
                print(f"Script: {model}")
                return lines
            except Exception as e:
                print(f"Script: {model} error ({e})")
                time.sleep(3)
    return None


def fallback_drop_script(story):
    from reel_v2 import _shorten
    sc = story["scenes"]
    hook = "Here's what's inside the next big Pokemon drop!" if story.get("topic") == "inside" \
        else "Huge drop alert for Pokemon collectors!"
    lines = [hook]
    for s in sc:
        txt = s["text"]
        txt = txt.capitalize() if txt.isupper() else txt
        txt = txt.replace("\n", ", ")
        if s["tag"] == "WHERE":
            txt = "Dropping at " + txt
        lines.append(_shorten(txt, 13))
    lines.append("Follow so you never miss a drop!")
    return [l for l in lines if l][:7]


# ================================================================ images
def download(url, out):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        with open(out, "wb") as f:
            f.write(r.content)
        im = Image.open(out)
        im.load()
        return im.convert("RGB")
    except Exception as e:
        print(f"  image failed {url[:80]}: {e}")
        return None


def prep_product(im, out):
    """Plain/white background -> cut the product out. Busy photo -> clean rounded card."""
    im.thumbnail((1400, 1400))
    a = np.array(im).astype(np.int16)
    h, w = a.shape[:2]
    b = max(4, int(min(h, w) * 0.03))
    border = np.concatenate([a[:b].reshape(-1, 3), a[-b:].reshape(-1, 3), a[:, :b].reshape(-1, 3), a[:, -b:].reshape(-1, 3)])
    mean, std = border.mean(0), border.std(0).mean()
    if std < 14 and mean.mean() > 200:
        diff = np.abs(a - mean).max(2)
        m = (diff > 28).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        if n > 1:
            i = 1 + int(np.argmax(st[1:, 4]))
            m = (lab == i).astype(np.uint8) * 255
            cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            full = np.zeros_like(m)
            cv2.drawContours(full, cs, -1, 255, -1)          # fill holes (white parts of the box)
            cover = full.mean() / 255
            if 0.12 < cover < 0.95:
                full = cv2.GaussianBlur(cv2.erode(full, np.ones((3, 3), np.uint8)), (3, 3), 0)
                rgba = Image.fromarray(np.dstack([np.array(im), full]).astype(np.uint8), "RGBA")
                rgba.crop(rgba.getbbox()).save(out)
                return out
    # rounded card with a white border
    im = im.copy()
    r = int(min(im.size) * 0.06)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=r, fill=255)
    bw = max(6, int(min(im.size) * 0.018))
    card = Image.new("RGBA", (im.width + bw * 2, im.height + bw * 2), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=r + bw, fill=(255, 255, 255, 255))
    im.putalpha(mask)
    card.alpha_composite(im, (bw, bw))
    card.save(out)
    return out


def logo_for(store, work):
    slug = re.sub(r"[^a-z0-9]+", "-", store.lower().replace("é", "e")).strip("-")
    for ext in ("png", "webp"):
        p = os.path.join("assets", "logos", f"{slug}.{ext}")
        if os.path.exists(p):
            return p
    return store_badge(store, os.path.join(work, f"badge_{slug}.png"))


# ================================================================ main entry
def words_for(line, mp3):
    """Voice the line; captions use the line's own words timed to the voice."""
    from reel_v2 import speak, duration
    timed = speak(line, mp3)
    dur = duration(mp3)
    toks = line.split()
    if len(timed) == len(toks):
        return [(t, w["start"], w["end"]) for t, w in zip(toks, timed)], dur
    a, b = (timed[0]["start"], timed[-1]["end"]) if timed else (0.05, dur)
    weights = [len(t) + 2 for t in toks]
    tot, acc, out = sum(weights), 0, []
    for t, wgt in zip(toks, weights):
        s = a + (b - a) * acc / tot
        acc += wgt
        out.append((t, s, a + (b - a) * acc / tot))
    return out, dur


def estimate(line):
    out, t = [], 0.12
    for w in line.split():
        d = max(0.18, len(w) / 13.0 + 0.1)
        out.append((w, t, t + d))
        t += d + 0.03
    return out, t + 0.2


def compile_drop_reel(story, output_mp4="pokepulse_reel.mp4"):
    from main import make_cta_slide, RETAILERS
    work = tempfile.mkdtemp(prefix="dropreel_")
    ensure_font()

    source = story.get("context", "") + " " + " ".join(s["text"] for s in story["scenes"])
    lines = ai_drop_script(story, source) or fallback_drop_script(story)
    print("Drop reel script:")
    for l in lines:
        print("   ", l)

    # pictures
    urls = list(dict.fromkeys(story.get("image_pool") or [s["img_url"] for s in story["scenes"]]))[:6]
    prods, bg_path = [], None
    for i, u in enumerate(urls):
        im = download(u, os.path.join(work, f"raw_{i}"))
        if im is None or min(im.size) < 200:
            continue
        if bg_path is None:
            bg_path = os.path.join(work, "bg.jpg")
            im.save(bg_path, quality=92)
        prods.append(prep_product(im, os.path.join(work, f"prod_{i}.png")))
    if not prods:
        raise RuntimeError("no usable product images")

    # background: your clips / free store b-roll if available, else the blurred hero picture
    bg = bg_path
    if os.getenv("DROPS_BROLL", "on").lower() != "off":
        try:
            import reel_v2
            reel_v2.BROLL_QUERIES["drops_store"] = ["store shelves", "shopping cart store", "toy store",
                                                   "retail store aisle", "card shop"]
            got = reel_v2.get_broll("drops_store", out=os.path.join(work, "broll.mp4"))
            bg = got or bg_path
        except Exception as e:
            print(f"B-roll skipped ({e})")

    # voice: always on for drop reels unless REEL_VOICE_MODE=off
    voiced = os.getenv("REEL_VOICE_MODE", "").strip().lower() not in ("off", "false", "0", "never")
    shots, vo_clips, t = [], [], 0.0
    logo = None
    default_logo = store_badge("WHAT'S INSIDE" if story.get("topic") == "inside" else "DROP ALERT",
                               os.path.join(work, "badge_drop.png"))
    prod_i = 0
    # price tags go on a picture only when we KNOW which product the price is for
    one_price = len(set(re.findall(r"\$\d[\d,]*(?:\.\d{2})?", source))) == 1
    for i, line in enumerate(lines):
        words = None
        if voiced:
            try:
                mp3 = os.path.join(work, f"vo_{i}.mp3")
                words, dur = words_for(line, mp3)
                dur += 0.08
                vo_clips.append((mp3, t))
            except Exception as e:
                print(f"Voice failed ({e}) - captions only")
                voiced = False
        if not words:
            words, dur = estimate(line)
        words = [(w, a + t, b + t) for w, a, b in words]
        chunks = chunk_words(words)
        chunks[0]["start"] = t
        chunks[-1]["end"] = max(chunks[-1]["end"], t + dur)

        store = next((r for r in RETAILERS if _norm(r) in _norm(line)), None)
        if store:
            logo = logo_for(store, work)
        elif logo is None:
            first = next((r for r in RETAILERS if _norm(r) in _norm(source)), None)
            logo = logo_for(first, work) if first else default_logo

        prices = list(dict.fromkeys(re.findall(r"\$\d[\d,]*(?:\.\d{2})?", line)))
        if i == 0 and len(prods) >= 2:
            products = [{"img": prods[0]}, {"img": prods[1]}]
        elif len(prices) == 1 and one_price:
            # only one price in the whole article -> it belongs to the article's lead product picture
            products = [{"img": prods[0], "price": prices[0]}]
        else:
            if i > 0 and i % 2 == 0:
                prod_i += 1
            products = [{"img": prods[prod_i % len(prods)]}]
        shots.append({"start": t, "end": t + dur, "chunks": chunks, "logo": logo, "bg": bg, "products": products})
        t += dur

    # newsletter CTA slide + line
    make_cta_slide("f_cta.png")
    end_secs = 2.2
    if voiced:
        try:
            from reel_v2 import speak, duration, CTA_LINE
            cta = os.path.join(work, "vo_cta.mp3")
            speak(CTA_LINE, cta)
            vo_clips.append((cta, t))
            end_secs = max(2.0, duration(cta) + 0.25)
        except Exception as e:
            print(f"CTA voice failed ({e})")

    music = glob.glob("audio/*.mp3") + glob.glob("audio/*.wav")
    track = random.choice(music) if music else None
    print(f"Drop reel: {len(shots)} shots, {t + end_secs:.1f}s, voice={'on' if vo_clips else 'off'}, music={track}")
    return render_video(shots, output_mp4, end_card="f_cta.png", end_secs=end_secs,
                        vo_clips=vo_clips, music=track)
