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

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
IG_USER_ID = "17841472317326348"

# High-Energy News & Collector Audio Beats (Direct MP3 CDN streams)
REAL_NEWS_AUDIO_TRACKS = [
    "https://actions.google.com/sounds/v1/sports/cheering_crowd.ogg",
    "https://actions.google.com/sounds/v1/science_fiction/force_field_hum.ogg",
    "https://raw.githubusercontent.com/rafaelreis-hotmart/Audio-Sample-files/master/sample.mp3"
]

# EXACT VIRAL STORIES FROM REFERENCE IMAGES
VIRAL_NEWS_PIECES = [
    {
        "story_id": "platinum_lvx",
        "alert": "AUCTION ALERT",
        "scene1": {
            "tag": "AUCTION ALERT",
            "img_url": "https://images.pokemontcg.io/pl3/146_hires.png",
            "zoom_type": "macro_slab",
            "line1": "LV.X",
            "line1_color": "#00FF66",
            "line2": "IS MOVING FAST.",
            "line2_color": "#FFFFFF",
            "line3": "",
            "line3_color": ""
        },
        "scene2": {
            "tag": "MARKET ALERT",
            "img_url": "https://images.pokemontcg.io/dp7/103_hires.png",
            "zoom_type": "macro_foil",
            "line1": "SUPREME VICTORS",
            "line1_color": "#FFE600",
            "line2": "PSA 10 SUPPLY",
            "line2_color": "#FFFFFF",
            "line3": "DRIED UP COMPLETELY",
            "line3_color": "#00FF66"
        },
        "caption_sub": "Supreme Victors and DP Platinum era Lv.X holos are facing intense buyouts across auction houses."
    },
    {
        "story_id": "zoroark_kindergarten",
        "alert": "AUCTION ALERT",
        "scene1": {
            "tag": "AUCTION ALERT",
            "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
            "zoom_type": "macro_art",
            "line1": "A KINDERGARTENER",
            "line1_color": "#FFE600",
            "line2": "DESIGNED THIS",
            "line2_color": "#FFFFFF",
            "line3": "$72,000+ CARD",
            "line3_color": "#00FF66"
        },
        "scene2": {
            "tag": "HISTORIC PROOF",
            "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
            "zoom_type": "macro_slab",
            "line1": "THE ONLY",
            "line1_color": "#FFFFFF",
            "line2": "BGS PRISTINE 10",
            "line2_color": "#FFE600",
            "line3": "FROM ENTIRE CONTEST",
            "line3_color": "#00FF66"
        },
        "caption_sub": "2010 Ruler of Illusion Zoroark Design Contest winner Megu Taniguchi's Zorua card just shattered all sales records at 72K USD!"
    },
    {
        "story_id": "call_of_legends",
        "alert": "TRENDING",
        "scene1": {
            "tag": "TRENDING",
            "img_url": "https://images.pokemontcg.io/swsh7/215_hires.png",
            "zoom_type": "macro_slab",
            "line1": "THE LOW POP",
            "line1_color": "#FFE600",
            "line2": "VINTAGE MARKET",
            "line2_color": "#FFFFFF",
            "line3": "IS SURGING.",
            "line3_color": "#00FF66"
        },
        "scene2": {
            "tag": "PRICE SQUEEZE",
            "img_url": "https://images.pokemontcg.io/ex8/105_hires.png",
            "zoom_type": "macro_foil",
            "line1": "EX ERA GRAILS",
            "line1_color": "#FFE600",
            "line2": "BREAKING ALL-TIME",
            "line2_color": "#FFFFFF",
            "line3": "AUCTION CEILINGS",
            "line3_color": "#00FF66"
        },
        "caption_sub": "Call of Legends and Gold Star grails are seeing explosive auction volume increases year-over-year."
    }
]

W, H = 1080, 1920

def ensure_font():
    if not os.path.exists("BebasNeue.ttf"):
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf"
        r = requests.get(url, headers=API_HEADERS)
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

def draw_tight_text(draw, text, y, font, fill="white", stroke_fill="#000000", stroke_width=8):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (W - w) // 2
    draw.text((x, y), text, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
    return y + h - 8

# --- BUILD EXACT FULL-BLEED CARD LADDER LAYOUT ---
def render_fullbleed_news_slide(scene, out_path):
    img = Image.new("RGB", (W, H), (10, 10, 12))
    draw = ImageDraw.Draw(img)

    # 1. Download & Process the High-Res News Image
    pdata = requests.get(scene["img_url"], headers=API_HEADERS).content
    with open("temp_raw.png", "wb") as f:
        f.write(pdata)
    raw_img = Image.open("temp_raw.png").convert("RGB")

    # Full-Bleed Scaling: Card fills 75-80% of upper canvas (from y=0 down to y=1180)
    photo_box_h = 1180
    if scene["zoom_type"] == "macro_art":
        # Crop specifically into the card artwork box (like img_18)
        iw, ih = raw_img.size
        crop_box = (int(iw * 0.08), int(ih * 0.12), int(iw * 0.92), int(ih * 0.65))
        raw_img = raw_img.crop(crop_box)
        raw_img = raw_img.resize((W, photo_box_h), Image.Resampling.LANCZOS)
        img.paste(raw_img, (0, 0))
    else:
        # Full macro slab taking up the top (like img_17, img_19, img_20)
        raw_img.thumbnail((1000, 1140), Image.Resampling.LANCZOS)
        rw, rh = raw_img.size
        rx = (W - rw) // 2
        ry = 30
        img.paste(raw_img, (rx, ry))

    # Dark Vignette Gradient Transition under the image
    for y in range(960, 1240):
        t = (y - 960) / 280
        alpha = int(255 * t)
        draw.line([(0, y), (W, y)], fill=(10, 10, 12, alpha))

    # 2. Red Alert Pill Badge (Exact proportions from img_17 - img_20)
    tag_text = scene["tag"]
    a_font = get_font(52)
    abox = draw.textbbox((0, 0), tag_text, font=a_font)
    aw = (abox[2] - abox[0]) + 56
    ah = 68
    ax = (W - aw) // 2
    ay = 1140

    draw.rounded_rectangle([ax + 3, ay + 4, ax + aw + 3, ay + ah + 4], radius=6, fill="#000000")
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=4, fill="#E50914")
    draw.text((ax + 28, ay + 6), tag_text, font=a_font, fill="#FFFFFF")

    # 3. Stacked Massive Condensed Bebas Typography (Exact Colors & Sizing)
    # If only 2 lines, bump to 175px (like 'LV.X IS MOVING FAST')
    has_3 = bool(scene["line3"])
    f_size = 142 if has_3 else 178
    f_huge = get_font(f_size)

    y_start = ay + ah + 16
    y_start = draw_tight_text(draw, scene["line1"], y_start, f_huge, fill=scene["line1_color"])
    y_start = draw_tight_text(draw, scene["line2"], y_start, f_huge, fill=scene["line2_color"])
    if has_3:
        draw_tight_text(draw, scene["line3"], y_start, f_huge, fill=scene["line3_color"])

    img.save(out_path)

# --- NEWSLETTER CTA OUTRO ---
def make_cta_slide(out_path="f3_cta.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    cdata = requests.get(cta_url, headers=API_HEADERS).content
    with open("raw_cta.png", "wb") as f:
        f.write(cdata)

    base = Image.new("RGB", (W, H), (10, 10, 12))
    cta_img = Image.open("raw_cta.png").convert("RGB")
    cta_img.thumbnail((1080, 1350), Image.Resampling.LANCZOS)
    cw, ch = cta_img.size
    cx = (W - cw) // 2
    cy = 160
    base.paste(cta_img, (cx, cy))

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle([80, 1620, W - 80, 1730], radius=55, fill="#FFE600", outline="#FFFFFF", width=3)
    c_font = get_font(52)
    c_box = draw.textbbox((0, 0), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font)
    cw_txt = c_box[2] - c_box[0]
    draw.text(((W - cw_txt) // 2, 1644), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font, fill="#000000")
    base.save(out_path)

# --- FFMPEG VIDEO COMPILER: FULL-BLEED SLIDES + BROADCAST AUDIO ---
def compile_news_reel(story, output_mp4="pokepulse_reel.mp4"):
    print("Building Scene 1 (Full-Bleed Cover Hook)...")
    render_fullbleed_news_slide(story["scene1"], "f1_cover.png")

    print("Building Scene 2 (Full-Bleed News Proof)...")
    render_fullbleed_news_slide(story["scene2"], "f2_proof.png")

    print("Building Scene 3 (Newsletter Outro)...")
    make_cta_slide("f3_cta.png")

    # 2.8s hook + 2.8s proof + 2.0s CTA = 7.6s Snappy High-Retention Loop
    scene_files = [
        ("f1_cover.png", "s1.mp4", "2.8"),
        ("f2_proof.png", "s2.mp4", "2.8"),
        ("f3_cta.png", "s3.mp4", "2.0")
    ]

    for img_in, vid_out, dur in scene_files:
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", dur, "-i", img_in,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", vid_out
        ], check=True)

    with open("playlist.txt", "w") as f:
        for _, vid_out, _ in scene_files:
            f.write(f"file '{vid_out}'\n")

    # Download Broadcast-Grade News Beat
    audio_file = "bg_audio.mp3"
    audio_success = False
    for track_url in REAL_NEWS_AUDIO_TRACKS:
        try:
            r = requests.get(track_url, headers=API_HEADERS, timeout=8)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(audio_file, "wb") as f:
                    f.write(r.content)
                audio_success = True
                break
        except Exception:
            continue

    if not audio_success:
        # High-energy 808 sub-bass broadcast pulse
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=130:duration=7.6",
            "-c:a", "libmp3lame", "-b:a", "192k", audio_file
        ], check=True)

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-i", audio_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", "[1:a]afade=t=out:st=6.4:d=1.2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", "7.6",
        output_mp4
    ], check=True)

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
    story = random.choice(VIRAL_NEWS_PIECES)
    print(f"Producing Card Ladder Style News Reel: {story['scene1']['line1']} {story['scene1']['line2']}")

    mp4_file = compile_news_reel(story, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    caption = (
        f"🚨 {story['alert']} | {story['scene1']['line1']} {story['scene1']['line2']} {story['scene1']['line3']}\n\n"
        f"{story['caption_sub']}\n\n"
        f"What are your thoughts on this auction record? Drop your comments below! 👇\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
    )

    publish_content(video_cdn_url, caption)
