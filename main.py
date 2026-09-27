import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Canvas: 1080x1350 (Instagram 4:5 Portrait)
W, H = 1080, 1350

# Colors matching your screenshot
BG_DARK = (10, 10, 14)
NEON_CYAN = (0, 229, 255)    # "SECRETMUDKIP" cyan
NEON_YELLOW = (255, 230, 0)  # "ENERGY" yellow
NEON_GREEN = (0, 255, 102)   # "MAJOR GRAILS" / "$72,000+ CARD" green
ALERT_RED = (220, 20, 60)    # Red pill badge
WHITE = (255, 255, 255)

def get_font(size):
    font_paths = [
        "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arialbd.ttf"
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    return ImageFont.load_default()

def create_story_cover(
    bg_image_url: str,
    badge_text: str,          # e.g., "NEW CONSIGNOR" or "STORY ALERT"
    line1_text: str,          # e.g., "SECRETMUDKIP" or "A 6-YEAR-OLD"
    line1_color: tuple,       # e.g., NEON_CYAN or WHITE
    line2_text: str,          # e.g., "IS SELLING" or "DESIGNED THIS"
    line2_color: tuple,       # e.g., WHITE
    line3_text: str,          # e.g., "MAJOR GRAILS" or "$72,000+ CARD"
    line3_color: tuple,       # e.g., NEON_GREEN
    output_path: str = "viral_cover.png"
):
    # 1. Load Background / Character Image
    if bg_image_url.startswith("http"):
        resp = requests.get(bg_image_url)
        bg = Image.open(BytesIO(resp.content)).convert("RGBA")
    else:
        bg = Image.open(bg_image_url).convert("RGBA")

    # Crop & scale background to fill 1080x1350
    bg_aspect = bg.width / bg.height
    target_aspect = W / H
    if bg_aspect > target_aspect:
        new_h = H
        new_w = int(H * bg_aspect)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - W) // 2
        bg = bg.crop((left, 0, left + W, H))
    else:
        new_w = W
        new_h = int(W / bg_aspect)
        bg = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
        top = (new_h - H) // 2
        bg = bg.crop((0, top, W, top + H))

    # 2. Add Dark Gradient at the Bottom for Text Contrast
    gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient)
    
    # Fade from transparent to solid dark starting around 50% height
    for y in range(int(H * 0.50), H):
        factor = ((y - H * 0.50) / (H * 0.50)) ** 1.4
        alpha = int(255 * factor)
        g_draw.line([(0, y), (W, y)], fill=(5, 5, 10, min(255, alpha)))

    canvas = Image.alpha_composite(bg, gradient)
    draw = ImageDraw.Draw(canvas)

    # 3. Draw Red Pill Badge
    font_badge = get_font(32)
    badge_w = font_badge.getlength(badge_text) + 36
    badge_h = 48
    badge_x = (W - badge_w) // 2
    badge_y = int(H * 0.63)

    draw.rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        fill=ALERT_RED
    )
    draw.text((badge_x + 18, badge_y + 8), badge_text, font=font_badge, fill=WHITE)

    # 4. Line 1 (Hook Text)
    font_line1 = get_font(110)
    w1 = font_line1.getlength(line1_text)
    draw.text(((W - w1) // 2, badge_y + 60), line1_text, font=font_line1, fill=line1_color)

    # 5. Line 2 (Action / Subject)
    font_line2 = get_font(110)
    w2 = font_line2.getlength(line2_text)
    draw.text(((W - w2) // 2, badge_y + 175), line2_text, font=font_line2, fill=line2_color)

    # 6. Line 3 (Bottom Climax Highlight)
    font_line3 = get_font(95)
    w3 = font_line3.getlength(line3_text)
    draw.text(((W - w3) // 2, badge_y + 290), line3_text, font=font_line3, fill=line3_color)

    canvas.convert("RGB").save(output
