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

# High-Energy News Broadcast & Adventure Beats (Royalty-Free)
BROADCAST_AUDIO_TRACKS = [
    "https://actions.google.com/sounds/v1/sports/cheering_crowd.ogg",
    "https://actions.google.com/sounds/v1/science_fiction/force_field_hum.ogg",
    "https://raw.githubusercontent.com/rafaelreis-hotmart/Audio-Sample-files/master/sample.mp3"
]

# IN-DEPTH 5-PART DOCUMENTARY NEWS STORIES
DOCUMENTARY_NEWS_STORIES = [
    {
        "story_id": "zoroark_kindergarten_doc",
        "alert": "AUCTION ALERT",
        "scenes": [
            {
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
            {
                "tag": "ORIGIN STORY",
                "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
                "zoom_type": "macro_crop",
                "line1": "2010 CONTEST",
                "line1_color": "#FFE600",
                "line2": "MEGU TANIGUCHI",
                "line2_color": "#FFFFFF",
                "line3": "ILLUSION'S ZORUA",
                "line3_color": "#00FF66"
            },
            {
                "tag": "HISTORIC ARTIFACT",
                "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
                "zoom_type": "macro_slab",
                "line1": "THE ONLY",
                "line1_color": "#FFFFFF",
                "line2": "BGS PRISTINE 10",
                "line2_color": "#FFE600",
                "line3": "FROM ENTIRE CONTEST",
                "line3_color": "#00FF66"
            },
            {
                "tag": "AUCTION RECORD",
                "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
                "zoom_type": "macro_slab",
                "line1": "HAMMER DROPPED",
                "line1_color": "#FFE600",
                "line2": "AT $72,000 USD",
                "line2_color": "#FFFFFF",
                "line3": "1 OF 1 HOLY GRAIL",
                "line3_color": "#00FF66"
            }
        ],
        "caption_full": (
            "🚨 AUCTION ALERT | A KINDERGARTENER DESIGNED THIS $72,000+ CARD!\n\n"
            "In 2010, the Pokémon Company hosted the legendary 'Ruler of Illusion Zoroark' design contest in Japan.\n\n"
            "Six-year-old kindergarten winner Megu Taniguchi drew this charming Zorua riding in a bus alongside Pikachu. "
            "Only winners received copies of their own cards, making this one of the rarest Pokémon artifacts on Earth.\n\n"
            "This exact card was certified by Beckett as a Pristine 10—the only Pristine 10 from the entire contest—and just hammered at an all-time record of $72,000+ USD!\n\n"
            "What would you pay for a true 1-of-1 piece of Pokémon history? Drop your thoughts below! 👇\n\n"
            "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
            "#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
        )
    },
    {
        "story_id": "platinum_lvx_doc",
        "alert": "MARKET ALERT",
        "scenes": [
            {
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
            {
                "tag": "SUPPLY SHOCK",
                "img_url": "https://images.pokemontcg.io/pl3/146_hires.png",
                "zoom_type": "macro_crop",
                "line1": "SUPREME VICTORS",
                "line1_color": "#FFE600",
                "line2": "RAYQUAZA C LV.X",
                "line2_color": "#FFFFFF",
                "line3": "PSA 10 POP NEAR ZERO",
                "line3_color": "#00FF66"
            },
            {
                "tag": "PRICE SQUEEZE",
                "img_url": "https://images.pokemontcg.io/dp7/103_hires.png",
                "zoom_type": "macro_crop",
                "line1": "STORMFRONT & DP",
                "line1_color": "#FFE600",
                "line2": "30-DAY SALES",
                "line2_color": "#FFFFFF",
                "line3": "SURGING OVER 400%",
                "line3_color": "#00FF66"
            },
            {
                "tag": "INVESTOR OUTLOOK",
                "img_url": "https://images.pokemontcg.io/pl1/128_hires.png",
                "zoom_type": "macro_slab",
                "line1": "RAW COPIES DRIED",
                "line1_color": "#FFE600",
                "line2": "THE NEXT BIG VINTAGE",
                "line2_color": "#FFFFFF",
                "line3": "MARKET ABSORPTION",
                "line3_color": "#00FF66"
            }
        ],
        "caption_full": (
            "🚨 MARKET ALERT | PLATINUM ERA LV.X IS MOVING FAST!\n\n"
            "Between 2007 and 2009, Diamond & Pearl and Platinum introduced Level X holos with shimmering silver borders and dynamic Pokémon popping out of the artwork.\n\n"
            "Today, PSA 10 populations for chase Lv.X cards like Rayquaza C, Charizard, and Garchomp are in the single digits worldwide.\n\n"
            "Over the past 30 days, auction volume and buy pressure have surged over 400% as vintage collectors shift from WOTC to Platinum era grails!\n\n"
            "Are you stacking Lv.X holos or focusing on modern SIRs? Let's discuss in the comments! 👇\n\n"
            "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
            "#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
        )
    },
    {
        "story_id": "call_of_legends_doc",
        "alert": "TRENDING NOW",
        "scenes": [
            {
                "tag": "TRENDING NOW",
                "img_url": "https://images.pokemontcg.io/swsh7/215_hires.png",
                "zoom_type": "macro_slab",
                "line1": "THE LOW POP",
                "line1_color": "#FFE600",
                "line2": "VINTAGE MARKET",
                "line2_color": "#FFFFFF",
                "line3": "IS SURGING.",
                "line3_color": "#00FF66"
            },
            {
                "tag": "SHINY GRAILS",
                "img_url": "https://images.pokemontcg.io/swsh7/215_hires.png",
                "zoom_type": "macro_crop",
                "line1": "CALL OF LEGENDS",
                "line1_color": "#FFE600",
                "line2": "LUGIA & UMBREON",
                "line2_color": "#FFFFFF",
                "line3": "RECORD AUCTIONS",
                "line3_color": "#00FF66"
            },
            {
                "tag": "HISTORIC RARITY",
                "img_url": "https://images.pokemontcg.io/ex8/105_hires.png",
                "zoom_type": "macro_crop",
                "line1": "EX ERA GOLD STARS",
                "line1_color": "#FFE600",
                "line2": "CGC PRISTINE 10",
                "line2_color": "#FFFFFF",
                "line3": "BLOWS PAST 45K USD",
                "line3_color": "#00FF66"
            },
            {
                "tag": "AUCTION VERDICT",
                "img_url": "https://images.pokemontcg.io/ex14/100_hires.png",
                "zoom_type": "macro_slab",
                "line1": "BUY, SELL OR HOLD?",
                "line1_color": "#FFE600",
                "line2": "PRISTINE SUPPLY",
                "line2_color": "#FFFFFF",
                "line3": "VIRTUALLY EXTINCT",
                "line3_color": "#00FF66"
            }
        ],
        "caption_full": (
            "🚨 TRENDING NOW | THE LOW POP VINTAGE MARKET IS SURGING!\n\n"
            "High-grade vintage grails from Call of Legends and the mid-2000s EX era are breaking historical auction ceilings.\n\n"
            "With populations locked away in private vaults, pristine 10 sales have doubled over the last quarter alone.\n\n"
            "Are vintage grails the safest long-term hold in the Pokémon hobby? Let us know below! 👇\n\n"
            "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
            "#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
        )
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

# --- CARD LADDER FULL-BLEED SLIDE GENERATOR ---
def render_story_slide(scene, out_path):
    img = Image.new("RGB", (W, H), (10, 10, 12))
    draw = ImageDraw.Draw(img)

    pdata = requests.get(scene["img_url"], headers=API_HEADERS).content
    with open("temp_raw.png", "wb") as f:
        f.write(pdata)
    raw_img = Image.open("temp_raw.png").convert("RGB")

    photo_box_h = 1180
    if scene["zoom_type"] == "macro_art":
        iw, ih = raw_img.size
        crop_box = (int(iw * 0.08), int(ih * 0.12), int(iw * 0.92), int(ih * 0.65))
        raw_img = raw_img.crop(crop_box)
        raw_img = raw_img.resize((W, photo_box_h), Image.Resampling.LANCZOS)
        img.paste(raw_img, (0, 0))
    elif scene["zoom_type"] == "macro_crop":
        iw, ih = raw_img.size
        crop_box = (int(iw * 0.10), int(ih * 0.18), int(iw * 0.90), int(ih * 0.72))
        raw_img = raw_img.crop(crop_box)
        raw_img = raw_img.resize((W, photo_box_h), Image.Resampling.LANCZOS)
        img.paste(raw_img, (0, 0))
    else:
        raw_img.thumbnail((1000, 1140), Image.Resampling.LANCZOS)
        rw, rh = raw_img.size
        rx = (W - rw) // 2
        ry = 30
        img.paste(raw_img, (rx, ry))

    # Dark Vignette Gradient Transition
    for y in range(960, 1240):
        t = (y - 960) / 280
        alpha = int(255 * t)
        draw.line([(0, y), (W, y)], fill=(10, 10, 12, alpha))

    # Red Alert Pill Badge
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

    # Stacked Bebas Typography
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
def make_cta_slide(out_path="f_cta.png"):
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

# --- FFMPEG 15-SECOND MINI-DOCUMENTARY COMPILER ---
def compile_documentary_reel(story, output_mp4="pokepulse_reel.mp4"):
    scene_files = []
    # 4 Story Chapters (3.0s each)
    for idx, sc in enumerate(story["scenes"]):
        fname = f"scene_{idx+1}.png"
        vname = f"s_{idx+1}.mp4"
        print(f"Rendering Story Chapter {idx+1}: {sc['line1']}...")
        render_story_slide(sc, fname)
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-t", "3.0", "-i", fname,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", vname
        ], check=True)
        scene_files.append(vname)

    # 5th Scene: Newsletter CTA (3.0s)
    print("Rendering Scene 5: Newsletter CTA...")
    make_cta_slide("f_cta.png")
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-t", "3.0", "-i", "f_cta.png",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "s_cta.mp4"
    ], check=True)
    scene_files.append("s_cta.mp4")

    # Playlist
    with open("playlist.txt", "w") as f:
        for v in scene_files:
            f.write(f"file '{v}'\n")

    # Audio Download / Fallback (Total 15.0s)
    audio_file = "bg_audio.mp3"
    audio_success = False
    for track_url in BROADCAST_AUDIO_TRACKS:
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
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=130:duration=15.0",
            "-c:a", "libmp3lame", "-b:a", "192k", audio_file
        ], check=True)

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-i", audio_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", "[1:a]afade=t=out:st=13.5:d=1.5[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", "15.0",
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
    story = random.choice(DOCUMENTARY_NEWS_STORIES)
    print(f"Producing 15s Story Documentary Reel: {story['story_id']}")

    mp4_file = compile_documentary_reel(story, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    publish_content(video_cdn_url, story["caption_full"])
