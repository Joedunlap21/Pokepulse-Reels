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

API_HEADERS = {"User-Agent": "Mozilla/5.0 (CardStax/PokePulse Agency Engine)"}
IG_USER_ID = "17841472317326348"

# High-Energy Background Beats
HYPE_AUDIO_TRACKS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",
    "https://cdn.pixabay.com/download/audio/2022/10/14/audio_9939f77c30.mp3"
]

# Curated High-Stakes Viral Stories & Market News (Matching Reference Graphics)
VIRAL_NEWS_REELS = [
    {
        "alert": "AUCTION ALERT",
        "headline_line1": "A KINDERGARTENER",
        "headline_line2": "DESIGNED THIS",
        "headline_line3": "72,000+ USD CARD.",
        "colors": ["#FFE600", "#FFFFFF", "#00FF66"],
        "hero_img": "https://images.pokemontcg.io/col1/22_hires.png",
        "graph_title": "VINTAGE PROMO EXPLOSION",
        "bars": [
            {"label": "2018", "pct": "+350%", "h": 220},
            {"label": "2021", "pct": "+1,420%", "h": 460},
            {"label": "2024", "pct": "+2,880%", "h": 680},
            {"label": "2026", "pct": "+3,650%", "h": 850}
        ],
        "story_sub": "THE ONLY BGS PRISTINE 10 FROM ENTIRE CONTEST"
    },
    {
        "alert": "TRENDING",
        "headline_line1": "THE LOW POP",
        "headline_line2": "VINTAGE MARKET",
        "headline_line3": "IS SURGING.",
        "colors": ["#FFE600", "#FFFFFF", "#00FF66"],
        "hero_img": "https://images.pokemontcg.io/swsh7/215_hires.png",
        "graph_title": "CALL OF LEGENDS YOY PRICING",
        "bars": [
            {"label": "LUGIA", "pct": "+3,500%", "h": 850},
            {"label": "RAIKOU", "pct": "+3,201%", "h": 780},
            {"label": "GROUDON", "pct": "+2,882%", "h": 700},
            {"label": "RAYQUAZA", "pct": "+2,503%", "h": 610}
        ],
        "story_sub": "GRAILS ARE OFFICIALLY UP OVER 2,000% YOY"
    },
    {
        "alert": "AUCTION ALERT",
        "headline_line1": "LV.X GRAILS",
        "headline_line2": "ARE MOVING",
        "headline_line3": "RIDICULOUSLY FAST.",
        "colors": ["#00FF66", "#FFFFFF", "#FFE600"],
        "hero_img": "https://images.pokemontcg.io/pl3/146_hires.png",
        "graph_title": "PLATINUM ERA MARKET BREAKOUT",
        "bars": [
            {"label": "RAW", "pct": "+210%", "h": 320},
            {"label": "PSA 8", "pct": "+540%", "h": 490},
            {"label": "PSA 9", "pct": "+1,180%", "h": 680},
            {"label": "PSA 10", "pct": "+2,940%", "h": 860}
        ],
        "story_sub": "SUPREME VICTORS & PLATINUM SUPPLY DRIES UP"
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

def draw_tight_text(draw, text, y, font, fill="white"):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = (W - w) // 2
    draw.text((x, y), text, font=font, fill=fill)
    return y + (bbox[3] - bbox[1])

# --- SLIDE 1: THE EXACT VIRAL HOOK (Matching Reference Images 1, 2, 4, 6) ---
def make_viral_hook_frame(reel, out_path="f1_hook.png"):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Top 55%: Massive Macro Graded Slab Hero Visual
    top_h = 1040
    cdata = requests.get(reel["hero_img"], headers=API_HEADERS).content
    with open("temp_slab.png", "wb") as f:
        f.write(cdata)

    card = Image.open("temp_slab.png").convert("RGB")
    # Crop and zoom into the foil/art
    card_w, card_h = card.size
    crop_box = (0, 0, card_w, int(card_h * 0.95))
    cropped = card.crop(crop_box).resize((W, top_h), Image.Resampling.LANCZOS)
    img.paste(cropped, (0, 0))

    # Dark gradient fade over bottom of image into pitch black
    for y in range(top_h - 180, top_h):
        alpha = int(255 * ((y - (top_h - 180)) / 180))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    # 2. Red Alert Pill Badge in Center
    alert_text = reel["alert"]
    a_font = get_font(52)
    abox = draw.textbbox((0, 0), alert_text, font=a_font)
    aw = (abox[2] - abox[0]) + 50
    ah = 68
    ax = (W - aw) // 2
    ay = top_h - 34

    draw.rounded_rectangle([ax + 3, ay + 4, ax + aw + 3, ay + ah + 4], radius=6, fill="#000000")
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=6, fill="#E50914")
    draw.text((ax + 25, ay + 6), alert_text, font=a_font, fill="#FFFFFF")

    # 3. Bottom 45% (Pure Pitch Black): Huge Stacked Condensed Typography
    f_huge = get_font(148)
    y_start = top_h + 65

    # Line 1 (e.g. Yellow)
    y_start = draw_tight_text(draw, reel["headline_line1"], y_start, f_huge, fill=reel["colors"][0]) + 5
    # Line 2 (Crisp White)
    y_start = draw_tight_text(draw, reel["headline_line2"], y_start, f_huge, fill=reel["colors"][1]) + 5
    # Line 3 (Neon Green)
    y_start = draw_tight_text(draw, reel["headline_line3"], y_start, f_huge, fill=reel["colors"][2]) + 10

    img.save(out_path)

# --- SLIDE 2: THE NEON BAR GRAPH SLIDE (Matching Reference Image 5) ---
def make_graph_frame(reel, out_path="f2_graph.png"):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Header Box
    h_font = get_font(72)
    sub_font = get_font(48)
    draw_tight_text(draw, reel["graph_title"], 90, h_font, fill="#FFFFFF")
    draw_tight_text(draw, "YEAR-OVER-YEAR ROI COMPARISON", 175, sub_font, fill="#A0AEC0")

    # Graph Area
    graph_base_y = 1100
    bars = reel["bars"]
    num_bars = len(bars)
    bar_w = 160
    total_w = num_bars * bar_w + (num_bars - 1) * 60
    start_x = (W - total_w) // 2

    for idx, b in enumerate(bars):
        bx = start_x + idx * (bar_w + 60)
        by = graph_base_y - b["h"]
        
        # Green Neon Bar
        draw.rounded_rectangle([bx, by, bx + bar_w, graph_base_y], radius=8, fill="#00FF66", outline="#FFFFFF", width=2)

        # Percentage text above bar
        p_font = get_font(42)
        pbox = draw.textbbox((0, 0), b["pct"], font=p_font)
        pw = pbox[2] - pbox[0]
        draw.text((bx + (bar_w - pw) // 2, by - 55), b["pct"], font=p_font, fill="#00FF66")

        # Label under bar
        l_font = get_font(44)
        lbox = draw.textbbox((0, 0), b["label"], font=l_font)
        lw = lbox[2] - lbox[0]
        draw.text((bx + (bar_w - lw) // 2, graph_base_y + 20), b["label"], font=l_font, fill="#FFFFFF")

    # Bottom Callout / Viral Punchline
    f_huge = get_font(128)
    draw_tight_text(draw, "PRICE SURGE", 1240, f_huge, fill="#00E5FF")
    draw_tight_text(draw, "GRAILS ARE UP", 1365, f_huge, fill="#FFE600")
    draw_tight_text(draw, ">2,000% YOY", 1490, f_huge, fill="#00FF66")

    # Sub-footer
    b_font = get_font(38)
    draw_tight_text(draw, reel["story_sub"], 1670, b_font, fill="#A0AEC0")
    img.save(out_path)

# --- SLIDE 3: CUSTOM CTA OUTRO (Exact Newsletter Graphic) ---
def make_cta_frame(out_path="f3_cta.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    cdata = requests.get(cta_url, headers=API_HEADERS).content
    with open("raw_cta.png", "wb") as f:
        f.write(cdata)

    base = Image.new("RGB", (W, H), (0, 0, 0))
    cta_img = Image.open("raw_cta.png").convert("RGB")
    cta_img.thumbnail((1080, 1350), Image.Resampling.LANCZOS)
    cw, ch = cta_img.size
    cx = (W - cw) // 2
    cy = 220
    base.paste(cta_img, (cx, cy))

    draw = ImageDraw.Draw(base)
    c_font = get_font(52)
    draw_tight_text(draw, "TAP LINK IN BIO TO SUBSCRIBE FREE", 1680, c_font, fill="#FFE600")
    base.save(out_path)

# --- COMPILING HIGH-PACED 9:16 REEL WITH AUDIO ---
def build_reel_mp4(frame_files, output_mp4="pokepulse_reel.mp4"):
    # 4.5s hook, 5.0s graph breakdown, 3.5s CTA = 13.0s total
    durations = [4.5, 5.0, 3.5]
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
    print(f"Generating Viral News Reel: {reel['headline_line1']} {reel['headline_line2']}")

    # 1. The Viral Hook Slide (Top Graded Slab + Red Alert + Huge Stacked Neon Text)
    make_viral_hook_frame(reel, "f1_hook.png")

    # 2. The Growth Graph Slide (Neon Green Bars + Big Percentage Stats)
    make_graph_frame(reel, "f2_graph.png")

    # 3. Custom Newsletter CTA Outro
    make_cta_frame("f3_cta.png")

    frames = ["f1_hook.png", "f2_graph.png", "f3_cta.png"]

    print("Rendering Studio 9:16 Video with FFmpeg...")
    mp4_file = build_reel_mp4(frames, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    caption = (
        f"🚨 {reel['alert']} | {reel['headline_line1']} {reel['headline_line2']} {reel['headline_line3']}\n\n"
        f"{reel['story_sub']}\n\n"
        f"Are you buying vintage or sticking with modern? Drop your thoughts below! 👇\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #VintagePokemon"
    )

    publish_content(video_cdn_url, caption)
