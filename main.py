import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Canvas: Standard 4:5 Instagram Portrait
W, H = 1080, 1350

# Exact Colors from References
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
ALERT_RED = (229, 9, 20)      # Netflix/PWCC style red
NEON_YELLOW = (255, 230, 0)   # #FFE600
NEON_GREEN = (0, 255, 51)     # #00FF33
NEON_CYAN = (0, 229, 255)     # #00E5FF
HOT_PINK = (255, 20, 147)     # #FF1493

# Auto-download Anton / Impact font to guarantee 1-to-1 bold look
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
FONT_PATH = "Anton-Regular.ttf"

def ensure_font():
    if not os.path.exists(FONT_PATH):
        print("Downloading bold condensed font...")
        r = requests.get(FONT_URL)
        with open(FONT_PATH, "wb") as f:
            f.write(r.content)

def get_fitted_font(text: str, target_width: int, max_font_size: int = 220):
    """Dynamically scales font so every line fills the exact width of the frame."""
    ensure_font()
    size = max_font_size
    font = ImageFont.truetype(FONT_PATH, size)
    while font.getlength(text) > target_width and size > 30:
        size -= 2
        font = ImageFont.truetype(FONT_PATH, size)
    return font, size

def build_viral_cover(
    card_img_url: str,
    badge_text: str,         # e.g. "AUCTION ALERT" or "TRENDING"
    lines: list,             # List of tuples: [("TEXT", COLOR), ...]
    output_path: str = "test_cover.png"
):
    ensure_font()
    canvas = Image.new("RGBA", (W, H), BLACK)

    # 1. Fetch & Scale Card/Slab Artwork (Upper 62% of the frame)
    if card_img_url.startswith("http"):
        resp = requests.get(card_img_url)
        card = Image.open(BytesIO(resp.content)).convert("RGBA")
    else:
        card = Image.open(card_img_url).convert("RGBA")

    # Fit card into upper portion
    max_card_h = int(H * 0.62)
    aspect = card.width / card.height
    scaled_w = int(max_card_h * aspect)
    card_resized = card.resize((scaled_w, max_card_h), Image.Resampling.LANCZOS)
    
    # Center horizontally, place near top
    card_x = (W - scaled_w) // 2
    canvas.paste(card_resized, (card_x, 30), card_resized)

    # 2. Fade to Pure Black starting around the bottom of the card
    gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient)
    fade_start = int(H * 0.44)
    fade_end = int(H * 0.60)
    for y in range(fade_start, H):
        if y < fade_end:
            alpha = int(255 * ((y - fade_start) / (fade_end - fade_start)))
        else:
            alpha = 255
        g_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

    canvas = Image.alpha_composite(canvas, gradient)
    draw = ImageDraw.Draw(canvas)

    # 3. Draw Badge (Centered Red Box with White Text)
    if badge_text:
        badge_font = ImageFont.truetype(FONT_PATH, 42)
        bw = badge_font.getlength(badge_text)
        pad_x = 24
        pad_y = 12
        box_w = bw + (pad_x * 2)
        box_h = 56
        badge_x = (W - box_w) // 2
        badge_y = int(H * 0.58)

        # Solid sharp red rectangle
        draw.rectangle(
            [badge_x, badge_y, badge_x + box_w, badge_y + box_h],
            fill=ALERT_RED
        )
        draw.text((badge_x + pad_x, badge_y + 4), badge_text, font=badge_font, fill=WHITE)
        current_y = badge_y + box_h + 10
    else:
        current_y = int(H * 0.62)

    # 4. Render Stacked Lines (Each line auto-scaled to fill 92% of the screen width)
    TARGET_TEXT_WIDTH = int(W * 0.92) # 993 pixels wide

    for text, color in lines:
        font, font_size = get_fitted_font(text, TARGET_TEXT_WIDTH)
        tw = font.getlength(text)
        tx = (W - tw) // 2
        
        # Heavy black drop shadow for extreme punch
        shadow_offset = max(3, font_size // 30)
        draw.text((tx + shadow_offset, current_y + shadow_offset), text, font=font, fill=BLACK)
        draw.text((tx - 1, current_y), text, font=font, fill=BLACK)
        draw.text((tx + 1, current_y), text, font=font, fill=BLACK)
        
        # Main Text
        draw.text((tx, current_y), text, font=font, fill=color)

        # Tight line spacing matching the reference screenshots
        current_y += int(font_size * 0.96)

    canvas.convert("RGB").save(output_path, quality=98)
    print(f"Generated 1:1 Cover -> {output_path}")

# -------------------------------------------------------------
# Test run replicating the exact Gold Star / CGC Grails reference
# -------------------------------------------------------------
if __name__ == "__main__":
    sample_img = "https://images.pokemontcg.io/ex10/105_hires.png" # Gold Star Latias
    build_viral_cover(
        card_img_url=sample_img,
        badge_text="AUCTION ALERT",
        lines=[
            ("GOLD STAR", NEON_YELLOW),
            ("CGC GRAILS", WHITE),
            ("ENDING TONIGHT!", NEON_GREEN)
        ],
        output_path="test_cover.png"
    )
