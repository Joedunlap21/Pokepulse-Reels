import os
import random
import time
import cloudinary
import cloudinary.uploader

# Cloudinary configuration from GitHub Secrets
cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL")
)

from PIL import Image, ImageDraw, ImageFont
import requests

API_HEADERS = {"User-Agent": "Mozilla/5.0 (CardStax/PokePulse News Agent)"}

# --- VIRAL BREAKING NEWS STORIES VAULT ---
# Each story: Tag, Headline, Subtitle, Hero Image URL, Slide 2 Content, Slide 3 Content
VIRAL_NEWS_STORIES = [
    {
        "tag": "MARKET ALERT",
        "headline": "PRISMATIC EVOLUTIONS CHAOS",
        "subtitle": "PRE-ORDERS SELL OUT IN SECONDS ACROSS ALL RETAILERS",
        "hero_img": "https://images.pokemontcg.io/sv8pt5/161_hires.png",  # Eevee / Prismatic highlight
        "slide2": {
            "title": "WHAT JUST HAPPENED?",
            "bullets": [
                "Allocations slashed by up to 60% for local game stores nationwide.",
                "Bots swept major retail drops within 15 seconds of launch.",
                "Booster bundles and ETBs are already hitting 2.5x MSRP on secondary markets.",
                "Collectors are comparing this frenzy to the peak of 2021 Evolving Skies."
            ]
        },
        "slide3": {
            "title": "MARKET IMPACT & FORECAST",
            "bullets": [
                "Expect extreme opening week volatility before reprint waves arrive.",
                "Graded Eeveelution SIRs projected to open at record-breaking modern highs.",
                "Market sentiment: DO NOT pay 3x scalper prices during release week.",
                "Follow PokéPulse for real-time restock pings and live floor alerts."
            ]
        }
    },
    {
        "tag": "AUCTION RECORD",
        "headline": "MOONBREON HITS ALL-TIME HIGH",
        "subtitle": "PSA 10 SHATTERS CEILING AS RAW SUPPLY DISAPPEARS",
        "hero_img": "https://images.pokemontcg.io/swsh7/215_hires.png",
        "slide2": {
            "title": "THE NUMBERS DON'T LIE",
            "bullets": [
                "PSA 10 copies just closed over 1,400 USD across multiple verified auction houses.",
                "Raw copies in mint condition are virtually extinct under 800 USD.",
                "Evolving Skies sealed booster boxes officially crossing 750 USD per box.",
                "Population growth in PSA 10 has slowed significantly due to harsh grading."
            ]
        },
        "slide3": {
            "title": "BUY, SELL, OR HOLD?",
            "bullets": [
                "Modern grail status is now firmly cemented alongside Gold Stars.",
                "Short term: Price consolidation likely after this aggressive breakout.",
                "Long term: The definitive face card of the entire Sword & Shield era.",
                "Recommendation: Hold PSA 10s; take profits only if pivoting to vintage."
            ]
        }
    },
    {
        "tag": "BREAKING NEWS",
        "headline": "TEAM ROCKET EXPANSION LEAKED",
        "subtitle": "DARK POKEMON RETURN IN UPCOMING 2026 SPECIAL SET",
        "hero_img": "https://images.pokemontcg.io/sv8/238_hires.png",
        "slide2": {
            "title": "LEAK DETAILS CONFIRMED",
            "bullets": [
                "Trademark filings in Japan reveal 'The Glory of Team Rocket'.",
                "Dark Charizard and Dark Mewtwo Special Illustration Rares rumored.",
                "First main-series Dark Pokémon mechanic introduced in over a decade.",
                "Expected release schedule targets early fall international rollout."
            ]
        },
        "slide3": {
            "title": "COLLECTOR REACTION",
            "bullets": [
                "Nostalgia premium: Original Team Rocket (2000) vintage holos surging.",
                "Rocket's Mewtwo and Dark Dragonite seeing immediate market pickups.",
                "Anticipated to be the single most printed and hoarded set of the year.",
                "Full breakdown drops in this Sunday's PokéPulse Market Report."
            ]
        }
    }
]


# --- AUTO-FIT FONT ENGINE ---
def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "Arial.ttf"
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def draw_autofit_text(draw, text, box, max_font_size=80, min_font_size=18, fill="white", bold=True, align="center"):
    x1, y1, x2, y2 = box
    max_w = x2 - x1
    max_h = y2 - y1

    curr_size = max_font_size
    font = get_font(curr_size, bold=bold)

    while curr_size > min_font_size:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if w <= max_w and h <= max_h:
            break
        curr_size -= 2
        font = get_font(curr_size, bold=bold)

    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    if align == "center":
        x = x1 + (max_w - w) / 2 - bbox[0]
    elif align == "left":
        x = x1 - bbox[0]
    else:
        x = x2 - w - bbox[0]

    y = y1 + (max_h - h) / 2 - bbox[1]
    draw.text((x, y), text, fill=fill, font=font)
    return font


# --- SLIDE BUILDERS (NEWS CAROUSEL) ---

def make_news_cover_slide(story, hero_img_path, output_path="slide_1_cover.jpg"):
    """Slide 1: High-impact Viral Clickbait Cover."""
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), (10, 12, 16))
    draw = ImageDraw.Draw(img)

    # Red Alert Pill
    pill_w, pill_h = 440, 56
    pill_x1 = (W - pill_w) // 2
    draw.rounded_rectangle([pill_x1, 70, pill_x1 + pill_w, 70 + pill_h], radius=28, fill="#E50914")
    draw_autofit_text(draw, story["tag"], (pill_x1, 70, pill_x1 + pill_w, 70 + pill_h), max_font_size=32, min_font_size=20, fill="#FFFFFF", bold=True)

    # Big Headline
    draw_autofit_text(draw, story["headline"].upper(), (50, 145, W - 50, 260), max_font_size=82, min_font_size=36, fill="#FFE600", bold=True)

    # Subtitle Bar
    draw_autofit_text(draw, story["subtitle"], (50, 270, W - 50, 325), max_font_size=28, min_font_size=18, fill="#00FF66", bold=True)

    # Hero Visual
    if os.path.exists(hero_img_path):
        card = Image.open(hero_img_path).convert("RGBA")
        card.thumbnail((660, 750), Image.Resampling.LANCZOS)
        cw, ch = card.size
        cx = (W - cw) // 2
        cy = 360
        draw.rounded_rectangle([cx - 10, cy - 6, cx + cw + 10, cy + ch + 14], radius=20, fill=(0, 0, 0))
        img.paste(card, (cx, cy), mask=card.split()[3])

    # Bottom Callout / Branding
    draw.line([(50, 1180), (W - 50, 1180)], fill="#2D3748", width=2)
    draw_autofit_text(draw, "@CARD.STAX", (50, 1205, 400, 1270), max_font_size=32, min_font_size=20, fill="#A0AEC0", bold=True, align="left")
    draw_autofit_text(draw, "SWIPE TO READ 👉", (W - 400, 1205, W - 50, 1270), max_font_size=32, min_font_size=20, fill="#FFE600", bold=True, align="right")

    img.save(output_path, quality=95)


def make_news_info_slide(story_headline, slide_info, slide_num, output_path):
    """Slides 2 & 3: Deep-dive News Breakdown with Clean Bullet Cards."""
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), (10, 12, 16))
    draw = ImageDraw.Draw(img)

    # Top Tag
    pill_w, pill_h = 320, 52
    draw.rounded_rectangle([60, 60, 60 + pill_w, 60 + pill_h], radius=26, fill="#E50914")
    draw_autofit_text(draw, f"REPORT PART {slide_num - 1}", (60, 60, 60 + pill_w, 60 + pill_h), max_font_size=28, min_font_size=18, fill="#FFFFFF", bold=True)

    # Slide Section Title
    draw_autofit_text(draw, slide_info["title"].upper(), (60, 135, W - 60, 215), max_font_size=56, min_font_size=28, fill="#FFE600", bold=True, align="left")

    # Clean Content Cards for Bullets
    bullets = slide_info.get("bullets", [])
    start_y = 240
    card_gap = 20
    available_h = 900
    card_h = (available_h - (len(bullets) - 1) * card_gap) // len(bullets)

    for i, b_text in enumerate(bullets):
        y1 = start_y + i * (card_h + card_gap)
        y2 = y1 + card_h
        
        # Dark Card Box
        draw.rounded_rectangle([60, y1, W - 60, y2], radius=16, fill="#161B22", outline="#30363D", width=2)

        # Neon Accent Pill
        draw.rounded_rectangle([80, y1 + 25, 92, y2 - 25], radius=6, fill="#00FF66")

        # Auto-fit Bullet Prose
        draw_autofit_text(draw, b_text, (110, y1 + 15, W - 90, y2 - 15), max_font_size=32, min_font_size=18, fill="#FFFFFF", bold=False, align="left")

    # Bottom Branding & Swipe
    draw.line([(60, 1180), (W - 60, 1180)], fill="#2D3748", width=2)
    draw_autofit_text(draw, "@CARD.STAX", (60, 1205, 400, 1270), max_font_size=32, min_font_size=20, fill="#A0AEC0", bold=True, align="left")
    
    next_text = "SWIPE NEXT 👉" if slide_num == 2 else "FINAL SLIDE 👉"
    draw_autofit_text(draw, next_text, (W - 400, 1205, W - 60, 1270), max_font_size=32, min_font_size=20, fill="#FFE600", bold=True, align="right")

    img.save(output_path, quality=95)


# --- UPLOAD & INSTAGRAM PUBLISHING ---
def upload_to_cdn(file_path):
    try:
        res = cloudinary.uploader.upload(file_path, folder="pokepulse_news")
        return res.get("secure_url")
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None

def post_carousel(image_urls, caption):
    ig_user_id = os.getenv("IG_USER_ID")
    access_token = os.getenv("IG_ACCESS_TOKEN")
    if not ig_user_id or not access_token:
        print("Error: Missing IG_USER_ID or IG_ACCESS_TOKEN.")
        return

    print("Step 1: Uploading carousel item containers...")
    item_ids = []
    for u in image_urls:
        r = requests.post(f"https://graph.facebook.com/v21.0/{ig_user_id}/media", data={
            "image_url": u,
            "is_carousel_item": "true",
            "access_token": access_token
        }).json()
        if "id" in r:
            item_ids.append(r["id"])
        else:
            print("Error creating item container:", r)
        time.sleep(2)

    if len(item_ids) != len(image_urls):
        print(f"Aborted: expected {len(image_urls)} items, created {len(item_ids)}")
        return

    print("Step 2: Creating carousel container...")
    c_res = requests.post(f"https://graph.facebook.com/v21.0/{ig_user_id}/media", data={
        "media_type": "CAROUSEL",
        "caption": caption,
        "children": ",".join(item_ids),
        "access_token": access_token
    }).json()

    if "id" not in c_res:
        print("Error creating carousel container:", c_res)
        return

    time.sleep(10)

    print("Step 3: Publishing live to Instagram...")
    pub_res = requests.post(f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish", data={
        "creation_id": c_res["id"],
        "access_token": access_token
    }).json()

    if "id" in pub_res:
        print(f"Success! Carousel live on @card.stax: {pub_res['id']}")
    else:
        print("Publishing error:", pub_res)


# --- MAIN PIPELINE ---
if __name__ == "__main__":
    # Pick a viral news story
    story = random.choice(VIRAL_NEWS_STORIES)
    print(f"Generating News Carousel: {story['headline']}")

    # 1. Slide 1 (Viral Cover)
    hero_local = "hero_news.png"
    h_data = requests.get(story["hero_img"], headers=API_HEADERS).content
    with open(hero_local, "wb") as f:
        f.write(h_data)
    make_news_cover_slide(story, hero_local, "slide_1_cover.jpg")

    # 2. Slide 2 (Part 1: What Happened)
    make_news_info_slide(story["headline"], story["slide2"], 2, "slide_2_info.jpg")

    # 3. Slide 3 (Part 2: Market Impact)
    make_news_info_slide(story["headline"], story["slide3"], 3, "slide_3_impact.jpg")

    # 4. Slide 4 (Final Custom Newsletter Graphic)
    newsletter_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    n_data = requests.get(newsletter_url, headers=API_HEADERS).content
    with open("slide_4_newsletter.png", "wb") as f:
        f.write(n_data)

    slide_files = [
        "slide_1_cover.jpg",
        "slide_2_info.jpg",
        "slide_3_impact.jpg",
        "slide_4_newsletter.png"
    ]

    print("Uploading 4 news slides to Cloudinary...")
    urls = []
    for sf in slide_files:
        u = upload_to_cdn(sf)
        if u:
            urls.append(u)

    caption = (
        f"🚨 POKÉPULSE MARKET ALERT | {story['headline']} 🚨\n\n"
        f"{story['subtitle']}\n\n"
        f"Swipe through for the full breakdown and collector forecast! 👉\n\n"
        f"📬 Never miss breaking market moves—join the free PokéPulse Newsletter (Link in bio!)\n\n"
        f"#PokemonCards #PokemonTCG #CardStax #PokePulse #PokemonNews"
    )

    if len(urls) == 4:
        post_carousel(urls, caption)
    else:
        print(f"Error: expected 4 slides, only uploaded {len(urls)}.")
