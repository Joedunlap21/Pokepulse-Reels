import os
import random
import time
import subprocess
import xml.etree.ElementTree as ET
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

# High-Energy Background Beats (Direct CDN)
HYPE_AUDIO_TRACKS = [
    "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3",
    "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3",
    "https://cdn.pixabay.com/download/audio/2022/10/14/audio_9939f77c30.mp3"
]

# Verified Public MP4 Direct Video Assets (Guaranteed raw video stream)
DIRECT_NEWS_VIDEOS = [
    {
        "clip1": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "clip2": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        "tag": "AUCTION RECORD"
    },
    {
        "clip1": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4",
        "clip2": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyBlazes.mp4",
        "tag": "MARKET ALERT"
    }
]

W, H = 1080, 1920

# Download Bebas Neue
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

def draw_tight_text(draw, text, y, font, fill="white", stroke_fill="#000000", stroke_width=6):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (W - w) // 2
    draw.text((x, y), text, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
    return y + h - 6

# --- LIVE POKÉMON NEWS FETCHER ---
def fetch_latest_pokemon_news():
    print("Fetching live Pokémon TCG community news...")
    try:
        feed_url = "https://www.pokebeach.com/feed"
        res = requests.get(feed_url, headers=API_HEADERS, timeout=8)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")

        if items:
            top_item = random.choice(items[:5])
            title = top_item.find("title").text.upper()
            words = title.split()
            mid = len(words) // 2
            line1 = " ".join(words[:mid]) if mid > 0 else "BREAKING UPDATE"
            line2 = " ".join(words[mid:]) if mid > 0 else title
            return {
                "alert": "BREAKING NEWS",
                "line1": line1[:22],
                "line2": line2[:24],
                "line3": "JUST ANNOUNCED!",
                "context": title
            }
    except Exception as e:
        print(f"RSS fetch fallback: {e}")

    defaults = [
        {
            "alert": "AUCTION ALERT",
            "line1": "A KINDERGARTENER",
            "line2": "DESIGNED THIS",
            "line3": "72,000+ USD CARD",
            "context": "2010 Megu Taniguchi Zoroark contest card sells for record high"
        },
        {
            "alert": "MARKET ALERT",
            "line1": "GOLD STAR",
            "line2": "CGC GRAILS",
            "line3": "ENDING TONIGHT!",
            "context": "Latias & Celebi Gold Star Pristine 10s breaking all auction records"
        },
        {
            "alert": "TRENDING NOW",
            "line1": "PLATINUM LV.X",
            "line2": "ARE MOVING",
            "line3": "INSANELY FAST",
            "context": "Supreme Victors and Platinum holos completely drying up on market"
        }
    ]
    return random.choice(defaults)

# --- OVERLAY GENERATOR (TRANSPARENT PNG OVER VIDEO) ---
def create_video_overlay(alert_text, line1, line2, line3, out_path="overlay.png"):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Dark Vignette Gradient on bottom 45% so text pops off video
    for y in range(H - 850, H):
        alpha = int(210 * ((y - (H - 850)) / 850))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    # Red Alert Pill
    a_font = get_font(52)
    abox = draw.textbbox((0, 0), alert_text, font=a_font)
    aw = (abox[2] - abox[0]) + 60
    ah = 68
    ax = (W - aw) // 2
    ay = H - 680

    draw.rounded_rectangle([ax + 3, ay + 4, ax + aw + 3, ay + ah + 4], radius=10, fill=(0, 0, 0, 220))
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=8, fill="#E50914", outline="#FFFFFF", width=3)
    draw.text((ax + 30, ay + 6), alert_text, font=a_font, fill="#FFFFFF")

    # Stacked Bebas Typography
    f_huge = get_font(136)
    y_start = ay + ah + 18
    y_start = draw_tight_text(draw, line1, y_start, f_huge, fill="#FFE600")
    y_start = draw_tight_text(draw, line2, y_start, f_huge, fill="#FFFFFF")
    draw_tight_text(draw, line3, y_start, f_huge, fill="#00FF66")

    img.save(out_path)

# --- CTA OUTRO FRAME ---
def make_cta_slide(out_path="cta_slide.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    cdata = requests.get(cta_url, headers=API_HEADERS).content
    with open("raw_cta.png", "wb") as f:
        f.write(cdata)

    base = Image.new("RGB", (W, H), (30, 18, 58))
    cta_img = Image.open("raw_cta.png").convert("RGB")
    cta_img.thumbnail((1080, 1350), Image.Resampling.LANCZOS)
    cw, ch = cta_img.size
    cx = (W - cw) // 2
    cy = 180
    base.paste(cta_img, (cx, cy))

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle([80, 1620, W - 80, 1730], radius=55, fill="#FFE600", outline="#FFFFFF", width=3)
    c_font = get_font(52)
    c_box = draw.textbbox((0, 0), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font)
    cw_txt = c_box[2] - c_box[0]
    draw.text(((W - cw_txt) // 2, 1644), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font, fill="#000000")
    base.save(out_path)

# --- SAFE VIDEO DOWNLOADER (Validates Real Video File) ---
def download_safe_video(url, dest_file):
    res = requests.get(url, headers=API_HEADERS, timeout=20)
    with open(dest_file, "wb") as f:
        f.write(res.content)
    # Check if file has valid size (> 50KB)
    if os.path.getsize(dest_file) < 50000:
        raise ValueError(f"Downloaded file {dest_file} is too small, likely blocked.")

# --- FFMPEG COMPOSITOR ---
def compile_news_reel(news, video_pkg, output_mp4="pokepulse_reel.mp4"):
    print("Downloading news video B-roll clips...")
    download_safe_video(video_pkg["clip1"], "clip1.mp4")
    download_safe_video(video_pkg["clip2"], "clip2.mp4")

    audio_url = random.choice(HYPE_AUDIO_TRACKS)
    print(f"Downloading audio track: {audio_url}")
    audio_data = requests.get(audio_url, headers=API_HEADERS).content
    with open("bg_audio.mp3", "wb") as f:
        f.write(audio_data)

    create_video_overlay(news["alert"], news["line1"], news["line2"], news["line3"], "overlay1.png")
    create_video_overlay("MARKET WATCH", "VERIFIED SALES", "BREAKING OUT", "CHECK BIO!", "overlay2.png")
    make_cta_slide("cta_slide.png")

    # Render Scene 1 with Overlay (3.0s)
    subprocess.run([
        "ffmpeg", "-y", "-t", "3.0", "-i", "clip1.mp4", "-i", "overlay1.png",
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v0];[v0][1:v]overlay=0:0[out]",
        "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "scene1.mp4"
    ], check=True)

    # Render Scene 2 with Overlay (3.0s)
    subprocess.run([
        "ffmpeg", "-y", "-t", "3.0", "-i", "clip2.mp4", "-i", "overlay2.png",
        "-filter_complex", "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v0];[v0][1:v]overlay=0:0[out]",
        "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "scene2.mp4"
    ], check=True)

    # Render Scene 3 CTA (2.0s)
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-t", "2.0", "-i", "cta_slide.png",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "scene3.mp4"
    ], check=True)

    # Concat scenes + mux high-energy beat (Total 8.0s)
    with open("concat_list.txt", "w") as f:
        f.write("file 'scene1.mp4'\n")
        f.write("file 'scene2.mp4'\n")
        f.write("file 'scene3.mp4'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt",
        "-i", "bg_audio.mp3",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", "[1:a]afade=t=out:st=6.8:d=1.2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", "8.0",
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
    news = fetch_latest_pokemon_news()
    video_pkg = random.choice(DIRECT_NEWS_VIDEOS)

    print(f"Producing Video News Reel: {news['line1']} {news['line2']}")
    mp4_file = compile_news_reel(news, video_pkg, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    caption = (
        f"🚨 {news['alert']} | {news['line1']} {news['line2']} {news['line3']}\n\n"
        f"Full Scoop: {news['context']}\n\n"
        f"What are your thoughts on this latest update? Drop your comments below! 👇\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
    )

    publish_content(video_cdn_url, caption)
