"""
Make AI background videos with Google Veo (Gemini API) and add them to the clip library.

Run from GitHub: Actions -> "Make AI Backgrounds" -> Run workflow.
Uses the GEMINI_API_KEY secret. Veo is NOT in the Gemini free tier: billing must be on for the
Google AI Studio project. Veo 3.1 Lite costs about $0.05/second at 720p, so one 8-second clip is
about $0.40 and the default run (4 clips) about $1.60. Blocked generations are not charged.

Clips are saved as clips/lib_ai_*.mp4 and listed in clips/library.json with kind "ai", so the
Reels bot picks them like any other general background.

Prompts are original: no Pokemon characters, logos or brand names (those would be blocked and
would not be safe to post anyway).
"""
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone

import requests

API = "https://generativelanguage.googleapis.com/v1beta"
KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("VEO_MODEL", "").strip() or "veo-3.1-lite-generate-preview"
COUNT = int(os.getenv("AI_CLIP_COUNT", "4") or 4)
EXTRA = os.getenv("AI_CLIP_PROMPT", "").strip()      # optional custom prompt from the Run workflow form
LIB = os.path.join("clips", "library.json")

STYLE = ("Vertical 9:16 looping background video, bright saturated anime / cel-shaded style, smooth slow camera "
         "motion, no text, no logos, no brand names, no real people.")
PROMPTS = [
    ("meadow_creatures", "A sunny anime meadow full of wildflowers where small fluffy original fantasy creatures "
     "(round, big-eyed, pastel coloured, not from any existing franchise) hop and chase each other, puffy clouds."),
    ("energy_orbs", "Glowing orbs of elemental energy (fire red, water blue, grass green, lightning yellow, psychic "
     "purple) floating and swirling through a purple starry galaxy, sparkles trailing behind them."),
    ("holo_card_shine", "Extreme close-up of a blank holographic trading card with rainbow foil shimmer, light "
     "sweeping across it, sparkles, dark purple background with bokeh."),
    ("card_shop_shelves", "Anime-style cozy hobby shop interior, shelves stacked with colourful blank sealed card "
     "packs and boxes, warm lights, slow dolly forward."),
    ("floating_cards", "Dozens of shiny blank collectible cards slowly tumbling and floating through a colourful "
     "nebula in space, glittering stars, dreamy."),
    ("sunset_field", "Golden-hour anime grass field with fireflies, tiny original cute creatures silhouetted on a "
     "hill, sky in pink, orange and purple, gentle wind."),
    ("lightning_sky", "Stylised anime sky with playful yellow lightning bolts crackling between fluffy clouds, "
     "bright blue sky, sparks and glow."),
    ("toy_aisle", "Bright anime-style toy store aisle with colourful shelves of plush toys and blank boxed "
     "collectibles, confetti falling, cheerful."),
    ("binder_pages", "Close-up of a collector's binder with pages of blank shiny cards being flipped, soft light, "
     "sparkles on the foil, purple and blue background."),
    ("ocean_island", "Anime tropical island with crystal water and small original sea creatures splashing, "
     "rainbow in the sky, vivid colours."),
]


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:30] or "custom"


def start(prompt, params):
    body = {"instances": [{"prompt": f"{prompt} {STYLE}"}], "parameters": params}
    r = requests.post(f"{API}/models/{MODEL}:predictLongRunning",
                      headers={"x-goog-api-key": KEY, "Content-Type": "application/json"},
                      json=body, timeout=60)
    return r


def generate(prompt, out_path):
    # try the full settings first, then simpler ones if the model rejects a parameter
    for params in ({"aspectRatio": "9:16", "durationSeconds": 8}, {"aspectRatio": "9:16"}, {}):
        r = start(prompt, params)
        if r.status_code == 200:
            break
        print(f"  start failed with {params}: HTTP {r.status_code} {r.text[:300]}")
        if r.status_code in (401, 403, 429):
            return False
    else:
        return False
    op = r.json().get("name")
    print(f"  operation {op}")
    for _ in range(90):                       # up to ~15 min
        time.sleep(10)
        s = requests.get(f"{API}/{op}", headers={"x-goog-api-key": KEY}, timeout=60).json()
        if s.get("done"):
            break
    else:
        print("  timed out")
        return False
    if s.get("error"):
        print(f"  error: {s['error']}")
        return False
    try:
        uri = s["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
    except (KeyError, IndexError, TypeError):
        print(f"  no video in response (probably blocked): {json.dumps(s)[:400]}")
        return False
    v = requests.get(uri, headers={"x-goog-api-key": KEY}, timeout=300, allow_redirects=True)
    if v.status_code != 200 or len(v.content) < 50_000:
        print(f"  download failed: HTTP {v.status_code}, {len(v.content)} bytes")
        return False
    with open(out_path, "wb") as fh:
        fh.write(v.content)
    print(f"  saved {out_path} ({len(v.content) // 1024} KB)")
    return True


def main():
    if not KEY:
        sys.exit("GEMINI_API_KEY is not set")
    os.makedirs("clips", exist_ok=True)
    with open(LIB) as fh:
        lib = json.load(fh)
    have = {e["file"] for e in lib["clips"]}
    jobs = [(slug(EXTRA), EXTRA)] if EXTRA else []
    pool = PROMPTS[:]
    random.shuffle(pool)
    # prefer prompts we don't have a clip for yet
    pool.sort(key=lambda p: any(f.startswith(f"lib_ai_{p[0]}") for f in have))
    jobs += pool[:max(0, COUNT - len(jobs))]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    made = 0
    for name, prompt in jobs:
        fname = f"lib_ai_{name}_{stamp}.mp4"
        print(f"Generating {fname} with {MODEL}: {prompt[:80]}...")
        if generate(prompt, os.path.join("clips", fname)):
            lib["clips"].append({"file": fname, "keywords": [], "kind": "ai", "url": "",
                                 "note": f"Veo ({MODEL}) {stamp}: {prompt[:120]}"})
            made += 1
    with open(LIB, "w") as fh:
        json.dump(lib, fh, indent=2, ensure_ascii=False)
    print(f"Made {made} of {len(jobs)} clips.")
    if made == 0:
        sys.exit("No clips were made - check the log above (billing on? model name right?)")


if __name__ == "__main__":
    main()
