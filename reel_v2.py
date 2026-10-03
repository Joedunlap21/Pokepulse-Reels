"""
PokePulse Reel maker v2 - free voiceover + word-by-word captions.

  voice    : edge-tts (free Microsoft neural voices, no key)
  script   : optional Google Gemini free tier (GEMINI_API_KEY) rewrites lines short & punchy,
             otherwise simple trimming
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

# The "Multilingual" voices are Microsoft's newest, most human-sounding ones.
VOICES = ["en-US-AndrewMultilingualNeural", "en-US-BrianMultilingualNeural",
          "en-US-AvaMultilingualNeural", "en-US-EmmaMultilingualNeural",
          "en-US-ChristopherNeural", "en-US-SteffanNeural", "en-GB-RyanNeural", "en-AU-WilliamNeural"]
VOICE = os.getenv("REEL_VOICE", "").strip() or "en-US-AndrewMultilingualNeural"
if VOICE == "random":
    VOICE = random.choice(VOICES[:4])
VOICE_RATE = os.getenv("REEL_VOICE_RATE", "").strip() or "+20%"
VOICE_PITCH = os.getenv("REEL_VOICE_PITCH", "").strip() or "+6Hz"   # slightly higher = more upbeat
# auto = voice on news & sales only, music-only for drops & bulk lists. on / off force it.
VOICE_MODE = os.getenv("REEL_VOICE_MODE", "").strip().lower() or "auto"
MUSIC_VOLUME = 0.14                                      # music under the voice

# Instagram covers the top ~220px and bottom ~420px (username, caption, buttons) and the right edge.
ART_TOP, ART_BOTTOM = 320, 1090
TAG_Y = 210
CAP_CENTER_Y = 1270
CAP_MAX_W = 900
FPS = 30


# ---------------------------------------------------------------- script

STOP_END = {"is", "are", "the", "a", "an", "to", "of", "with", "and", "for", "on", "in", "at", "will", "be", "its", "this", "that", "from", "as", "by", "set"}

def _shorten(s, max_words=14):
    s = re.sub(r"^(according to (a report from )?[\w\s\.\-']+?,\s*)", "", s, flags=re.I)
    s = re.sub(r"\breportedly\s+", "", s, flags=re.I)
    s = re.sub(r"\s*\([^)]*\)", "", s)
    s = s.strip().rstrip(".")
    words = s.split()
    if len(words) > max_words:
        cut = " ".join(words[:max_words])
        # end on a clause if we can
        m = re.match(r"(.{25,}?)[,;:]\s", cut + " ")
        s = m.group(1) if m else cut
    s = s.strip(" ,;:-")
    ws = s.split()
    while len(ws) > 3 and ws[-1].lower().strip(".,") in STOP_END:
        ws.pop()
    s = " ".join(ws)
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


def ai_script(story):
    """Optional free rewrite with Google Gemini (free key from aistudio.google.com).
    Returns [{"say":..., "screen":...}, ...] or None -> simple trimming is used instead."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    facts = [sc["text"] + (f" ({sc['sub']})" if sc.get("sub") else "") for sc in story["scenes"]]
    prompt = (
        "You are the voice of PokePulse, a Pokemon card collector page on Instagram. "
        "Write the script for a short Reel like a hyped-up collector talking to friends - upbeat, high energy, "
        "fun, confident. Use contractions and short punchy sentences. End most lines with an exclamation mark "
        "so the voice reads them with energy. Plain everyday words. No news-anchor phrases "
        "('reportedly', 'according to', 'it has been announced'), no corporate words, no hashtags, no emojis.\n"
        "NEVER invent facts, prices, dates or card names that aren't in the source.\n\n"
        f"Write exactly {len(facts)} slides, one per slide below, in the same order and about the same thing.\n"
        "For each slide give:\n"
        '  "say": what the voice says, 6-14 words, sounds natural out loud\n'
        '  "screen": the big on-screen text, 2-6 words, ALL CAPS, the key fact\n'
        "Slide 1 is the hook - make a collector stop scrolling (a surprise, a number, a question). "
        "Start straight with the news itself. Never open with filler like 'Okay', 'So', 'Guys', 'Yo', "
        "'This one's wild', 'You won't believe', 'Listen up'.\n"
        "The last slide should land the point (why it matters / what to do).\n"
        'Reply with JSON only: {"slides": [{"say": "...", "screen": "..."}]}\n\n'
        f"FULL ARTICLE CONTEXT:\n{story.get('context', '')[:3000]}\n\n"
        "SLIDES:\n" + "\n".join(f"{i+1}. {f}" for i, f in enumerate(facts))
    )
    model = os.getenv("REEL_AI_MODEL", "").strip() or "gemini-2.5-flash"
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json"}},
            timeout=60)
        if r.status_code != 200:
            print(f"AI script: Gemini HTTP {r.status_code} {r.text[:200]!r}")
            return None
        content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        m = re.search(r"\{.*\}", content, re.S)
        slides = json.loads(m.group(0))["slides"]
        out = [{"say": re.sub(r"\s+", " ", str(x.get("say", ""))).strip(),
                "screen": re.sub(r"\s+", " ", str(x.get("screen", ""))).strip().upper()} for x in slides]
        if len(out) != len(facts) or any(not x["say"] or not x["screen"] or len(x["say"].split()) > 22
                                         or len(x["screen"].split()) > 9 for x in out):
            print(f"AI script rejected ({len(out)} slides)")
            return None
        print(f"AI script: {model}")
        return out
    except Exception as e:
        print(f"AI script failed ({e}) - using simple trimming")
        return None


def build_script(story):
    script = ai_script(story)
    if script:
        return script
    says = fallback_lines(story)
    return [{"say": say, "screen": _shorten(sc["text"], 7).rstrip(".").upper()}
            for say, sc in zip(says, story["scenes"])]


def wants_voice(story):
    if VOICE_MODE in ("on", "true", "1", "always"):
        return True
    if VOICE_MODE in ("off", "false", "0", "never"):
        return False
    return story.get("topic") in ("news", "sales")


# ---------------------------------------------------------------- voice

async def _tts(text, out_mp3):
    import edge_tts
    comm = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH, boundary="WordBoundary")
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


def render_block(text, path):
    """Music-only mode: the slide's short on-screen line, big, up to 3 lines."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    words = text.upper().split()
    for size in range(150, 76, -6):
        f, stroke = get_font(size), max(6, size // 14)
        lines, cur = [], []
        for w in words:
            if cur and text_w(d, " ".join(cur + [w]), f, stroke) > CAP_MAX_W:
                lines.append(cur)
                cur = []
            cur.append(w)
        if cur:
            lines.append(cur)
        if len(lines) <= 3:
            break
    line_h = int(size * 1.0)
    y = CAP_CENTER_Y - (len(lines) * line_h) // 2 + 40
    space = text_w(d, " ", f)
    for ln in lines:
        x = (W - text_w(d, " ".join(ln), f, stroke)) // 2
        for w in ln:
            d.text((x, y), w, font=f, fill=YELLOW if _is_key(w) else WHITE,
                   stroke_width=stroke, stroke_fill="#000000")
            x += text_w(d, w, f, stroke) + space
        y += line_h
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


def render_scene_clip(scene, idx, words, dur, zoom_in, out, screen_text=None):
    bg, tag = f"v2_bg_{idx}.png", f"v2_tag_{idx}.png"
    render_background(scene, bg)
    render_tag(scene["tag"], tag)
    caps = []
    if words:
        chunks = chunk_words(words)
        for j, ch in enumerate(chunks):
            p = f"v2_cap_{idx}_{j}.png"
            render_caption([c["w"] for c in ch], p)
            start = ch[0]["start"]
            end = chunks[j + 1][0]["start"] if j + 1 < len(chunks) else dur
            caps.append((p, max(0, start - 0.05), end))
    elif screen_text:
        p = f"v2_block_{idx}.png"
        render_block(screen_text, p)
        caps.append((p, 0.1, dur))

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

CTA_LINE = "Want the full weekly breakdown? It's free. Link in bio."

def compile_voiced_reel(story, output_mp4="pokepulse_reel.mp4"):
    from main import make_cta_slide, render_motion_clip

    script = build_script(story)
    voiced = wants_voice(story)
    print(f"Mode: {'VOICEOVER (' + VOICE + ')' if voiced else 'MUSIC ONLY'}  [topic={story.get('topic')}]")
    for i, x in enumerate(script):
        print(f"  {i+1}. say: {x['say']}  |  screen: {x['screen']}")

    clips, voices = [], []
    for i, (sc, x) in enumerate(zip(story["scenes"], script)):
        out = f"v2_scene_{i}.mp4"
        if voiced:
            vo = f"v2_vo_{i}.mp3"
            words = speak(x["say"], vo)
            dur = round(duration(vo) + 0.08, 3)
            render_scene_clip(sc, i, words, dur, i % 2 == 0, out)
            voices.append((vo, dur))
        else:
            n = len(x["screen"].split())
            dur = round(max(1.5, min(0.7 + n * 0.28, 2.5)), 2)
            render_scene_clip(sc, i, None, dur, i % 2 == 0, out, screen_text=x["screen"])
        clips.append((out, dur))

    make_cta_slide("f_cta.png")
    if voiced:
        cta_vo = "v2_vo_cta.mp3"
        speak(CTA_LINE, cta_vo)
        cta_dur = round(max(1.8, duration(cta_vo) + 0.2), 3)
        voices.append((cta_vo, cta_dur))
    else:
        cta_dur = 1.8
    render_motion_clip("f_cta.png", None, cta_dur, "v2_scene_cta.mp4")
    clips.append(("v2_scene_cta.mp4", cta_dur))
    total = sum(d for _, d in clips)

    with open("v2_playlist.txt", "w") as f:
        for c, _ in clips:
            f.write(f"file '{c}'\n")

    music = glob.glob("audio/*.mp3") + glob.glob("audio/*.wav")
    track = random.choice(music) if music else None
    if track:
        print(f"Music: {track}")
    fade = f"afade=t=out:st={max(0.5, total - 1.2):.2f}:d=1.2"

    if voiced:
        # voice track: each line padded to its scene length so it stays in sync
        vo_inputs, vo_fc = [], ""
        for k, (v, d) in enumerate(voices):
            vo_inputs += ["-i", v]
            vo_fc += f"[{k}]apad=whole_dur={d}[a{k}];"
        vo_fc += "".join(f"[a{k}]" for k in range(len(voices))) + f"concat=n={len(voices)}:v=0:a=1[vo]"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + vo_inputs +
                       ["-filter_complex", vo_fc, "-map", "[vo]", "-ar", "44100", "v2_voice.wav"], check=True)
        mix_in = ["-i", "v2_voice.wav"]
        if track:
            mix_in += ["-stream_loop", "-1", "-i", track]
            afc = (f"[2:a]volume={MUSIC_VOLUME},{fade}[m];"
                   f"[1:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
        else:
            afc = "[1:a]anull[aout]"
    else:
        if track:
            mix_in = ["-stream_loop", "-1", "-i", track]
            afc = f"[1:a]volume=0.9,{fade}[aout]"
        else:
            mix_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            afc = "[1:a]anull[aout]"

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "v2_playlist.txt"]
                   + mix_in +
                   ["-filter_complex", afc, "-map", "0:v", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", output_mp4], check=True)
    return output_mp4


# ---------------------------------------------------------------- voice samples

SAMPLE_LINE = "Pokemon just dropped a brand new box! Here's what's inside, and what it'll cost you!"

def make_voice_samples(folder="voice_samples"):
    os.makedirs(folder, exist_ok=True)
    global VOICE
    for v in VOICES:
        VOICE = v
        try:
            speak(SAMPLE_LINE, os.path.join(folder, f"{v}.mp3"))
            print(f"made sample: {v}")
        except Exception as e:
            print(f"{v} failed: {e}")


if __name__ == "__main__":
    make_voice_samples()
