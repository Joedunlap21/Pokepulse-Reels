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
    cloudinary_url=os.getenv("CLOUDINARY_URL")
)

API_HEADERS = {"User-Agent": "Mozilla/5.0 (CardStax/PokePulse Reels Agent)"}

# High-Energy Royalty-Free Audio Tracks (Hype Trap / Upbeat Synth)
HYPE_AUDIO_TRACKS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",  # Upbeat Action Trap Beat
    "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",  # Energetic Electronic Hype
    "https://cdn.pixabay.com/download/audio/2022/10/14/audio_9939f77c30.mp3"   # Modern Hip Hop / Trap Beat
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

def make_intro_frame(topic, out_path="frame_intro.png"):
    img = Image.new("RGB", (W, H), (10, 12, 16))
    draw = ImageDraw.Draw(img)

    # Red Pill Hook
    pill_w, pill_h = 480, 70
    pill_x1 = (W - pill_w) // 2
    draw.rounded_rectangle([pill_x1, 280, pill_x1 + pill_w, 280 + pill_h], radius=35, fill="#E50914")
    draw_autofit_text(draw, "MARKET WATCH 2026", (pill_x1, 280, pill_x1 + pill_w, 280 + pill_h), max_font_size=34, min_font_size=22, fill="#FFFFFF", bold=True)

    # Big Hook Headline
    draw_autofit_text(draw, topic["hook"], (60, 420, W - 60, 680), max_font_size=88, min_font_size=40, fill="#FFE600", bold=True)
    draw_autofit_text(draw, topic["subhook"], (60, 720, W - 60, 820), max_font_size=42, min_font_size=24, fill="#00FF66", bold=True)

    # Branding
    draw_autofit_text(draw, "@CARD.STAX", (60, 1600, W - 60, 1680), max_font_size=48, min_font_size=28, fill="#A0AEC0", bold=True)
    img.save(out_path)

def make_card_frame(card_data, rank, out_path):
    img = Image.new("RGB", (W, H), (10, 12, 16))
    draw = ImageDraw.Draw(img)

    # Top Alert
    pill_w, pill_h = 360, 64
    pill_x1 = (W - pill_w) // 2
    draw.rounded_rectangle([pill_x1, 140, pill_x1 + pill_w, 140 + pill_h], radius=32, fill="#E50914")
    draw_autofit_text(draw, f"TOP HIT #{rank}", (pill_x1, 140, pill_x1 + pill_w, 140 + pill_h), max_font_size=32, min_font_size=22, fill="#FFFFFF", bold=True)

    # Card Name
    draw_autofit_text(draw, card_data["name"], (60, 230, W - 60, 340), max_font_size=68, min_font_size=36, fill="#FFE600", bold=True)

    # Card Visual
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

    # Price Box
    box_w, box_h = 800, 180
    bx1 = (W - box_w) // 2
    by1 = 1420
    draw.rounded_rectangle([bx1, by1, bx1 + box_w, by1 + box_h], radius=24, fill="#161B22", outline="#00FF66", width=4)
    draw_autofit_text(draw, f"VERIFIED MARKET FLOOR: {card_data['price']}", (bx1 + 20, by1 + 20, bx1 + box_w - 20, by1 + 100), max_font_size=42, min_font_size=24, fill="#FFFFFF", bold=True)
    draw_autofit_text(draw, f"SET: {card_data['set'].upper()}", (bx1 + 20, by1 + 105, bx1 + box_w - 20, by1 + 160), max_font_size=32, min_font_size=20, fill="#A0AEC0", bold=True)

    # Footer
    draw_autofit_text(draw, "@CARD.STAX", (60, 1720, W - 60, 1800), max_font_size=44, min_font_size=26, fill="#A0AEC0", bold=True)
    img.save(out_path)

def make_cta_frame(out_path="frame_cta.png"):
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

# --- VIDEO RENDERING VIA FFMPEG WITH AUDIO MUXING ---
def build_reel_mp4(frame_files, output_mp4="pokepulse_reel.mp4"):
    durations = [2.5, 3.0, 3.0, 3.0, 3.0]  # Total = 14.5 seconds
    total_duration = sum(durations)

    with open("playlist.txt", "w") as f:
        for frame, dur in zip(frame_files, durations):
            f.write(f"file '{frame}'\n")
            f.write(f"duration {dur}\n")
        f.write(f"file '{frame_files[-1]}'\n")

    # Download a random hype audio track
    audio_url = random.choice(HYPE_AUDIO_TRACKS)
    print(f"Downloading high-energy audio track: {audio_url}")
    audio_data = requests.get(audio_url, headers=API_HEADERS).content
    with open("bg_audio.mp3", "wb") as f:
        f.write(audio_data)

    # Concat frames + mux audio, trim audio to exact video length, add 1.5s audio fadeout
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
# --- INSTAGRAM REELS & STORY PUBLISHING ---
def publish_to_reels_and_story(video_url, caption):
    # .strip() guarantees no accidental hidden spaces or newlines break the request
    ig_user_id = os.getenv("IG_USER_ID", "").strip()
    access_token = os.getenv("IG_ACCESS_TOKEN", "").strip()

    if not ig_user_id or not access_token:
        print("Missing IG_USER_ID or IG_ACCESS_TOKEN.")
        return

    # 1. PUBLISH TO REELS
    print("Step 1: Initializing Reels container with audio...")
    res = requests.post(f"https://graph.facebook.com/v21.0/{ig_user_id}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token
    }).json()

    if "id" in res:
        container_id = res["id"]
        print(f"Reel Container ID: {container_id}. Waiting for processing...")
        for _ in range(15):
            time.sleep(10)
            status = requests.get(f"https://graph.facebook.com/v21.0/{container_id}?fields=status_code&access_token={access_token}").json()
            print(f"Processing status: {status.get('status_code')}")
            if status.get("status_code") == "FINISHED":
                break
            elif status.get("status_code") == "ERROR":
                print("Video encoding failed on Instagram's end.")
                break

        pub = requests.post(f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish", data={
            "creation_id": container_id,
            "access_token": access_token
        }).json()
        if "id" in pub:
            print(f"Success! Reel is LIVE on @card.stax: {pub['id']}")
        else:
            print("Publishing Reel error:", pub)
    else:
        print("Error initializing Reel:", res)

    # 2. ALSO PUBLISH TO STORY (so you can save it to Highlights!)
    print("\nStep 2: Publishing to Instagram Story...")
    story_res = requests.post(f"https://graph.facebook.com/v21.0/{ig_user_id}/media", data={
        "media_type": "STORIES",
        "video_url": video_url,
        "access_token": access_token
    }).json()

    if "id" in story_res:
        story_container_id = story_res["id"]
        print(f"Story Container ID: {story_container_id}. Waiting for processing...")
        for _ in range(12):
            time.sleep(8)
            s_status = requests.get(f"https://graph.facebook.com/v21.0/{story_container_id}?fields=status_code&access_token={access_token}").json()
            if s_status.get("status_code") == "FINISHED":
                break

        story_pub = requests.post(f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish", data={
            "creation_id": story_container_id,
            "access_token": access_token
        }).json()
        if "id" in story_pub:
            print(f"Success! Story is LIVE on @card.stax: {story_pub['id']}")
            print("You can now tap 'Highlight' in the Instagram app to pin it to your profile!")
        else:
            print("Publishing Story error:", story_pub)
    else:
        print("Error initializing Story:", story_res)
            publish_to_reels_and_story(video_cdn_url, caption)
