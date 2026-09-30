import os
import re
import time
import glob
import random
import subprocess
import cloudinary
import cloudinary.uploader
import requests
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL", "").strip()
)

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
IG_USER_ID = "17841472317326348"

NEWS_SOURCES = [
    {"name": "POKEBEACH", "rss": "https://www.pokebeach.com/feed", "badge": "BREAKING NEWS"},
    {"name": "POKEGUARDIAN", "rss": "https://www.pokeguardian.com/rss.xml", "badge": "SET REVEAL"}
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
    x = (W - w) // 2

    draw.text((x, y), text, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
    return y + h - 6

def calculate_reading_duration(scene):
    words = sum(len(scene.get(f"line{i}", "").split()) for i in [1, 2, 3])
    calc_dur = 1.8 + (words * 0.28)
    return round(max(2.4, min(calc_dur, 4.2)), 2)

def scrape_exact_article_images(article_url, domain):
    found_images = []
    try:
        r = requests.get(article_url, headers=API_HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        
        html = r.text
        raw_imgs = re.findall(r'<img[^>]+(?:src|data-src|data-lazy-src)=["\']([^"\']+\.(?:png|jpg|jpeg))["\']', html, re.I)
        
        for img_src in raw_imgs:
            img_src = img_src.strip()
            if img_src.startswith("//"):
                img_src = "https:" + img_src
            elif img_src.startswith("/"):
                base = "https://www.pokebeach.com" if "pokebeach" in domain.lower() else "https://www.pokeguardian.com"
                img_src = base + img_src

            lower = img_src.lower()
            if any(ign in lower for ign in ["logo", "avatar", "gravatar", "icon", "banner", "button", "ads", "pixel", "facebook", "twitter", "footer"]):
                continue

            if img_src not in found_images:
                found_images.append(img_src)

    except Exception as e:
        print(f"Error scraping images from {article_url}: {e}")

    return found_images

def build_dynamic_story_from_live_news():
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

                raw_title = item.find("title").text.strip() if item.find("title") is not None else "BREAKING POKÉMON NEWS"
                desc = item.find("description").text if item.find("description") is not None else ""
                clean_desc = re.sub(r'<[^>]+>', '', desc).strip()

                print(f"Checking article: {raw_title}")
                article_images = scrape_exact_article_images(link, source["name"])
                
                if not article_images:
                    print(f"No direct card scans in {link}, checking next...")
                    continue

                with open(posted_log, "a") as f:
                    f.write(link + "\n")

                print(f"Extracted photos from article: {article_images[:3]}")

                img1 = article_images[0]
                img2 = article_images[1] if len(article_images) > 1 else img1
                img3 = article_images[2] if len(article_images) > 2 else img2
                img4 = article_images[3] if len(article_images) > 3 else img1

                words = raw_title.upper().split()
                half = max(1, len(words) // 2)
                t1 = " ".join(words[:half])
                t2 = " ".join(words[half:])

                story = {
                    "story_id": raw_title[:30],
                    "scenes": [
                        {
                            "tag": source["badge"],
                            "img_url": img1,
                            "crop_mode": "center",
                            "line1": t1,
                            "line1_color": "#FFE600",
                            "line2": t2,
                            "line2_color": "#FFFFFF",
                            "line3": "POKEPULSE EXCLUSIVE",
                            "line3_color": "#00FF66"
                        },
                        {
                            "tag": source["name"],
                            "img_url": img2,
                            "crop_mode": "center",
                            "line1": "OFFICIAL REVEAL",
                            "line1_color": "#FFE600",
                            "line2": "DETAILS CONFIRMED",
                            "line2_color": "#FFFFFF",
                            "line3": "CHECKING THE SPECS",
                            "line3_color": "#00FF66"
                        },
                        {
                            "tag": "MARKET IMPACT",
                            "img_url": img3,
                            "crop_mode": "center",
                            "line1": "CHASE CARDS ALERT",
                            "line1_color": "#FFFFFF",
                            "line2": "PRICING & RESTOCKS",
                            "line2_color": "#FFE600",
                            "line3": "COLLECTOR DEMAND",
                            "line3_color": "#00FF66"
                        },
                        {
                            "tag": "POKEPULSE VERDICT",
                            "img_url": img4,
                            "crop_mode": "center",
                            "line1": "FULL BREAKDOWN",
                            "line1_color": "#FFE600",
                            "line2": "IN CAPTION BELOW",
                            "line2_color": "#FFFFFF",
                            "line3": "STAY AHEAD OF RESTOCKS",
                            "line3_color": "#00FF66"
                        }
                    ],
                    "caption_full": (
                        f"🚨 {source['badge']} | {raw_title}!\n\n"
                        f"Official Report via {source['name']}:\n"
                        f"{clean_desc[:280]}\n\n"
                        f"What are your thoughts on this drop? Drop your reaction below! 👇\n\n"
                        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
                        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokeBeach #PokemonNews"
                    )
                }
                return story
        except Exception as e:
            print(f"Error checking {source['name']}: {e}")
            continue

    raise Exception("No fresh articles with scrapable card images found. Check back shortly!")

def render_native_scene_slide(scene, out_path):
    img = Image.new("RGB", (W, H), (10, 10, 14))
    draw = ImageDraw.Draw(img)

    try:
        pdata = requests.get(scene["img_url"], headers=API_HEADERS, timeout=10).content
        with open("temp_raw.png", "wb") as f:
            f.write(pdata)
        raw = Image.open("temp_raw.png").convert("RGB")
        raw.thumbnail((1020, 1160), Image.Resampling.LANCZOS)
        rw, rh = raw.size
        img.paste(raw, ((W - rw) // 2, 40))
    except Exception as e:
        print(f"Error loading image {scene['img_url']}: {e}")

    for y in range(980, 1260):
        t = (y - 980) / 280
        alpha = int(255 * t)
        draw.line([(0, y), (W, y)], fill=(10, 10, 14, alpha))

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

    has_3 = bool(scene.get("line3"))
    start_target = 142 if has_3 else 178

    y_start = ay + ah + 16
    y_start = draw_autofit_text(draw, scene.get("line1", ""), y_start, max_w=980, target_size=start_target, fill=scene.get("line1_color", "#FFFFFF"))
    y_start = draw_autofit_text(draw, scene.get("line2", ""), y_start, max_w=980, target_size=start_target, fill=scene.get("line2_color", "#FFFFFF"))
    if has_3:
        draw_autofit_text(draw, scene.get("line3", ""), y_start, max_w=980, target_size=start_target, fill=scene.get("line3_color", "#00FF66"))

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

def compile_live_action_reel(story, output_mp4="pokepulse_reel.mp4"):
    scene_vids = []
    total_duration = 0.0

    for idx, sc in enumerate(story["scenes"]):
        slide_img = f"slide_{idx+1}.png"
        out_vid = f"scene_{idx+1}.mp4"

        dur = calculate_reading_duration(sc)
        total_duration += dur

        print(f"Rendering scene {idx+1} ({dur}s): {sc['line1']}...")
        render_native_scene_slide(sc, slide_img)

        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", str(dur), "-i", slide_img,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", out_vid
        ], check=True)
        scene_vids.append(out_vid)

    cta_dur = 2.8
    total_duration += cta_dur
    print(f"Rendering Scene 5: Newsletter CTA ({cta_dur}s)...")
    make_cta_slide("f_cta.png")
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-t", str(cta_dur), "-i", "f_cta.png",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "scene_cta.mp4"
    ], check=True)
    scene_vids.append("scene_cta.mp4")

    with open("playlist.txt", "w") as f:
        for v in scene_vids:
            f.write(f"file '{v}'\n")

    # Detect all uploaded audio in audio/ folder or root
    audio_candidates = glob.glob("audio/*.mp3") + glob.glob("audio/*.wav") + glob.glob("*.mp3")
    audio_candidates = [f for f in audio_candidates if f not in ["bg_audio.mp3", "pokemon_beat.mp3"]]

    if audio_candidates:
        selected_audio = random.choice(audio_candidates)
        print(f"Using rotated soundtrack: {selected_audio}")
        audio_file = selected_audio
    else:
        audio_file = "bg_audio.wav"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"sine=frequency=220:sample_rate=44100",
            "-t", str(total_duration),
            "-c:a", "pcm_s16le",
            audio_file
        ], check=True)

    fade_start = max(0.5, round(total_duration - 1.2, 2))
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-stream_loop", "-1", "-i", audio_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", f"[1:a]afade=t=out:st={fade_start}:d=1.2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-shortest",
        "-t", str(total_duration),
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
        for _ in range(18):
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
    story = build_dynamic_story_from_live_news()
    print(f"Producing Live News Reel: {story['story_id']}")

    mp4_file = compile_live_action_reel(story, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    publish_content(video_cdn_url, story["caption_full"])
