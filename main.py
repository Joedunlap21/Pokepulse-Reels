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

COHESIVE_NEWS_STORIES = [
    {
        "story_id": "zoroark_kindergarten",
        "alert": "AUCTION ALERT",
        "scene1": {
            "title_tag": "AUCTION ALERT",
            "line1": "A KINDERGARTENER",
            "line2": "DESIGNED THIS",
            "line3": "72,000+ USD CARD",
            "photo": "https://images.pokemontcg.io/col1/22_hires.png"
        },
        "scene2": {
            "title_tag": "HISTORIC PROOF",
            "line1": "ONLY BGS 10",
            "line2": "FROM ENTIRE",
            "line3": "DESIGN CONTEST",
            "photo": "https://images.pokemontcg.io/col1/22_hires.png"
        },
        "scene3": {
            "title_tag": "MARKET IMPACT",
            "line1": "1 OF 1 GRAIL",
            "line2": "NEVER HITTING",
            "line3": "AUCTION AGAIN",
            "photo": "https://images.pokemontcg.io/col1/22_hires.png"
        },
        "caption_sub": "In 2010, Pokémon held the Zoroark Card Design Contest across Japan. Winner Megu Taniguchi designed this legendary Zorua promo in kindergarten. A BGS Pristine 10 just smashed all sales records at over 72,000 USD!"
    },
    {
        "story_id": "gold_star_cgc_surge",
        "alert": "MARKET ALERT",
        "scene1": {
            "title_tag": "MARKET ALERT",
            "line1": "GOLD STAR",
            "line2": "CGC GRAILS",
            "line3": "ENDING TONIGHT!",
            "photo": "https://images.pokemontcg.io/ex8/105_hires.png"
        },
        "scene2": {
            "title_tag": "DEOXYS GRAIL",
            "line1": "LATIAS GOLD STAR",
            "line2": "PRISTINE 10 SUBGRADES",
            "line3": "BLOWS PAST 45K USD",
            "photo": "https://images.pokemontcg.io/ex8/105_hires.png"
        },
        "scene3": {
            "title_tag": "VINTAGE SCARCITY",
            "line1": "EX ERA SUPPLY DRIED",
            "line2": "INVESTORS HOARDING",
            "line3": "NEXT TARGET: RAYQUAZA",
            "photo": "https://images.pokemontcg.io/ex8/105_hires.png"
        },
        "caption_sub": "Gold Star Pristine 10s from the mid-2000s EX era are officially in price discovery mode. High-grade copies are breaking all historical price ceilings."
    },
    {
        "story_id": "platinum_lvx_extinction",
        "alert": "TRENDING NOW",
        "scene1": {
            "title_tag": "TRENDING NOW",
            "line1": "PLATINUM LV.X",
            "line2": "ARE MOVING",
            "line3": "INSANELY FAST",
            "photo": "https://images.pokemontcg.io/pl3/146_hires.png"
        },
        "scene2": {
            "title_tag": "AUCTION SQUEEZE",
            "line1": "RAYQUAZA & GARCHOMP",
            "line2": "HITTING ALL-TIME",
            "line3": "PRICE PEAKS",
            "photo": "https://images.pokemontcg.io/pl3/146_hires.png"
        },
        "scene3": {
            "title_tag": "FUTURE VALUE",
            "line1": "RAW COPIES GONE",
            "line2": "GRADED COPIES",
            "line3": "BECOMING UNTOUCHABLE",
            "photo": "https://images.pokemontcg.io/pl3/146_hires.png"
        },
        "caption_sub": "Supreme Victors and DP era Lv.X holos are undergoing massive market absorption. With high-grade populations near zero, collectors are sweeping inventory."
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

def create_studio_canvas():
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

    return img

def build_fitted_scene(scene_data, out_path):
    img = create_studio_canvas()
    draw = ImageDraw.Draw(img)

    pdata = requests.get(scene_data["photo"], headers=API_HEADERS).content
    with open("temp_card.png", "wb") as f:
        f.write(pdata)

    card = Image.open("temp_card.png").convert("RGBA")
    card.thumbnail((900, 1040), Image.Resampling.LANCZOS)
    cw, ch = card.size
    cx = (W - cw) // 2
    cy = 60

    draw.rounded_rectangle([cx - 15, cy - 8, cx + cw + 15, cy + ch + 18], radius=26, fill=(15, 8, 30))
    img.paste(card, (cx, cy), mask=card.split()[3])

    tag_text = scene_data["title_tag"]
    a_font = get_font(50)
    abox = draw.textbbox((0, 0), tag_text, font=a_font)
    aw = (abox[2] - abox[0]) + 56
    ah = 66
    ax = (W - aw) // 2
    ay = cy + ch + 15

    draw.rounded_rectangle([ax + 3, ay + 4, ax + aw + 3, ay + ah + 4], radius=10, fill=(0, 0, 0, 230))
    draw.rounded_rectangle([ax, ay, ax + aw, ay + ah], radius=8, fill="#E50914", outline="#FFFFFF", width=3)
    draw.text((ax + 28, ay + 6), tag_text, font=a_font, fill="#FFFFFF")

    f_huge = get_font(132)
    y_start = ay + ah + 18
    y_start = draw_tight_text(draw, scene_data["line1"], y_start, f_huge, fill="#FFE600")
    y_start = draw_tight_text(draw, scene_data["line2"], y_start, f_huge, fill="#FFFFFF")
    draw_tight_text(draw, scene_data["line3"], y_start, f_huge, fill="#00FF66")

    img.save(out_path)

def make_cta_slide(out_path="f4_cta.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    cdata = requests.get(cta_url, headers=API_HEADERS).content
    with open("raw_cta.png", "wb") as f:
        f.write(cdata)

    base = create_studio_canvas()
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

def compile_cohesive_news_reel(story, output_mp4="pokepulse_reel.mp4"):
    print("Building Scene 1 (Cover Hook)...")
    build_fitted_scene(story["scene1"], "f1_cover.png")

    print("Building Scene 2 (Story Context)...")
    build_fitted_scene(story["scene2"], "f2_context.png")

    print("Building Scene 3 (Market Forecast)...")
    build_fitted_scene(story["scene3"], "f3_impact.png")

    print("Building Scene 4 (Newsletter Outro)...")
    make_cta_slide("f4_cta.png")

    scene_files = [("f1_cover.png", "s1.mp4"), ("f2_context.png", "s2.mp4"), ("f3_impact.png", "s3.mp4"), ("f4_cta.png", "s4.mp4")]
    for img_in, vid_out in scene_files:
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", "2.2", "-i", img_in,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", vid_out
        ], check=True)

    with open("playlist.txt", "w") as f:
        for _, vid_out in scene_files:
            f.write(f"file '{vid_out}'\n")

    print("Generating pure 8-bit Pokemon-themed audio track...")
    audio_file = "bg_audio.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "sine=frequency=523.25:beep_factor=4:duration=8.8",
        "-c:a", "libmp3lame", "-b:a", "192k", audio_file
    ], check=True)

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-i", audio_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", "[1:a]afade=t=out:st=7.6:d=1.2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", "8.8",
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
    story = random.choice(COHESIVE_NEWS_STORIES)
    print(f"Producing Cohesive News Story Reel: {story['scene1']['line1']} {story['scene1']['line2']}")

    mp4_file = compile_cohesive_news_reel(story, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    caption = (
        f"🚨 {story['alert']} | {story['scene1']['line1']} {story['scene1']['line2']} {story['scene1']['line3']}\n\n"
        f"{story['caption_sub']}\n\n"
        f"What are your thoughts on this grail? Drop your comments below! 👇\n\n"
        f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
    )

    publish_content(video_cdn_url, caption)
