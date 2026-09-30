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

# LIVE TIER-1 POKEMON RSS FEEDS
NEWS_FEEDS = [
    {"source": "POKEBEACH", "url": "https://www.pokebeach.com/feed", "badge": "BREAKING NEWS"},
    {"source": "POKEGUARDIAN", "url": "https://www.pokeguardian.com/rss.xml", "badge": "SET REVEAL"}
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
    try:
        return ImageFont.truetype("BebasNeue.ttf", size)
    except Exception:
        return ImageFont.load_default()

def fetch_latest_pokemon_news():
    """Scrapes latest unposted breaking news from PokeBeach / PokeGuardian."""
    posted_log = "posted_news.txt"
    posted_ids = set()
    if os.path.exists(posted_log):
        with open(posted_log, "r") as f:
            posted_ids = set(line.strip() for line in f if line.strip())

    for feed in NEWS_FEEDS:
        try:
            r = requests.get(feed["url"], headers=API_HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            
            root = ET.fromstring(r.content)
            channel = root.find("channel")
            if channel is None:
                continue

            for item in channel.findall("item"):
                link = item.find("link").text.strip() if item.find("link") is not None else ""
                if link in posted_ids:
                    continue

                title = item.find("title").text.strip() if item.find("title") is not None else "BREAKING POKÉMON UPDATE"
                desc = item.find("description").text if item.find("description") is not None else ""
                clean_desc = re.sub(r'<[^>]+>', '', desc).strip()

                # Extract image thumbnail from description or enclosure
                img_url = "https://images.pokemontcg.io/swsh7/215_hires.png"
                img_match = re.search(r'src=["\'](https?://[^"\']+\.(?:png|jpg|jpeg))["\']', desc)
                if img_match:
                    img_url = img_match.group(1)

                # Record as posted
                with open(posted_log, "a") as f:
                    f.write(link + "\n")

                return {
                    "source": feed["source"],
                    "badge": feed["badge"],
                    "title": title,
                    "summary": clean_desc[:240],
                    "img_url": img_url,
                    "link": link
                }
        except Exception as e:
            print(f"Error checking {feed['source']}: {e}")
            continue

    # Fallback to TCGplayer Market Alert if feeds are temporarily down
    return {
        "source": "TCGPLAYER MARKET",
        "badge": "MARKET ALERT",
        "title": "TEAM ROCKET EXPANSION MARKET SURGE",
        "summary": "Special Illustration Rares and Secret Illustration Rares see double-digit price increases across major retail platforms.",
        "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
        "link": "https://infinite.tcgplayer.com/pokemon"
    }

def draw_autofit_text(draw, text, y, max_w=980, target_size=140, min_size=50, fill="white"):
    if not text:
        return y
    curr_size = target_size
    font = get_font(curr_size)
    while curr_size > min_size:
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=6)
        if (bbox[2] - bbox[0]) <= max_w:
            break
        curr_size -= 4
        font = get_font(curr_size)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=6)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((W - w) // 2, y), text, font=font, fill=fill, stroke_fill="#000000", stroke_width=6)
    return y + h + 10

def render_news_slide(news, slide_type, out_path):
    img = Image.new("RGB", (W, H), (10, 10, 14))
    draw = ImageDraw.Draw(img)

    # Download article/card image
    try:
        pdata = requests.get(news["img_url"], headers=API_HEADERS, timeout=8).content
        with open("temp_raw.png", "wb") as f:
            f.write(pdata)
        raw = Image.open("temp_raw.png").convert("RGB")
        raw.thumbnail((1020, 1160), Image.Resampling.LANCZOS)
        rw, rh = raw.size
        img.paste(raw, ((W - rw) // 2, 60))
    except Exception:
        pass

    # Black gradient underlay for text
    for y in range(980, 1260):
        t = (y - 980) / 280
        draw.line([(0, y), (W, y)], fill=(10, 10, 14, int(255 * t)))

    # Red Pill Badge
    tag_text = news["badge"] if slide_type == "hook" else news["source"]
    a_font = get_font(52)
    abox = draw.textbbox((0, 0), tag_text, font=a_font)
    aw = (abox[2] - abox[0]) + 56
    ah = 68
    ax = (W - aw) // 2
    ay = 1140

    draw.rounded_rectangle([ax + 3, ay + 4, ax + aw + 3, ay + ah + 4], radius=6, fill="#000000")
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=4, fill="#E50914")
    draw.text((ax + 28, ay + 6), tag_text, font=a_font, fill="#FFFFFF")

    y_pos = ay + ah + 24
    if slide_type == "hook":
        words = news["title"].upper().split()
        half = len(words) // 2
        line1 = " ".join(words[:half])
        line2 = " ".join(words[half:])
        y_pos = draw_autofit_text(draw, line1, y_pos, target_size=145, fill="#FFE600")
        draw_autofit_text(draw, line2, y_pos, target_size=145, fill="#FFFFFF")
    else:
        y_pos = draw_autofit_text(draw, "LATEST OFFICIAL REPORT", y_pos, target_size=120, fill="#FFE600")
        draw_autofit_text(draw, news["summary"][:90].upper(), y_pos, target_size=85, fill="#FFFFFF")

    img.save(out_path)

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

def compile_and_post():
    news = fetch_latest_pokemon_news()
    print(f"Scraped Breaking Story: {news['title']} via {news['source']}")

    render_news_slide(news, "hook", "slide_1.png")
    render_news_slide(news, "details", "slide_2.png")
    make_cta_slide("slide_3.png")

    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "3.2", "-i", "slide_1.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "v1.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "3.8", "-i", "slide_2.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "v2.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-t", "2.8", "-i", "slide_3.png", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "v3.mp4"], check=True)

    with open("list.txt", "w") as f:
        f.write("file 'v1.mp4'\nfile 'v2.mp4'\nfile 'v3.mp4'\n")

    out_mp4 = "pokepulse_live_reel.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
        "-f", "lavfi", "-i", "sine=frequency=130:duration=9.8",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-t", "9.8", out_mp4
    ], check=True)

    print("Uploading live Reel to Cloudinary...")
    res = cloudinary.uploader.upload_large(out_mp4, resource_type="video", folder="pokepulse_reels")
    video_url = res.get("secure_url")

    caption = (
        f"🚨 {news['badge']} | {news['title']}\n\n"
        f"Source: {news['source']}\n\n"
        f"{news['summary']}\n\n"
        f"Read full breakdown & market impacts in this week's PokéPulse report!\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #PokeBeach #CardStax #PokemonNews #PokemonReels #PokePulse"
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
        for _ in range(15):
            time.sleep(10)
            st = requests.get(f"https://graph.facebook.com/v21.0/{cid}?fields=status_code&access_token={access_token}").json()
            if st.get("status_code") == "FINISHED":
                break
        pub = requests.post(f"https://graph.facebook.com/v21.0/{IG_USER_ID}/media_publish", data={
            "creation_id": cid,
            "access_token": access_token
        }).json()
        print("Published live news Reel:", pub)
    else:
        print("Publishing error:", r)

if __name__ == "__main__":
    compile_and_post()
