import os
import random
import time
import subprocess
import cloudinary
import cloudinary.uploader
import requests
from PIL import Image, ImageDraw, ImageFont

# Cloudinary Setup from GitHub Secrets
cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL", "").strip()
)

API_HEADERS = {"User-Agent": "Mozilla/5.0 (CardStax/PokePulse Reels Agent)"}

# Verified Instagram Business Account ID for @card.stax (hardcoded to prevent any newline bugs)
IG_USER_ID = "17841472317326348"

# High-Energy Royalty-Free Audio Tracks
HYPE_AUDIO_TRACKS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",
    "https://cdn.pixabay.com/download/audio/2022/10/14/audio_9939f77c30.mp3"
]

# High-Hype Pokémon Cards for Viral Reels
REEL_TOPICS = [
    {
        "hook": "THE MOST EXPENSIVE MODERN CARDS",
        "subhook": "HOLD OR SELL IN 2026?",
        "cards": [
            {"name": "UMBREON VMAX ALT ART", "set": "Evolving Skies", "price": "850.00 USD", "img": "https://images.pokemontcg.io/swsh7/215_hires.png"},
            {"name": "GIRATINA V ALT ART", "set": "Lost Origin", "price": "395.00 USD", "img": "https://images.pokemontcg.io/swsh11/186_hires.png"},
            {"name": "PIKACHU EX SIR", "set": "Surging Sparks", "price": "380.00 USD", "img": "https://images.pokemontcg.io/sv8/238_hires.png"}
        ]
    },
    {
        "hook": "POKÉMON CARDS EXPLODING IN VALUE",
        "subhook": "RECENT 30-DAY SALES SURGE",
        "cards": [
            {"name": "CHARIZARD EX SIR", "set": "151 Special Set", "price": "210.00 USD", "img": "https://images.pokemontcg.io/sv3pt5/199_hires.png"},
            {"name": "TERAPAGOS EX SIR", "set": "Stellar Crown", "price": "145.00 USD", "img": "https://images.pokemontcg.io/sv7/170_hires.png"},
            {"name": "MAGIKARP IR", "set": "Paldea Evolved", "price": "135.00 USD", "img": "https://images.pokemontcg.io/sv2/203_hires.png"}
        ]
    }
]

# --- TYPOGRAPHY & AUTO-FIT ---
def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "Arial.ttf"
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_autofit_text(draw, text, box, max_font_size=80, min_font_size=20, fill="white", bold=True, align="center"):
    x1, y1, x2, y2 = box
    max_w = x2 - x1
    max_h = y2 - y1

    curr_size = max_font_size
    font = get_font(curr_size, bold=bold)

    while curr_size > min_font_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            break
        curr_size -= 2
        font = get_font(curr_size, bold=bold)

    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    if align == "center":
        x = x1 + (max_w - w) / 2 - bbox[0]
    elif align == "left":
        x = x1 - bbox[0]
    else:
        x = x2 - w - bbox[0]

    y = y1 + (max_h - h) / 2 - bbox[1]
    draw.text((x, y), text, fill=fill, font=font)
    return font

# --- 9:16 VERTICAL FRAME GENERATORS (1080x1920) ---
W, H = 1080, 1920

def make_intro_frame(topic, out_path="f1_intro.png"):
    img = Image.new("RGB", (W, H), (10, 12, 16))
    draw = ImageDraw.Draw(img)

    pill_w, pill_h = 480, 70
    pill_x1 = (W - pill_w) // 2
    draw.rounded_rectangle([pill_x1, 280, pill_x1 + pill_w, 280 + pill_h], radius=35, fill="#E50914")
    draw_autofit_text(draw, "MARKET WATCH 2026", (pill_x1, 280, pill_x1 + pill_w, 280 + pill_h), max_font_size=34, min_font_size=22, fill="#FFFFFF", bold=True)

    draw_autofit_text(draw, topic["hook"], (60, 420, W - 60, 680), max_font_size=88, min_font_size=40, fill="#FFE600", bold=True)
    draw_autofit_text(draw, topic["subhook"], (60, 720, W - 60, 820), max_font_size=42, min_font_size=24, fill="#00FF66", bold=True)

    draw_autofit_text(draw, "@CARD.STAX", (60, 1600, W - 60, 1680), max_font_size=48, min_font_size=28, fill="#A0AEC0", bold=True)
    img.save(out_path)

def make_card_frame(card_data, rank, out_path):
    img = Image.new("RGB", (W, H), (10, 12, 16))
    draw = ImageDraw.Draw(img)

    pill_w, pill_h = 360, 64
    pill_x1 = (W - pill_w) // 2
    draw.rounded_rectangle([pill_x1, 140, pill_x1 + pill_w, 140 + pill_h], radius=32, fill="#E50914")
    draw_autofit_text(draw, f"TOP HIT #{rank}", (pill_x1, 140, pill_x1 + pill_w, 140 + pill_h), max_font_size=32, min_font_size=22, fill="#FFFFFF", bold=True)

    draw_autofit_text(draw, card_data["name"], (60, 230, W - 60, 340), max_font_size=68, min_font_size=36, fill="#FFE600", bold=True)

    img_data = requests.get(card_data["img"], headers=API_HEADERS).content
    with open("temp_card.png", "wb") as f:
        f.write(img_data)

    card = Image.open("temp_card.png").convert("RGBA")
    card.thumbnail((720, 960), Image.Resampling.LANCZOS)
    cw, ch = card.size
    cx = (W - cw) // 2
    cy = 380

    draw.rounded_rectangle([cx - 12, cy - 6, cx + cw + 12, cy + ch + 14], radius=24, fill=(0, 0, 0))
    img.paste(card, (cx, cy), mask=card.split()[3])

    box_w, box_h = 800, 180
    bx1 = (W - box_w) // 2
    by1 = 1420
    draw.rounded_rectangle([bx1, by1, bx1 + box_w, by1 + box_h], radius=24, fill="#161B22", outline="#00FF66", width=4)
    draw_autofit_text(draw, f"VERIFIED MARKET FLOOR: {card_data['price']}", (bx1 + 20, by1 + 20, bx1 + box_w - 20, by1 + 100), max_font_size=42, min_font_size=24, fill="#FFFFFF", bold=True)
    draw_autofit_text(draw, f"SET: {card_data['set'].upper()}", (bx1 + 20, by1 + 105, bx1 + box_w - 20, by1 + 160), max_font_size=32, min_font_size=20, fill="#A0AEC0", bold=True)

    draw_autofit_text(draw, "@CARD.STAX", (60, 1720, W - 60, 1800), max_font_size=44, min_font_size=26, fill="#A0AEC0", bold=True)
    img.save(out_path)

def make_cta_frame(out_path="f5_cta.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    cdata = requests.get(cta_url, headers=API_HEADERS).content
    with open("raw_cta.png", "wb") as f:
        f.write(cdata)

    base = Image.new("RGB", (W, H), (10, 12, 16))
    cta_img = Image.open("raw_cta.png").convert("RGB")
    cta_img.thumbnail((1080, 1350), Image.Resampling.LANCZOS)
    cw, ch = cta_img.size
    cx = (W - cw) // 2
    cy = (H - ch) // 2
    base.paste(cta_img, (cx, cy))

    draw = ImageDraw.Draw(base)
    draw_autofit_text(draw, "TAP LINK IN BIO TO SUBSCRIBE FREE", (60, 1680, W - 60, 1780), max_font_size=42, min_font_size=22, fill="#FFE600", bold=True)
    base.save(out_path)

# --- VIDEO RENDERING VIA FFMPEG ---
def build_reel_mp4(frame_files, output_mp4="pokepulse_reel.mp4"):
    durations = [2.5, 3.0, 3.0, 3.0, 3.0]
    total_duration = sum(durations)

    with open("playlist.txt", "w") as f:
        for frame, dur in zip(frame_files, durations):
            f.write(f"file '{frame}'\n")
            f.write(f"duration {dur}\n")
        f.write(f"file '{frame_files[-1]}'\n")

    audio_url = random.choice(HYPE_AUDIO_TRACKS)
    print(f"Downloading high-energy audio track: {audio_url}")
    audio_data = requests.get(audio_url, headers=API_HEADERS).content
    with open("bg_audio.mp3", "wb") as f:
        f.write(audio_data)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-i", "bg_audio.mp3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", f"[1:a]afade=t=out:st={total_duration - 1.5}:d=1.5[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", str(total_duration),
        "-vf", "scale=1080:1920",
        output_mp4
    ]
    subprocess.run(cmd, check=True)
    return output_mp4

# --- PUBLISHING TO REELS AND STORY ---
def publish_content(video_url, caption):
    access_token = os.getenv("IG_ACCESS_TOKEN", "").strip()

    # 1. PUBLISH TO REELS
    print("Step 1: Initializing Reels container with audio...")
    res = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token
    }).json()

    if "id" in res:
        container_id = res["id"]
        print(f"Reel Container ID: {container_id}. Transcoding...")
        for _ in range(15):
            time.sleep(10)
            status = requests.get(f"https://graph.facebook.com/v21.0/{container_id}?fields=status_code&access_token={access_token}").json()
            code = status.get("status_code")
            print(f"Status: {code}")
            if code == "FINISHED":
                break
            elif code == "ERROR":
                print("Encoding error on Instagram.")
                break

        pub = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish", data={
            "creation_id": container_id,
            "access_token": access_token
        }).json()
        print(f"Reel Publish Result: {pub}")
    else:
        print("Reel Error:", res)

    # 2. ALSO PUBLISH TO STORY (for Highlights)
    print("\nStep 2: Publishing to Story...")
    s_res = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media", data={
        "media_type": "STORIES",
        "video_url": video_url,
        "access_token": access_token
    }).json()

    if "id" in s_res:
        s_id = s_res["id"]
        for _ in range(12):
            time.sleep(8)
            s_status = requests.get(f"https://graph.facebook.com/v21.0/{s_id}?fields=status_code&access_token={access_token}").json()
            if s_status.get("status_code") == "FINISHED":
                break
        s_pub = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish", data={
            "creation_id": s_id,
            "access_token": access_token
        }).json()
        print(f"Story Publish Result: {s_pub}")
    else:
        print("Story Error:", s_res)


if __name__ == "__main__":
    topic = random.choice(REEL_TOPICS)
    print(f"Starting pipeline for: {topic['hook']}")

    make_intro_frame(topic, "f1_intro.png")

    frames = ["f1_intro.png"]
    for idx, card in enumerate(topic["cards"], start=1):
        fpath = f"f_{idx}_card.png"
        make_card_frame(card, idx, fpath)
        frames.append(fpath)

    make_cta_frame("f5_cta.png")
    frames.append("f5_cta.png")

    print("Rendering video with FFmpeg...")
    mp4_file = build_reel_mp4(frames, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    caption = (
        f"🔥 {topic['hook']} 🔥\n\n"
        f"{topic['subhook']}\n\n"
        f"Which one are you holding long term? Drop your pick below! 👇\n\n"
        f"📬 Free Weekly Pokémon Market Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse"
    )

    publish_content(video_cdn_url, caption)
