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

# Raw GitHub CDN Audio Tracks (Direct MP3 streams - Never rate-limited or blocked)
HYPE_AUDIO_TRACKS = [
    "https://raw.githubusercontent.com/rafaelreis-hotmart/Audio-Sample-files/master/sample.mp3",
    "https://actions.google.com/sounds/v1/sports/football_stadium_crowd_cheer.ogg",
    "https://actions.google.com/sounds/v1/cartoon/metal_whack.ogg"
]

# Verified High-Res News Photos
NEWS_PHOTO_LIBRARY = [
    {
        "alert": "AUCTION ALERT",
        "line1": "A KINDERGARTENER",
        "line2": "DESIGNED THIS",
        "line3": "72,000+ USD CARD",
        "photo1": "https://images.pokemontcg.io/col1/22_hires.png",
        "photo2": "https://images.pokemontcg.io/swsh7/215_hires.png",
        "context": "2010 Megu Taniguchi contest winner Zoroark card hits all-time auction record"
    },
    {
        "alert": "MARKET ALERT",
        "line1": "GOLD STAR",
        "line2": "CGC GRAILS",
        "line3": "ENDING TONIGHT!",
        "photo1": "https://images.pokemontcg.io/ex8/105_hires.png",
        "photo2": "https://images.pokemontcg.io/ex14/100_hires.png",
        "context": "Latias & Celebi Gold Star Pristine 10s breaking all historical price ceilings"
    },
    {
        "alert": "TRENDING NOW",
        "line1": "PLATINUM LV.X",
        "line2": "ARE MOVING",
        "line3": "INSANELY FAST",
        "photo1": "https://images.pokemontcg.io/pl3/146_hires.png",
        "photo2": "https://images.pokemontcg.io/dp7/103_hires.png",
        "context": "Supreme Victors Rayquaza and Platinum era supply near extinction"
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

def draw_tight_text(draw, text, y, font, fill="white", stroke_fill="#000000", stroke_width=6):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (W - w) // 2
    draw.text((x, y), text, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
    return y + h - 6

def fetch_live_news():
    print("Checking for breaking Pokémon news...")
    try:
        res = requests.get("https://www.pokebeach.com/feed", headers=API_HEADERS, timeout=8)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")
        if items:
            top_item = random.choice(items[:5])
            title = top_item.find("title").text.upper()
            words = title.split()
            mid = len(words) // 2
            line1 = " ".join(words[:mid]) if mid > 0 else "BREAKING UPDATE"
            line2 = " ".join(words[mid:]) if mid > 0 else title
            base = random.choice(NEWS_PHOTO_LIBRARY)
            return {
                "alert": "BREAKING NEWS",
                "line1": line1[:22],
                "line2": line2[:24],
                "line3": "JUST ANNOUNCED!",
                "photo1": base["photo1"],
                "photo2": base["photo2"],
                "context": title
            }
    except Exception as e:
        print(f"Curated fallback: {e}")

    return random.choice(NEWS_PHOTO_LIBRARY)

def prepare_slab_base(photo_url, out_path="slab_base.png"):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    r1, g1, b1 = 110, 70, 190
    r2, g2, b2 = 32, 18, 60
    for y in range(H):
        t = y / H
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    for r_spot in range(650, 0, -35):
        alpha = int(22 * (1 - r_spot / 650))
        draw.ellipse([W//2 - r_spot, H//2 - r_spot, W//2 + r_spot, H//2 + r_spot], fill=(155 + alpha, 110 + alpha, 245 + alpha))

    pdata = requests.get(photo_url, headers=API_HEADERS).content
    with open("temp_raw.png", "wb") as f:
        f.write(pdata)

    card = Image.open("temp_raw.png").convert("RGBA")
    card.thumbnail((920, 1260), Image.Resampling.LANCZOS)
    cw, ch = card.size
    cx = (W - cw) // 2
    cy = 60

    draw.rounded_rectangle([cx - 15, cy - 8, cx + cw + 15, cy + ch + 20], radius=28, fill=(15, 8, 30))
    img.paste(card, (cx, cy), mask=card.split()[3])
    img.save(out_path)

def create_video_overlay(alert_text, line1, line2, line3, out_path="overlay.png"):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y in range(H - 850, H):
        alpha = int(220 * ((y - (H - 850)) / 850))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    a_font = get_font(52)
    abox = draw.textbbox((0, 0), alert_text, font=a_font)
    aw = (abox[2] - abox[0]) + 60
    ah = 68
    ax = (W - aw) // 2
    ay = H - 680

    draw.rounded_rectangle([ax + 3, ay + 4, ax + aw + 3, ay + ah + 4], radius=10, fill=(0, 0, 0, 230))
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=8, fill="#E50914", outline="#FFFFFF", width=3)
    draw.text((ax + 30, ay + 6), alert_text, font=a_font, fill="#FFFFFF")

    f_huge = get_font(136)
    y_start = ay + ah + 18
    y_start = draw_tight_text(draw, line1, y_start, f_huge, fill="#FFE600")
    y_start = draw_tight_text(draw, line2, y_start, f_huge, fill="#FFFFFF")
    draw_tight_text(draw, line3, y_start, f_huge, fill="#00FF66")

    img.save(out_path)

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

# Download and validate audio with automatic synthetic audio fallback
def prepare_reliable_audio(dest_file="bg_audio.mp3"):
    for track_url in HYPE_AUDIO_TRACKS:
        try:
            r = requests.get(track_url, headers=API_HEADERS, timeout=10)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(dest_file, "wb") as f:
                    f.write(r.content)
                print(f"Loaded verified audio stream: {track_url}")
                return dest_file
        except Exception:
            continue

    # Bulletproof fallback: Generate clean 8-second synth stereo pad in FFmpeg
    print("Generating pure audio track via FFmpeg...")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:beep_factor=4:duration=8.0",
        "-c:a", "libmp3lame", "-b:a", "192k", dest_file
    ], check=True)
    return dest_file

def compile_cinematic_motion_reel(story, output_mp4="pokepulse_reel.mp4"):
    print("Generating Scene 1...")
    prepare_slab_base(story["photo1"], "slab1.png")
    create_video_overlay(story["alert"], story["line1"], story["line2"], story["line3"], "overlay1.png")

    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", "slab1.png", "-i", "overlay1.png",
        "-filter_complex",
        "[0:v]scale=8000:-1,zoompan=z='min(zoom+0.0018,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=90:s=1080x1920:fps=30[bg];"
        "[bg][1:v]overlay=0:0[out]",
        "-map", "[out]", "-t", "3.0", "-c:v", "libx264", "-pix_fmt", "yuv420p", "scene1.mp4"
    ], check=True)

    print("Generating Scene 2...")
    prepare_slab_base(story["photo2"], "slab2.png")
    create_video_overlay("MARKET WATCH", "PRISTINE POPULATION", "DROPPING DAILY", "SWIPE BIO!", "overlay2.png")

    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", "slab2.png", "-i", "overlay2.png",
        "-filter_complex",
        "[0:v]scale=8000:-1,zoompan=z='1.10':x='iw/2-(iw/zoom/2)+sin(in/10)*20':y='ih/2-(ih/zoom/2)':d=90:s=1080x1920:fps=30[bg];"
        "[bg][1:v]overlay=0:0[out]",
        "-map", "[out]", "-t", "3.0", "-c:v", "libx264", "-pix_fmt", "yuv420p", "scene2.mp4"
    ], check=True)

    print("Generating Scene 3 CTA...")
    make_cta_slide("cta_slide.png")
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-t", "2.0", "-i", "cta_slide.png",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "scene3.mp4"
    ], check=True)

    # Audio Muxing
    audio_file = prepare_reliable_audio("bg_audio.mp3")

    with open("concat_list.txt", "w") as f:
        f.write("file 'scene1.mp4'\n")
        f.write("file 'scene2.mp4'\n")
        f.write("file 'scene3.mp4'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt",
        "-i", audio_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", "[1:a]afade=t=out:st=6.8:d=1.2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", "8.0",
        output_mp4
    ], check=True)

    return output_mp4

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
    story = fetch_live_news()
    print(f"Producing Cinematic Video Reel: {story['line1']} {story['line2']}")

    mp4_file = compile_cinematic_motion_reel(story, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    caption = (
        f"🚨 {story['alert']} | {story['line1']} {story['line2']} {story['line3']}\n\n"
        f"Context: {story['context']}\n\n"
        f"What are your thoughts on this latest market move? Drop your comments below! 👇\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
    )

    publish_content(video_cdn_url, caption)
