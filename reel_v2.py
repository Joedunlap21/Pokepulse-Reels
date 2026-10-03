"""
PokePulse Reel maker v2 - free voiceover + word-by-word captions.

  voice    : edge-tts (free Microsoft neural voices, no key)
  script   : GitHub Models (free with GITHUB_TOKEN) rewrites lines short & punchy,
             falls back to simple trimming if that's unavailable
  visuals  : big art + blurred fill, tag at top, captions in the IG safe zone
  audio    : voice on top, music ducked underneath

main.py calls compile_voiced_reel(story). If anything here fails, main.py
falls back to the old silent slideshow so a post never gets skipped.
"""
import os
import re
import json
import glob
import random
import asyncio
import subprocess

import requests
from PIL import Image, ImageDraw, ImageFilter

from main import W, H, BG, YELLOW, WHITE, GREEN, RED, get_font, text_w, load_image

VOICE = os.getenv("REEL_VOICE", "en-US-AndrewNeural")   # try en-US-GuyNeural / en-US-ChristopherNeural
VOICE_RATE = os.getenv("REEL_VOICE_RATE", "+12%")       # a bit faster = more energy
MUSIC_VOLUME = 0.14                                      # music under the voice

# Instagram covers the top ~220px and bottom ~420px (username, caption, buttons) and the right edge.
ART_TOP, ART_BOTTOM = 320, 1090
TAG_Y = 210
CAP_CENTER_Y = 1270
CAP_MAX_W = 900
FPS = 30


# ---------------------------------------------------------------- script

def _shorten(s, max_words=14):
    s = re.sub(r"^(according to (a report from )?[\w\s\.\-']+?,\s*)", "", s, flags=re.I)
    s = re.sub(r"\s*\([^)]*\)", "", s)
    s = s.strip().rstrip(".")
    words = s.split()
    if len(words) > max_words:
        cut = " ".join(words[:max_words])
        # end on a clause if we can
        m = re.match(r"(.{25,}?)[,;:]\s", cut + " ")
        s = m.group(1) if m else cut
    s = s.strip(" ,;:-")
    return (s[:1].upper() + s[1:] + ".") if s else s


def _bulk_line(i, sc):
    name = sc["text"].title()
    price = re.search(r"\$[\d,]+\.?\d*", sc.get("sub", ""))
    p = price.group(0) if price else ""
    return f"Number {i}. {name}. Going for about {p}." if p else f"Number {i}. {name}."


def fallback_lines(story):
    lines = []
    for i, sc in enumerate(story["scenes"]):
        if story["story_id"].startswith("bulk") and i > 0:
            lines.append(_bulk_line(i, sc))
        else:
            lines.append(_shorten(sc["text"].capitalize() if sc["text"].isupper() else sc["text"]))
    if story["story_id"].startswith("bulk"):
        lines[0] = "Check your bulk! " + _shorten(story["scenes"][0]["text"].capitalize(), 14)
    return lines


def ai_lines(story):
    """Free rewrite through GitHub Models. Returns None on any problem."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return None
    facts = [sc["text"] + (f" ({sc['sub']})" if sc.get("sub") else "") for sc in story["scenes"]]
    prompt = (
        "You write voiceover for a fast Pokemon TCG news Instagram Reel.\n"
        f"Rewrite each of these {len(facts)} slides into ONE short spoken line.\n"
        "Rules: max 14 words per line, punchy and hype but factual, no hashtags, no emojis, "
        "never invent facts, prices or dates that aren't given, write numbers how they're spoken is fine. "
        "Line 1 is the hook - make people stop scrolling.\n"
        'Reply with JSON only: {"lines": ["...", "..."]}\n\n'
        + "\n".join(f"{i+1}. {f}" for i, f in enumerate(facts))
    )
    raw = ""
    try:
        r = requests.post(
            "https://models.github.ai/inference/chat/completions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                     "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
            json={"model": os.getenv("REEL_AI_MODEL", "openai/gpt-4.1-mini"),
                  "messages": [{"role": "system", "content": "You reply with valid JSON only."},
                               {"role": "user", "content": prompt}],
                  "temperature": 0.6},
            timeout=45)
        raw = r.text
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"] or ""
        m = re.search(r"\{.*\}", content, re.S)
        lines = [re.sub(r"\s+", " ", str(l)).strip() for l in json.loads(m.group(0))["lines"]]
        if len(lines) != len(facts) or any(not l or len(l.split()) > 22 for l in lines):
            print(f"AI script rejected (got {len(lines)} lines)")
            return None
        print("AI script: GitHub Models")
        return lines
    except Exception as e:
        print(f"AI script unavailable ({e}) - using simple trimming. Response: {raw[:300]!r}")
        return None


# ---------------------------------------------------------------- voice

async def _tts(text, out_mp3):
    import edge_tts
    comm = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE, boundary="WordBoundary")
    words = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"w": chunk["text"],
                              "start": chunk["offset"] / 1e7,
                              "end": (chunk["offset"] + chunk["duration"]) / 1e7})
    return words


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    return float(out or 0)


def speak(text, out_mp3):
    """Returns word timings. Raises if the voice service fails (caller falls back)."""
    for attempt in range(3):
        try:
            words = asyncio.run(_tts(text, out_mp3))
            if os.path.getsize(out_mp3) > 1000:
                if not words:   # no timings -> spread words evenly
                    d, ws = duration(out_mp3), text.split()
                    words = [{"w": w, "start": d * i / len(ws), "end": d * (i + 1) / len(ws)}
                             for i, w in enumerate(ws)]
                return words
        except Exception as e:
            print(f"Voice attempt {attempt+1} failed: {e}")
    raise RuntimeError("edge-tts voice unavailable")


# ---------------------------------------------------------------- visuals

def render_background(scene, path):
    bg = Image.new("RGB", (W, H), BG)
    raw = load_image(scene["img_url"])
    if raw is not None:
        # full-screen blurred version so the whole frame has colour
        s = max(W / raw.width, H / raw.height)
        cover = raw.resize((int(raw.width * s) + 1, int(raw.height * s) + 1), Image.Resampling.LANCZOS)
        l, t = (cover.width - W) // 2, (cover.height - H) // 2
        cover = cover.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(30))
        bg = Image.blend(cover, Image.new("RGB", (W, H), BG), 0.45)
        # sharp art, as big as fits the art zone (full width for landscape images)
        art = raw.copy()
        if art.width / art.height > 1.4:   # wide news images: trim the sides so the art is bigger
            nw = int(art.height * 1.33)
            art = art.crop(((art.width - nw) // 2, 0, (art.width - nw) // 2 + nw, art.height))
        box_h = ART_BOTTOM - ART_TOP
        s = min(W / art.width, box_h / art.height)
        art = art.resize((int(art.width * s), int(art.height * s)), Image.Resampling.LANCZOS)
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle(
            [(W - art.width) // 2 + 10, ART_TOP + (box_h - art.height) // 2 + 14,
             (W + art.width) // 2 + 10, ART_TOP + (box_h + art.height) // 2 + 14], fill=(0, 0, 0, 150))
        bg = Image.alpha_composite(bg.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(14))).convert("RGB")
        bg.paste(art, ((W - art.width) // 2, ART_TOP + (box_h - art.height) // 2))
    # darken behind the captions so they always read
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(ART_BOTTOM - 40, H):
        a = min(200, int(200 * (y - (ART_BOTTOM - 40)) / 160))
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    bg = Image.alpha_composite(bg.convert("RGBA"), shade).convert("RGB")
    bg.save(path)


def render_tag(tag, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = get_font(64)
    tw = text_w(d, tag, f) + 70
    x = (W - tw) // 2
    d.rounded_rectangle([x + 5, TAG_Y + 6, x + tw + 5, TAG_Y + 92], radius=12, fill=(0, 0, 0, 255))
    d.rounded_rectangle([x, TAG_Y, x + tw, TAG_Y + 86], radius=12, fill=RED)
    d.text((x + 35, TAG_Y + 8), tag, font=f, fill=WHITE)
    img.save(path)


def _is_key(word):
    return bool(re.search(r"[\d$%]", word)) or word.strip(".,!?").upper() in {
        "NEW", "PSA", "RECORD", "MILLION", "FREE", "EXCLUSIVE", "RARE", "BREAKING", "CONFIRMED"}


def render_caption(words, path):
    """1-3 words, huge, white with yellow on numbers / key words."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    text = " ".join(w.upper() for w in words)
    size = 150
    while size > 80:
        f = get_font(size)
        if text_w(d, text, f, size // 14) <= CAP_MAX_W:
            break
        size -= 6
    f, stroke = get_font(size), max(6, size // 14)
    x = (W - text_w(d, text, f, stroke)) // 2
    y = CAP_CENTER_Y - size // 2
    space = text_w(d, " ", f)
    for w in words:
        w = w.upper()
        d.text((x, y), w, font=f, fill=YELLOW if _is_key(w) else WHITE,
               stroke_width=stroke, stroke_fill="#000000")
        x += text_w(d, w, f, stroke) + space
    img.save(path)


def chunk_words(words, max_words=3, max_chars=14):
    chunks, cur = [], []
    for w in words:
        chars = sum(len(c["w"]) + 1 for c in cur)
        if cur and chars + len(w["w"]) > max_chars:
            chunks.append(cur)
            cur = []
        cur.append(w)
        if len(cur) >= max_words or re.search(r"[.,!?;:]$", w["w"]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def render_scene_clip(scene, idx, words, dur, zoom_in, out):
    bg, tag = f"v2_bg_{idx}.png", f"v2_tag_{idx}.png"
    render_background(scene, bg)
    render_tag(scene["tag"], tag)
    chunks = chunk_words(words)
    caps = []
    for j, ch in enumerate(chunks):
        p = f"v2_cap_{idx}_{j}.png"
        render_caption([c["w"] for c in ch], p)
        start = ch[0]["start"]
        end = chunks[j + 1][0]["start"] if j + 1 < len(chunks) else dur
        caps.append((p, max(0, start - 0.05), end))

    frames = int(dur * FPS)
    z = f"1+0.06*on/{frames}" if zoom_in else f"1.06-0.06*on/{frames}"
    inputs = ["-framerate", str(FPS), "-loop", "1", "-t", str(dur), "-i", bg,
              "-framerate", str(FPS), "-loop", "1", "-t", str(dur), "-i", tag]
    fc = (f"[0]scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d=1:s={W}x{H}:fps={FPS}[b0];"
          f"[1]format=rgba,fade=t=in:st=0:d=0.15:alpha=1[tg];[b0][tg]overlay=0:0[b1]")
    last = "b1"
    for k, (p, s, e) in enumerate(caps):
        inputs += ["-i", p]
        fc += f";[{last}][{k + 2}]overlay=0:0:enable='between(t,{s:.2f},{e:.2f})'[c{k}]"
        last = f"c{k}"
    fc += f";[{last}]format=yuv420p[v]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + inputs +
                   ["-filter_complex", fc, "-map", "[v]", "-t", f"{dur:.3f}", "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out], check=True)


# ---------------------------------------------------------------- build

CTA_LINE = "Get the free weekly PokePulse report. Link in bio."

def compile_voiced_reel(story, output_mp4="pokepulse_reel.mp4"):
    from main import make_cta_slide, render_motion_clip

    lines = ai_lines(story) or fallback_lines(story)
    for i, l in enumerate(lines):
        print(f"  VO {i+1}: {l}")

    clips, voices = [], []
    for i, (sc, line) in enumerate(zip(story["scenes"], lines)):
        vo = f"v2_vo_{i}.mp3"
        words = speak(line, vo)
        dur = round(duration(vo) + 0.25, 3)
        out = f"v2_scene_{i}.mp4"
        render_scene_clip(sc, i, words, dur, i % 2 == 0, out)
        clips.append((out, dur))
        voices.append((vo, dur))

    # CTA
    cta_vo = "v2_vo_cta.mp3"
    speak(CTA_LINE, cta_vo)
    cta_dur = round(max(2.2, duration(cta_vo) + 0.4), 3)
    make_cta_slide("f_cta.png")
    render_motion_clip("f_cta.png", None, cta_dur, "v2_scene_cta.mp4")
    clips.append(("v2_scene_cta.mp4", cta_dur))
    voices.append((cta_vo, cta_dur))
    total = sum(d for _, d in clips)

    with open("v2_playlist.txt", "w") as f:
        for c, _ in clips:
            f.write(f"file '{c}'\n")

    # voice track: each line padded to its scene length so it stays in sync
    vo_inputs, vo_fc = [], ""
    for k, (v, d) in enumerate(voices):
        vo_inputs += ["-i", v]
        vo_fc += f"[{k}]apad=whole_dur={d}[a{k}];"
    vo_fc += "".join(f"[a{k}]" for k in range(len(voices))) + f"concat=n={len(voices)}:v=0:a=1[vo]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + vo_inputs +
                   ["-filter_complex", vo_fc, "-map", "[vo]", "-ar", "44100", "v2_voice.wav"], check=True)

    music = glob.glob("audio/*.mp3") + glob.glob("audio/*.wav")
    mix_in = ["-i", "v2_voice.wav"]
    if music:
        track = random.choice(music)
        print(f"Music: {track}")
        mix_in += ["-stream_loop", "-1", "-i", track]
        afc = (f"[2:a]volume={MUSIC_VOLUME},afade=t=out:st={max(0.5, total - 1.2):.2f}:d=1.2[m];"
               f"[1:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
    else:
        afc = "[1:a]anull[aout]"

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "v2_playlist.txt"]
                   + mix_in +
                   ["-filter_complex", afc, "-map", "0:v", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", output_mp4], check=True)
    return output_mp4
