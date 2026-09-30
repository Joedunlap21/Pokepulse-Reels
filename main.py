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

# High-Energy Broadcast Beats (Direct streams)
BROADCAST_AUDIO_TRACKS = [
    "https://actions.google.com/sounds/v1/sports/cheering_crowd.ogg",
    "https://actions.google.com/sounds/v1/science_fiction/force_field_hum.ogg",
    "https://raw.githubusercontent.com/rafaelreis-hotmart/Audio-Sample-files/master/sample.mp3"
]

LIVE_ACTION_STORIES = [
    {
        "story_id": "zoroark_kindergarten_mystery",
        "alert": "AUCTION ALERT",
        "scenes": [
            {
                "tag": "AUCTION ALERT",
                "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
                "crop_mode": "center",
                "motion": "zoom_in",
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
                "crop_mode": "art_box",
                "motion": "pan_right",
                "line1": "IN 2010 JAPAN",
                "line1_color": "#FFE600",
                "line2": "6-YEAR-OLD MEGU WON",
                "line2_color": "#FFFFFF",
                "line3": "OFFICIAL DESIGN CONTEST",
                "line3_color": "#00FF66"
            },
            {
                "tag": "HISTORIC RARITY",
                "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
                "crop_mode": "slab_top",
                "motion": "zoom_in",
                "line1": "COPIES GIVEN ONLY",
                "line1_color": "#FFFFFF",
                "line2": "TO CONTEST WINNERS",
                "line2_color": "#FFE600",
                "line3": "LESS THAN 10 EXIST",
                "line3_color": "#00FF66"
            },
            {
                "tag": "AUCTION CLIMAX",
                "img_url": "https://images.pokemontcg.io/col1/22_hires.png",
                "crop_mode": "center",
                "motion": "pan_left",
                "line1": "HAMMER DROPPED",
                "line1_color": "#FFE600",
                "line2": "AT $72,000 USD",
                "line2_color": "#FFFFFF",
                "line3": "ONLY BGS 10 ON EARTH",
                "line3_color": "#00FF66"
            }
        ],
        "caption_full": (
            "🚨 AUCTION ALERT | A KINDERGARTENER DESIGNED THIS $72,000+ CARD!\n\n"
            "In 2010, the Pokémon Company ran the legendary 'Ruler of Illusion Zoroark' design contest in Japan.\n\n"
            "Megu Taniguchi, a kindergarten student, drew this delightful Zorua riding a red bus alongside Pikachu. "
            "Her artwork won first place, and she was awarded official copies of her card.\n\n"
            "With less than 10 copies known to exist worldwide, a pristine BGS 10 copy just crossed the auction block, hammering at an unbelievable $72,000+ USD!\n\n"
            "What would you do if you owned this 1-of-1 grail? Drop your thoughts below! 👇\n\n"
            "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
            "#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews"
        )
    },
    {
        "story_id": "platinum_rayquaza_synthesis",
        "alert": "MARKET ALERT",
        "scenes": [
            {
                "tag": "MARKET ALERT",
                "img_url": "https://images.pokemontcg.io/pl3/146_hires.png",
                "crop_mode": "center",
                "motion": "zoom_in",
                "line1": "LV.X GRAILS",
                "line1_color": "#00FF66",
                "line2": "ARE MOVING",
                "line2_color": "#FFFFFF",
                "line3": "INSANELY FAST.",
                "line3_color": "#FFE600"
            },
            {
                "tag": "SUPPLY SHOCK",
                "img_url": "https://images.pokemontcg.io/pl3/146_hires.png",
                "crop_mode": "art_box",
                "motion": "pan_right",
                "line1": "SUPREME VICTORS",
                "line1_color": "#FFE600",
                "line2": "RAYQUAZA C LV.X",
                "line2_color": "#FFFFFF",
                "line3": "PSA 10 POP NEAR ZERO",
                "line3_color": "#00FF66"
            },
            {
                "tag": "SALES SQUEEZE",
                "img_url": "https://images.pokemontcg.io/dp7/103_hires.png",
                "crop_mode": "center",
                "motion": "zoom_in",
                "line1": "STORMFRONT & DP",
                "line1_color": "#FFE600",
                "line2": "30-DAY SALES VOLUME",
                "line2_color": "#FFFFFF",
                "line3": "EXPLODING OVER 400%",
                "line3_color": "#00FF66"
            },
            {
                "tag": "MARKET VERDICT",
                "img_url": "https://images.pokemontcg.io/pl1/128_hires.png",
                "crop_mode": "art_box",
                "motion": "pan_left",
                "line1": "RAW SUPPLY DRIED",
                "line1_color": "#FFE600",
                "line2": "THE NEXT RETRO VINTAGE",
                "line2_color": "#FFFFFF",
                "line3": "AUCTION SQUEEZE",
                "line3_color": "#00FF66"
            }
        ],
        "caption_full": (
            "🚨 MARKET ALERT | PLATINUM ERA LV.X IS MOVING FAST!\n\n"
            "Between 2007 and 2009, Platinum and DP sets introduced iconic silver-border Level X holos.\n\n"
            "With PSA 10 populations in the single digits, collectors and investors are aggressively absorbing all raw and graded supply across the market.\n\n"
            "Are Lv.X cards the most undervalued era in vintage Pokémon? Drop your comments below! 👇\n\n"
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

# --- DYNAMIC AUTO-FIT TYPOGRAPHY (Auto scales to canvas margins) ---
def draw_autofit_text(draw, text, y, max_w=980, target_size=155, min_size=55, fill="white", stroke_fill="#000000", stroke_width=8):
    if not text:
        return y

    curr_size = target_size
    font = get_font(curr_size)

    # Automatically step down font size until the text fits inside max_w
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

# --- DYNAMIC READING PACE CALCULATOR ---
def calculate_reading_duration(scene):
    # Count total words in lines
    words = sum(len(scene.get(f"line{i}", "").split()) for i in [1, 2, 3])
    # Base 1.8s + 0.28s per word, bounded between 2.4s and 4.2s
    calc_dur = 1.8 + (words * 0.28)
    return round(max(2.4, min(calc_dur, 4.2)), 2)

# --- IMAGE PREPARATION ---
def prepare_scene_base(img_url, crop_mode, out_path):
    pdata = requests.get(img_url, headers=API_HEADERS).content
    with open("temp_raw.png", "wb") as f:
        f.write(pdata)
    raw = Image.open("temp_raw.png").convert("RGB")
    iw, ih = raw.size

    canvas = Image.new("RGB", (W, H), (10, 10, 14))

    if crop_mode == "art_box":
        crop_box = (int(iw * 0.08), int(ih * 0.12), int(iw * 0.92), int(ih * 0.65))
        cropped = raw.crop(crop_box)
        cropped = cropped.resize((W, 1220), Image.Resampling.LANCZOS)
        canvas.paste(cropped, (0, 0))
    elif crop_mode == "slab_top":
        crop_box = (0, 0, iw, int(ih * 0.60))
        cropped = raw.crop(crop_box)
        cropped = cropped.resize((W, 1220), Image.Resampling.LANCZOS)
        canvas.paste(cropped, (0, 0))
    else:
        raw.thumbnail((1020, 1180), Image.Resampling.LANCZOS)
        rw, rh = raw.size
        canvas.paste(raw, ((W - rw) // 2, 20))

    # Dark gradient fade on bottom of image for crystal clear text overlay
    draw = ImageDraw.Draw(canvas)
    for y in range(980, 1260):
        t = (y - 980) / 280
        alpha = int(255 * t)
        draw.line([(0, y), (W, y)], fill=(10, 10, 14, alpha))

    canvas.save(out_path)

# --- OVERLAY BUILDER WITH AUTO-FITTING ---
def create_story_overlay(scene, out_path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

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

    # Stacked Bebas Headlines with Auto-Fitting
    has_3 = bool(scene.get("line3"))
    start_target = 142 if has_3 else 178

    y_start = ay + ah + 16
    y_start = draw_autofit_text(draw, scene.get("line1", ""), y_start, max_w=980, target_size=start_target, fill=scene.get("line1_color", "#FFFFFF"))
    y_start = draw_autofit_text(draw, scene.get("line2", ""), y_start, max_w=980, target_size=start_target, fill=scene.get("line2_color", "#FFFFFF"))
    if has_3:
        draw_autofit_text(draw, scene.get("line3", ""), y_start, max_w=980, target_size=start_target, fill=scene.get("line3_color", "#00FF66"))

    img.save(out_path)

# --- NEWSLETTER CTA SLIDE ---
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

# --- FFMPEG LIVE-ACTION DYNAMIC PACING COMPILER ---
def compile_live_action_reel(story, output_mp4="pokepulse_reel.mp4"):
    scene_vids = []
    total_duration = 0.0

    for idx, sc in enumerate(story["scenes"]):
        base_img = f"base_{idx+1}.png"
        over_img = f"over_{idx+1}.png"
        out_vid = f"scene_{idx+1}.mp4"

        # Dynamically calculate reading time based on word count
        dur = calculate_reading_duration(sc)
        total_duration += dur
        frames_count = int(dur * 30)

        print(f"Generating scene {idx+1} (Duration {dur}s): {sc['line1']}...")
        prepare_scene_base(sc["img_url"], sc["crop_mode"], base_img)
        create_story_overlay(sc, over_img)

        # Dynamic motion zoom / pan matched to exact calculated duration
        if sc["motion"] == "zoom_in":
            filter_str = (
                f"[0:v]scale=8000:-1,zoompan=z='min(zoom+0.0016,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames_count}:s=1080x1920:fps=30[bg];"
                "[bg][1:v]overlay=0:0[out]"
            )
        elif sc["motion"] == "pan_right":
            filter_str = (
                f"[0:v]scale=8000:-1,zoompan=z='1.10':x='(on/{frames_count})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames_count}:s=1080x1920:fps=30[bg];"
                "[bg][1:v]overlay=0:0[out]"
            )
        else:
            filter_str = (
                f"[0:v]scale=8000:-1,zoompan=z='1.10':x='(1-on/{frames_count})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames_count}:s=1080x1920:fps=30[bg];"
                "[bg][1:v]overlay=0:0[out]"
            )

        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", base_img, "-i", over_img,
            "-filter_complex", filter_str,
            "-map", "[out]", "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", out_vid
        ]
        subprocess.run(cmd, check=True)
        scene_vids.append(out_vid)

    # Scene 5: Newsletter CTA (Fixed 2.8s outro)
    cta_dur = 2.8
    total_duration += cta_dur
    print(f"Generating Scene 5: Newsletter CTA ({cta_dur}s)...")
    make_cta_slide("f_cta.png")
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-t", str(cta_dur), "-i", "f_cta.png",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "scene_cta.mp4"
    ], check=True)
    scene_vids.append("scene_cta.mp4")

    with open("playlist.txt", "w") as f:
        for v in scene_vids:
            f.write(f"file '{v}'\n")

    # Broadcast Audio Muxing
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
            f"-i", f"sine=frequency=130:duration={total_duration}",
            "-c:a", "libmp3lame", "-b:a", "192k", audio_file
        ], check=True)

    fade_start = round(total_duration - 1.5, 2)
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-i", audio_file,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", f"[1:a]afade=t=out:st={fade_start}:d=1.5[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-t", str(total_duration),
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
    story = random.choice(LIVE_ACTION_STORIES)
    print(f"Producing Dynamic Story Documentary: {story['story_id']}")

    mp4_file = compile_live_action_reel(story, "pokepulse_reel.mp4")

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    publish_content(video_cdn_url, story["caption_full"])
