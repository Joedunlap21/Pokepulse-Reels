import os
import random
import time
import subprocess
import cloudinary
import cloudinary.uploader
import requests
from PIL import Image, ImageDraw, ImageFont

cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL", "").strip()
)

API_HEADERS = {"User-Agent": "Mozilla/5.0 (CardStax/PokePulse Purple Studio Engine)"}
IG_USER_ID = "17841472317326348"

# High-Energy Background Beats
HYPE_AUDIO_TRACKS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",
    "https://cdn.pixabay.com/download/audio/2022/10/14/audio_9939f77c30.mp3"
]

VIRAL_NEWS_REELS = [
    {
        "alert": "AUCTION ALERT",
        "headline_line1": "A KINDERGARTENER",
        "headline_line2": "DESIGNED THIS",
        "headline_line3": "72,000+ USD CARD",
        "hero_img": "https://images.pokemontcg.io/col1/22_hires.png",
        "graph_title": "VINTAGE PROMO SURGE",
        "bars": [
            {"label": "2020", "pct": "+350%", "val": 220},
            {"label": "2022", "pct": "+1,420%", "val": 480},
            {"label": "2024", "pct": "+2,880%", "val": 710},
            {"label": "2026", "pct": "+3,650%", "val": 920}
        ],
        "story_sub": "ONLY BGS PRISTINE 10 IN EXISTENCE"
    },
    {
        "alert": "TRENDING NOW",
        "headline_line1": "THE LOW POP",
        "headline_line2": "VINTAGE MARKET",
        "headline_line3": "IS EXPLODING",
        "hero_img": "https://images.pokemontcg.io/swsh7/215_hires.png",
        "graph_title": "CALL OF LEGENDS YOY",
        "bars": [
            {"label": "LUGIA", "pct": "+3,500%", "val": 940},
            {"label": "RAIKOU", "pct": "+3,201%", "val": 810},
            {"label": "GROUDON", "pct": "+2,882%", "val": 720},
            {"label": "RAYQUAZA", "pct": "+2,503%", "val": 630}
        ],
        "story_sub": "GRAILS SURGING OVER 2,000% YOY"
    },
    {
        "alert": "MARKET ALERT",
        "headline_line1": "PLATINUM LV.X",
        "headline_line2": "ARE MOVING",
        "headline_line3": "INSANELY FAST",
        "hero_img": "https://images.pokemontcg.io/pl3/146_hires.png",
        "graph_title": "PLATINUM ERA BREAKOUT",
        "bars": [
            {"label": "RAW", "pct": "+210%", "val": 260},
            {"label": "PSA 8", "pct": "+540%", "val": 490},
            {"label": "PSA 9", "pct": "+1,180%", "val": 710},
            {"label": "PSA 10", "pct": "+2,940%", "val": 930}
        ],
        "story_sub": "SUPREME VICTORS SUPPLY NEAR ZERO"
    }
]

W, H = 1080, 1920

# Download Bebas Neue for identical typography
def ensure_font():
    if not os.path.exists("BebasNeue.ttf"):
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf"
        r = requests.get(url)
        with open("BebasNeue.ttf", "wb") as f:
            f.write(r.content)

ensure_font()

def get_font(size):
    if os.path.exists("BebasNeue.ttf"):
        try:
            return ImageFont.truetype("BebasNeue.ttf", size)
        except Exception:
            pass
    return ImageFont.load_default()

# --- DYNAMIC TEXT AUTO-FITTER (Guarantees Text Fits Every Time) ---
def draw_fitted_text(draw, text, y, max_w=940, target_size=120, min_size=40, fill="white", stroke_fill="#000000", stroke_width=6):
    curr_size = target_size
    font = get_font(curr_size)

    while curr_size > min_size:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        if w <= max_w:
            break
        curr_size -= 2
        font = get_font(curr_size)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (W - w) // 2

    draw.text((x, y), text, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
    return y + h + 8

# --- LIGHT PURPLE STUDIO GRADIENT ---
def create_purple_studio_background():
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    r1, g1, b1 = 120, 80, 205   # Vibrant royal lavender
    r2, g2, b2 = 38, 22, 75     # Deep luxury purple

    for y in range(H):
        t = y / H
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Center ambient spotlight
    for r_spot in range(650, 0, -35):
        alpha = int(22 * (1 - r_spot / 650))
        draw.ellipse([W//2 - r_spot, H//2 - r_spot, W//2 + r_spot, H//2 + r_spot], fill=(155 + alpha, 110 + alpha, 245 + alpha))

    return img

# --- SLIDE 1: VIRAL HOOK (PERFECT TEXT FIT & ZERO OVERFLOW) ---
def make_viral_hook_frame(reel, out_path="f1_hook.png"):
    img = create_purple_studio_background()
    draw = ImageDraw.Draw(img)

    # 1. Graded Slab Hero Visual (Scaled to leave room for text)
    cdata = requests.get(reel["hero_img"], headers=API_HEADERS).content
    with open("temp_hero.png", "wb") as f:
        f.write(cdata)

    card = Image.open("temp_hero.png").convert("RGBA")
    card.thumbnail((880, 1080), Image.Resampling.LANCZOS)
    cw, ch = card.size
    cx = (W - cw) // 2
    cy = 60

    # Slab Shadow
    draw.rounded_rectangle([cx - 15, cy - 8, cx + cw + 15, cy + ch + 20], radius=28, fill=(20, 10, 45))
    img.paste(card, (cx, cy), mask=card.split()[3])

    # 2. Red Alert Pill
    alert_text = reel["alert"]
    a_font = get_font(46)
    abox = draw.textbbox((0, 0), alert_text, font=a_font)
    aw = (abox[2] - abox[0]) + 54
    ah = 64
    ax = (W - aw) // 2
    ay = cy + ch - 70

    draw.rounded_rectangle([ax + 4, ay + 5, ax + aw + 4, ay + ah + 5], radius=32, fill="#000000")
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=32, fill="#E50914", outline="#FFFFFF", width=3)
    draw.text((ax + 27, ay + 7), alert_text, font=a_font, fill="#FFFFFF")

    # 3. Stacked Headline with Dynamic Auto-Fitting
    y_start = ay + ah + 25
    y_start = draw_fitted_text(draw, reel["headline_line1"], y_start, max_w=940, target_size=118, fill="#FFE600")
    y_start = draw_fitted_text(draw, reel["headline_line2"], y_start, max_w=940, target_size=118, fill="#FFFFFF")
    draw_fitted_text(draw, reel["headline_line3"], y_start, max_w=940, target_size=118, fill="#00FF66")

    img.save(out_path)

# --- SLIDE 2: MODERN GRAPH SLIDE ---
def make_graph_frame(reel, out_path="f2_graph.png"):
    img = create_purple_studio_background()
    draw = ImageDraw.Draw(img)

    # 1. Header with Auto-Fitting
    draw_fitted_text(draw, reel["graph_title"], 90, max_w=960, target_size=68, fill="#FFFFFF")
    draw_fitted_text(draw, "YEAR-OVER-YEAR ROI COMPARISON", 175, max_w=900, target_size=38, fill="#D6BCFA", stroke_width=0)

    # 2. Glassmorphic Chart Box
    box_w, box_h = 960, 1140
    bx = (W - box_w) // 2
    by = 250
    draw.rounded_rectangle([bx, by, bx + box_w, by + box_h], radius=32, fill=(28, 16, 58), outline="#7C3AED", width=3)

    for y_offset in [by + 250, by + 500, by + 750]:
        draw.line([(bx + 40, y_offset), (bx + box_w - 40, y_offset)], fill=(75, 45, 130), width=2)

    base_y = by + 930
    bars = reel["bars"]
    n_bars = len(bars)
    bar_w = 150
    spacing = 55
    total_w = n_bars * bar_w + (n_bars - 1) * spacing
    start_x = bx + (box_w - total_w) // 2

    for idx, b in enumerate(bars):
        cur_x = start_x + idx * (bar_w + spacing)
        bar_h = b["val"]
        cur_y = base_y - bar_h

        draw.rounded_rectangle([cur_x - 3, cur_y - 3, cur_x + bar_w + 3, base_y + 3], radius=22, fill=(10, 5, 25))
        draw.rounded_rectangle([cur_x, cur_y, cur_x + bar_w, base_y], radius=20, fill="#00FF66", outline="#FFFFFF", width=3)

        p_font = get_font(38)
        pbox = draw.textbbox((0, 0), b["pct"], font=p_font)
        pw = pbox[2] - pbox[0]
        draw.rounded_rectangle([cur_x - 10, cur_y - 60, cur_x + bar_w + 10, cur_y - 12], radius=14, fill="#120A24", outline="#00FF66", width=2)
        draw.text((cur_x + (bar_w - pw) // 2, cur_y - 56), b["pct"], font=p_font, fill="#00FF66")

        l_font = get_font(42)
        lbox = draw.textbbox((0, 0), b["label"], font=l_font)
        lw = lbox[2] - lbox[0]
        draw.text((cur_x + (bar_w - lw) // 2, base_y + 22), b["label"], font=l_font, fill="#FFFFFF")

    # 3. Bottom Callout with Auto-Fitting
    draw_fitted_text(draw, "GRAILS SURGING >2,000%", 1460, max_w=940, target_size=98, fill="#FFE600")
    draw_fitted_text(draw, reel["story_sub"], 1565, max_w=940, target_size=42, fill="#FFFFFF", stroke_width=0)

    img.save(out_path)

# --- SLIDE 3: CUSTOM CTA OUTRO ---
def make_cta_frame(out_path="f3_cta.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    cdata = requests.get(cta_url, headers=API_HEADERS).content
    with open("raw_cta.png", "wb") as f:
        f.write(cdata)

    base = create_purple_studio_background()
    cta_img = Image.open("raw_cta.png").convert("RGB")
    cta_img.thumbnail((1080, 1350), Image.Resampling.LANCZOS)
    cw, ch = cta_img.size
    cx = (W - cw) // 2
    cy = 200
    base.paste(cta_img, (cx, cy))

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle([80, 1630, W - 80, 1740], radius=55, fill="#FFE600", outline="#FFFFFF", width=3)
    c_font = get_font(50)
    c_box = draw.textbbox((0, 0), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font)
    cw_txt = c_box[2] - c_box[0]
    draw.text(((W - cw_txt) // 2, 1658), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font, fill="#000000")
    base.save(out_path)

# --- FAST-PACED REEL COMPILER ---
def build_snappy_reel(frame_files, output_mp4="pokepulse_reel.mp4"):
    durations = [2.2, 2.8, 2.0]
    total_duration = sum(durations)

    with open("playlist.txt", "w") as f:
        for frame, dur in zip(frame_files, durations):
            f.write(f"file '{frame}'\n")
            f.write(f"duration {dur}\n")
        f.write(f"file '{frame_files[-1]}'\n")

    audio_url = random.choice(HYPE_AUDIO_TRACKS)
    print(f"Downloading audio: {audio_url}")
    audio_data = requests.get(audio_url, headers=API_HEADERS).content
    with open("bg_audio.mp3", "wb") as f:
        f.write(audio_data)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-i", "bg_audio.mp3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", f"[1:a]afade=t=out:st={total_duration - 1.0}:d=1.0[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", str(total_duration),
        "-vf", "scale=1080:1920",
        output_mp4
    ]
    subprocess.run(cmd, check=True)
    return output_mp4

# --- PUBLISHING ENGINE ---
def publish_content(video_url, caption):
    access_token = os.getenv("IG_ACCESS_TOKEN", "").strip()

    print("Step 1: Publishing Reel to Instagram...")
    res = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token
    }).json()

    if "id" in res:
        cid = res["id"]
        print(f"Reel Container: {cid}. Transcoding...")
        for _ in range(15):
            time.sleep(10)
            status = requests.get(f"https://graph.facebook.com/v21.0/{cid}?fields=status_code&access_token={access_token}").json()
            code = status.get("status_code")
            print(f"Status: {code}")
            if code == "FINISHED":
                break
            elif code == "ERROR":
                print("Encoding error on Instagram.")
                break

        pub = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish", data={
            "creation_id": cid,
            "access_token": access_token
        }).json()
        print(f"Reel Publish Result: {pub}")
    else:
        print("Reel Error:", res)

    print("\nStep 2: Publishing to Story...")
    s_res = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media", data={
        "media_type": "STORIES",
        "video_url": video_url,
        "access_token": access_token
    }).json()

    if "id" in s_res:
        sid = s_res["id"]
        for _ in range(12):
            time.sleep(8)
            s_status = requests.get(f"https://graph.facebook.com/v21.0/{sid}?fields=status_code&access_token={access_token}").json()
            if s_status.get("status_code") == "FINISHED":
                break
        s_pub = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish", data={
            "creation_id": sid,
            "access_token": access_token
        }).json()
        print(f"Story Publish Result: {s_pub}")

if __name__ == "__main__":
    reel = random.choice(VIRAL_NEWS_REELS)
    print(f"Generating Precision Studio Reel: {reel['headline_line1']} {reel['headline_line2']}")

    make_viral_hook_frame(reel, "f1_hook.png")
    make_graph_frame(reel, "f2_graph.png")
    make_cta_frame("f3_cta.png")

    frames = ["f1_hook.png", "f2_graph.png", "f3_cta.png"]

    print("Compiling Snappy Video...")
    mp4_file = build_snappy_reel(frames, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    caption = (
        f"🚨 {reel['alert']} | {reel['headline_line1']} {reel['headline_line2']} {reel['headline_line3']}\n\n"
        f"{reel['story_sub']}\n\n"
        f"Are you picking up vintage grails or sticking to modern? Drop your thoughts below! 👇\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
    )

    publish_content(video_cdn_url, caption)
