import os
import re
import time
import subprocess
import cloudinary
import cloudinary.uploader
import requests
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

cloudinary.config(cloudinary_url=os.getenv("CLOUDINARY_URL", "").strip())

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
IG_USER_ID = "17841472317326348"

# 1080x1920 Instagram Reel Specs
W, H = 1080, 1920

NEWS_SOURCES = [
    {"name": "POKEBEACH", "rss": "https://www.pokebeach.com/feed", "badge": "BREAKING NEWS"},
    {"name": "POKEGUARDIAN", "rss": "https://www.pokeguardian.com/rss.xml", "badge": "SET REVEAL"}
]

def ensure_font():
    if not os.path.exists("BebasNeue.ttf"):
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf"
        r = requests.get(url, headers=API_HEADERS)
        with open("BebasNeue.ttf", "wb") as f:
            f.write(r.content)

ensure_font()

def get_font(size):
    try:
        return ImageFont.truetype("BebasNeue.ttf", size)
    except Exception:
        return ImageFont.load_default()

def fetch_live_article():
    """Fetches breaking Pokémon article and extracts authentic card/product images using built-in regex."""
    posted_log = "posted_news.txt"
    posted = set()
    if os.path.exists(posted_log):
        with open(posted_log, "r") as f:
            posted = set(line.strip() for line in f if line.strip())

    for source in NEWS_SOURCES:
        try:
            r = requests.get(source["rss"], headers=API_HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel is None:
                continue

            for item in channel.findall("item"):
                link = item.find("link").text.strip() if item.find("link") is not None else ""
                if link in posted:
                    continue

                title = item.find("title").text.strip() if item.find("title") is not None else "BREAKING POKÉMON NEWS"
                desc = item.find("description").text if item.find("description") is not None else ""

                article_images = []
                try:
                    art_page = requests.get(link, headers=API_HEADERS, timeout=10)
                    # Extract high-res card/product image URLs via regex (zero external dependencies)
                    matches = re.findall(r'<img[^>]+(?:src|data-src)=["\'](https?://[^"\']+\.(?:png|jpg|jpeg))["\']', art_page.text, re.I)
                    for src in matches:
                        if not any(x in src.lower() for x in ["icon", "logo", "avatar", "gravatar", "banner", "emoji"]):
                            if src not in article_images:
                                article_images.append(src)
                except Exception:
                    pass

                if not article_images:
                    for src in re.findall(r'src=["\'](https?://[^"\']+\.(?:png|jpg|jpeg))["\']', desc, re.I):
                        if not any(x in src.lower() for x in ["icon", "logo", "avatar"]):
                            article_images.append(src)

                with open(posted_log, "a") as f:
                    f.write(link + "\n")

                clean_desc = re.sub(r'<[^>]+>', '', desc).strip()
                return {
                    "source": source["name"],
                    "badge": source["badge"],
                    "title": title,
                    "summary": clean_desc[:260],
                    "images": article_images,
                    "url": link
                }
        except Exception as e:
            print(f"Error checking {source['name']}: {e}")
            continue

    return {
        "source": "POKEBEACH",
        "badge": "BREAKING NEWS",
        "title": "TEAM ROCKET EXPANSION OFFICIALLY CONFIRMED",
        "summary": "Special Illustration Rares and Secret Illustration Rares revealed for the upcoming international expansion.",
        "images": ["https://images.pokemontcg.io/col1/22_hires.png"],
        "url": "https://www.pokebeach.com"
    }

def draw_autofit_text(draw, text, y, max_w=980, target_size=155, min_size=55, fill="white", stroke_fill="#000000", stroke_width=8):
    if not text:
        return y
    curr_size = target_size
    font = get_font(curr_size)
    while curr_size > min_size:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        if w <= max_w:
            break
        curr_size -= 3
        font = get_font(curr_size)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((W - w) // 2, y), text, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
    return y + h + 8

def render_card_ladder_slide(img_url, badge_text, line1, line2, line3, out_path):
    base = Image.new("RGB", (W, H), (10, 10, 14))
    draw = ImageDraw.Draw(base)

    try:
        r = requests.get(img_url, headers=API_HEADERS, timeout=10)
        with open("temp_news_img.png", "wb") as f:
            f.write(r.content)
        card_raw = Image.open("temp_news_img.png").convert("RGB")
        card_raw.thumbnail((1020, 1150), Image.Resampling.LANCZOS)
        cw, ch = card_raw.size
        base.paste(card_raw, ((W - cw) // 2, 60))
    except Exception as e:
        print(f"Error loading news image {img_url}: {e}")

    # Deep black cinematic gradient transition
    for y in range(960, 1260):
        t = (y - 960) / 300
        draw.line([(0, y), (W, y)], fill=(10, 10, 14, int(255 * t)))

    # Red Alert Pill Badge
    a_font = get_font(52)
    abox = draw.textbbox((0, 0), badge_text, font=a_font)
    aw = (abox[2] - abox[0]) + 56
    ah = 68
    ax = (W - aw) // 2
    ay = 1140

    draw.rounded_rectangle([ax + 3, ay + 4, ax + aw + 3, ay + ah + 4], radius=6, fill="#000000")
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=4, fill="#E50914")
    draw.text((ax + 28, ay + 6), badge_text, font=a_font, fill="#FFFFFF")

    # Typography Stack (Bebas Neue)
    y_start = ay + ah + 22
    y_start = draw_autofit_text(draw, line1, y_start, target_size=150, fill="#FFE600")
    y_start = draw_autofit_text(draw, line2, y_start, target_size=150, fill="#FFFFFF")
    if line3:
        draw_autofit_text(draw, line3, y_start, target_size=130, fill="#00FF66")

    base.save(out_path)

def make_cta_slide(out_path="f_cta.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    cdata = requests.get(cta_url, headers=API_HEADERS).content
    with open("raw_cta.png", "wb") as f:
        f.write(cdata)

    base = Image.new("RGB", (W, H), (10, 10, 14))
    cta_img = Image.open("raw_cta.png").convert("RGB")
    cta_img.thumbnail((1080, 1350), Image.Resampling.LANCZOS)
    cw, ch = cta_img.size
    base.paste(cta_img, ((W - cw) // 2, 160))

    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle([80, 1620, W - 80, 1730], radius=55, fill="#FFE600", outline="#FFFFFF", width=3)
    c_font = get_font(52)
    c_box = draw.textbbox((0, 0), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font)
    draw.text(((W - (c_box[2] - c_box[0])) // 2, 1644), "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER", font=c_font, fill="#000000")
    base.save(out_path)

def get_upbeat_pokemon_audio(duration):
    """Generates an upbeat energetic 8-bit adventure arpeggio."""
    audio_path = "pokemon_beat.mp3"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"aevalsrc=sin(880*2*PI*t)*0.2*lt(mod(t*4,1),0.4)+sin(1174.66*2*PI*t)*0.25*between(mod(t*4,1),0.1,0.5)+sin(1318.51*2*PI*t)*0.2*between(mod(t*4,1),0.2,0.6)+sin(1760*2*PI*t)*0.15*between(mod(t*4,1),0.3,0.7):s=44100:d={duration}",
        "-c:a", "libmp3lame", "-b:a", "192k",
        audio_path
    ]
    try:
        subprocess.run(cmd, check=True)
        return audio_path
    except Exception:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            f"-i", f"sine=frequency=440:duration={duration}",
            "-c:a", "libmp3lame", audio_path
        ], check=True)
        return audio_path

def build_reel_and_publish():
    article = fetch_live_article()
    print(f"Building Reel for: {article['title']}")

    imgs = article["images"]
    img1 = imgs[0] if len(imgs) > 0 else "https://images.pokemontcg.io/col1/22_hires.png"
    img2 = imgs[1] if len(imgs) > 1 else img1
    img3 = imgs[2] if len(imgs) > 2 else img1

    words = article["title"].upper().split()
    half = max(1, len(words) // 2)
    t1 = " ".join(words[:half])
    t2 = " ".join(words[half:])

    # Scene 1: Breaking Hook
    render_card_ladder_slide(img1, article["badge"], t1, t2, "POKEPULSE EXCLUSIVE", "s1.png")

    # Scene 2: Official Source & Details
    render_card_ladder_slide(img2, article["source"], "OFFICIAL RELEASE", "DETAILS CONFIRMED", "FULL BREAKDOWN BELOW", "s2.png")

    # Scene 3: Market Impact
    render_card_ladder_slide(img3, "MARKET IMPACT", "CHASE CARD REVEAL", "PRICES & RESTOCKS", "CHECK CAPTION", "s3.png")

    # Scene 4: PokéPulse CTA Slide
    make_cta_slide("s4.png")

    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "3.2", "-i", "s1.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "v1.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "3.2", "-i", "s2.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "v2.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "3.2", "-i", "s3.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "v3.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "2.8", "-i", "s4.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "v4.mp4"], check=True)

    with open("concat.txt", "w") as f:
        f.write("file 'v1.mp4'\nfile 'v2.mp4'\nfile 'v3.mp4'\nfile 'v4.mp4'\n")

    total_len = 12.4
    audio_file = get_upbeat_pokemon_audio(total_len)

    final_mp4 = "live_pokepulse_reel.mp4"
    fade_start = round(total_len - 1.2, 2)
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        "-i", audio_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", f"[1:a]afade=t=out:st={fade_start}:d=1.2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", str(total_len),
        final_mp4
    ], check=True)

    print("Uploading to Cloudinary...")
    res = cloudinary.uploader.upload_large(final_mp4, resource_type="video", folder="pokepulse_reels")
    video_url = res.get("secure_url")

    caption = (
        f"🚨 {article['badge']} | {article['title']}\n\n"
        f"Reported via {article['source']}:\n"
        f"{article['summary']}\n\n"
        f"Read full breakdown & card analysis in this week's PokéPulse market report!\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokeBeach #PokemonNews"
    )

    access_token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    r = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token
    }).json()

    if "id" in r:
        cid = r["id"]
        for _ in range(16):
            time.sleep(10)
            st = requests.get(f"https://graph.facebook.com/v21.0/{cid}?fields=status_code&access_token={access_token}").json()
            if st.get("status_code") == "FINISHED":
                break
        pub = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish", data={
            "creation_id": cid,
            "access_token": access_token
        }).json()
        print("Published Live News Reel:", pub)
    else:
        print("Instagram error:", r)

if __name__ == "__main__":
    build_reel_and_publish()
