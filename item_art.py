"""
Pictures for the things the voice talks about ("8 booster packs", "a coin", "6 dice", "65 sleeves"...).
Built from the product's own official art + set logo so every picture belongs to THAT product.
"""
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageEnhance

WHITE = (255, 255, 255, 255)


def _cover(img, w, h):
    img = img.convert("RGB")
    s = max(w / img.width, h / img.height)
    img = img.resize((max(1, int(img.width * s) + 1), max(1, int(img.height * s) + 1)), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def _round(img, r):
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=r, fill=255)
    out = img.convert("RGBA")
    out.putalpha(m)
    return out


def _gloss(img, strength=90):
    """Diagonal shine like a foil wrapper."""
    w, h = img.size
    g = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(g)
    for k in range(-h, w, 6):
        a = int(strength * max(0, 1 - abs((k - w * 0.35)) / (w * 0.25)))
        d.line([(k, 0), (k + h, h)], fill=a, width=6)
    shine = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    shine.putalpha(Image.fromarray(np.minimum(np.array(g), np.array(img.split()[3]))))
    out = img.copy()
    out.alpha_composite(shine)
    return out


def _main_color(img):
    small = img.convert("RGB").resize((40, 40))
    a = np.array(small).reshape(-1, 3).astype(int)
    sat = a.max(1) - a.min(1)
    pick = a[sat > np.percentile(sat, 70)]
    c = pick.mean(0) if len(pick) else a.mean(0)
    return tuple(int(x) for x in c)


def _badge(img, text, font_fn):
    """Yellow 'x8' bubble in the top-right corner, sized to the picture."""
    from_txt = font_fn(text)
    pad = 26
    s = max(from_txt.width, from_txt.height) + pad
    want = int(max(img.width, img.height) * 0.26)
    if s < want:
        k = want / s
        from_txt = from_txt.resize((int(from_txt.width * k), int(from_txt.height * k)), Image.LANCZOS)
        s = want
    b = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(b)
    d.ellipse([0, 0, s - 1, s - 1], fill=(255, 232, 20, 255), outline=(0, 0, 0, 255), width=7)
    b.alpha_composite(from_txt, ((s - from_txt.width) // 2, (s - from_txt.height) // 2))
    out = Image.new("RGBA", (img.width + s // 3, img.height + s // 3), (0, 0, 0, 0))
    out.alpha_composite(img, (0, s // 3))
    out.alpha_composite(b, (out.width - s, 0))
    return out


def booster_pack(face, logo=None, w=360, h=620):
    pack = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    body = _cover(face, w - 16, h - 90)
    body = ImageEnhance.Color(body).enhance(1.2)
    pack.alpha_composite(_round(body, 18), (8, 45))
    d = ImageDraw.Draw(pack)
    for y0 in (0, h - 50):                             # crimped foil ends
        d.rectangle([4, y0 + 8, w - 4, y0 + 46], fill=(205, 208, 214, 255))
        for x in range(4, w - 4, 10):
            d.line([(x, y0 + 8), (x, y0 + 46)], fill=(160, 164, 172, 255), width=3)
        tooth = [(x, y0 + (0 if y0 == 0 else 54)) for x in range(4, w - 3, 12)]
        for k, (x, y) in enumerate(tooth[:-1]):
            d.polygon([(x, y0 + (10 if y0 == 0 else 44)), (x + 6, y), (x + 12, y0 + (10 if y0 == 0 else 44))],
                      fill=(205, 208, 214, 255))
    if logo is not None:
        lg = logo.convert("RGBA")
        lg.thumbnail((int(w * 0.8), int(h * 0.22)))
        pack.alpha_composite(lg, ((w - lg.width) // 2, 70))
    return _gloss(pack)


def pack_fan(face, logo, n, font_fn):
    k = max(1, min(n or 3, 5))
    packs = [booster_pack(face, logo) for _ in range(k)]
    W_, H_ = 360 + 150 * (k - 1) + 200, 760
    out = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    mid = (k - 1) / 2
    for i, p in enumerate(packs):
        ang = (i - mid) * 9
        r = p.rotate(-ang, resample=Image.BICUBIC, expand=True)
        x = int(100 + i * 150 + (0 if k > 1 else 0))
        y = int(40 + abs(i - mid) * 22)
        out.alpha_composite(r, (x - (r.width - 360) // 2, y))
    out = out.crop(out.getbbox())
    return _badge(out, f"x{n}", font_fn) if n and n > 1 else out


def coin(face, logo=None, size=520):
    c = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    for r in range(size // 2, 0, -2):                  # gold radial gradient
        t = r / (size / 2)
        col = (int(255 - 70 * t), int(215 - 80 * t), int(70 - 40 * t), 255)
        d.ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], fill=col)
    d.ellipse([10, 10, size - 10, size - 10], outline=(150, 105, 20, 255), width=16)
    d.ellipse([40, 40, size - 40, size - 40], outline=(255, 236, 160, 255), width=5)
    cx = cy = size / 2
    R = size * 0.28                                    # embossed Poke Ball
    d.pieslice([cx - R, cy - R, cx + R, cy + R], 180, 360, fill=(200, 40, 40, 255))
    d.pieslice([cx - R, cy - R, cx + R, cy + R], 0, 180, fill=(250, 245, 230, 255))
    d.rectangle([cx - R, cy - R * 0.1, cx + R, cy + R * 0.1], fill=(60, 40, 10, 255))
    d.ellipse([cx - R * 0.32, cy - R * 0.32, cx + R * 0.32, cy + R * 0.32], fill=(60, 40, 10, 255))
    d.ellipse([cx - R * 0.2, cy - R * 0.2, cx + R * 0.2, cy + R * 0.2], fill=(250, 245, 230, 255))
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(60, 40, 10, 255), width=10)
    return _gloss(c, 70)


def dice(face, logo=None, n=6, font_fn=None):
    def one(color):
        s = 260
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, s - 1, s - 1], radius=46, fill=color + (255,))
        d.rounded_rectangle([10, 10, s - 11, s - 11], radius=40, outline=(255, 255, 255, 90), width=4)
        for (x, y) in [(0.27, 0.27), (0.73, 0.27), (0.5, 0.5), (0.27, 0.73), (0.73, 0.73)]:
            d.ellipse([x * s - 24, y * s - 24, x * s + 24, y * s + 24], fill=(255, 255, 255, 255))
        return _gloss(im, 60)
    col = _main_color(face)
    out = Image.new("RGBA", (760, 560), (0, 0, 0, 0))
    for i, (x, y, a) in enumerate([(40, 220, -14), (420, 260, 11), (230, 20, 4)]):
        dd = one(col if i != 1 else (220, 30, 40)).rotate(a, resample=Image.BICUBIC, expand=True)
        out.alpha_composite(dd, (x, y))
    out = out.crop(out.getbbox())
    return _badge(out, f"x{n}", font_fn) if n and n > 1 and font_fn else out


def sleeves(face, logo=None, n=65, font_fn=None):
    w, h = 400, 560
    col = _main_color(face)
    out = Image.new("RGBA", (w + 160, h + 120), (0, 0, 0, 0))
    art = _cover(face, w - 40, h - 40)
    for i in range(4, -1, -1):
        s = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(s)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=26, fill=col + (255,))
        if i == 0:
            s.alpha_composite(_round(art, 18), (20, 20))
        s = _gloss(s, 50)
        out.alpha_composite(s.rotate(i * 3, resample=Image.BICUBIC, expand=False), (20 + i * 26, 20 + i * 18))
    out = out.crop(out.getbbox())
    return _badge(out, f"x{n}", font_fn) if n and n > 1 and font_fn else out


def deck_box(face, logo=None):
    w, h, dpt = 360, 520, 120
    out = Image.new("RGBA", (w + dpt, h + dpt), (0, 0, 0, 0))
    col = _main_color(face)
    dark = tuple(max(0, int(c * 0.6)) for c in col)
    light = tuple(min(255, int(c * 1.25)) for c in col)
    d = ImageDraw.Draw(out)
    d.polygon([(w, dpt), (w + dpt, 0), (w + dpt, h), (w, h + dpt)], fill=dark + (255,))      # side
    d.polygon([(0, dpt), (dpt, 0), (w + dpt, 0), (w, dpt)], fill=light + (255,))             # top
    front = _cover(face, w, h)
    out.alpha_composite(front.convert("RGBA"), (0, dpt))
    if logo is not None:
        lg = logo.convert("RGBA")
        lg.thumbnail((int(w * 0.8), int(h * 0.25)))
        out.alpha_composite(lg, ((w - lg.width) // 2, dpt + 30))
    return _gloss(out, 60)


def playmat(face, logo=None):
    w, h = 900, 520
    mat = _round(_cover(face, w, h), 40)
    d = ImageDraw.Draw(mat)
    d.rounded_rectangle([8, 8, w - 9, h - 9], radius=34, outline=(30, 30, 30, 255), width=10)
    for x in range(30, w - 30, 22):                      # stitched edge
        d.line([(x, 20), (x + 10, 20)], fill=(240, 240, 240, 255), width=3)
        d.line([(x, h - 21), (x + 10, h - 21)], fill=(240, 240, 240, 255), width=3)
    if logo is not None:
        lg = logo.convert("RGBA")
        lg.thumbnail((int(w * 0.4), int(h * 0.35)))
        mat.alpha_composite(lg, (w - lg.width - 50, 50))
    # slight perspective tilt
    coeffs = _persp((w, h), [(60, 0), (w - 60, 0), (w, h), (0, h)])
    return mat.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)


def _persp(size, dst):
    w, h = size
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, B = [], []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()


def binder(face, logo=None):
    w, h = 460, 600
    out = Image.new("RGBA", (w + 40, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([0, 0, 70, h - 1], radius=24, fill=(30, 30, 30, 255))       # spine
    for y in (120, h // 2, h - 120):
        d.ellipse([22, y - 16, 54, y + 16], fill=(190, 190, 190, 255))
    out.alpha_composite(_round(_cover(face, w - 30, h), 26), (60, 0))
    if logo is not None:
        lg = logo.convert("RGBA")
        lg.thumbnail((int(w * 0.7), int(h * 0.2)))
        out.alpha_composite(lg, (60 + (w - 30 - lg.width) // 2, 40))
    return _gloss(out, 50)


def code_card(face, logo=None):
    w, h = 420, 590
    c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=24, fill=(250, 250, 250, 255), outline=(30, 30, 30, 255), width=6)
    d.rounded_rectangle([20, 20, w - 21, 240], radius=16, fill=(30, 90, 200, 255))
    rnd = random.Random(4)
    x = 50
    while x < w - 50:                                  # barcode
        bw = rnd.choice([3, 4, 6, 8])
        d.rectangle([x, 330, x + bw, 470], fill=(20, 20, 20, 255))
        x += bw + rnd.choice([3, 5, 7])
    if logo is not None:
        lg = logo.convert("RGBA")
        lg.thumbnail((w - 80, 180))
        c.alpha_composite(lg, ((w - lg.width) // 2, 20 + (220 - lg.height) // 2))
    return c


def card_backs(face, logo=None, n=60, font_fn=None):
    """A spread of foil cards (fanned) using the product art as the card fronts."""
    w, h = 300, 420
    k = 5
    out = Image.new("RGBA", (1000, 700), (0, 0, 0, 0))
    art = ImageEnhance.Color(_cover(face, w, h)).enhance(1.3)
    for i in range(k):
        cimg = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
        ImageDraw.Draw(cimg).rounded_rectangle([0, 0, w + 15, h + 15], radius=20, fill=(250, 214, 60, 255))
        cimg.alpha_composite(_round(art, 14), (8, 8))
        cimg = _gloss(cimg, 110)
        r = cimg.rotate((i - 2) * -10, resample=Image.BICUBIC, expand=True)
        out.alpha_composite(r, (120 + i * 140, 60 + abs(i - 2) * 25))
    out = out.crop(out.getbbox())
    return _badge(out, f"x{n}", font_fn) if n and n > 1 and font_fn else out


# keyword -> (builder, uses count)
ITEMS = [
    (r"^(booster|packs?)$", "packs"),
    (r"^(coin|coins)$", "coin"),
    (r"^(dice|die)$", "dice"),
    (r"^sleeves?$", "sleeves"),
    (r"^(deck-?box|box)$", "deckbox"),     # 'deck box' handled via previous word check
    (r"^playmats?$", "playmat"),
    (r"^binders?$", "binder"),
    (r"^code$", "code"),
    (r"^(foil|cards)$", "cards"),
]


def make(kind, face, logo, n, font_fn, out_path):
    if kind == "packs":
        im = pack_fan(face, logo, n, font_fn)
    elif kind == "coin":
        im = coin(face, logo)
    elif kind == "dice":
        im = dice(face, logo, n, font_fn)
    elif kind == "sleeves":
        im = sleeves(face, logo, n, font_fn)
    elif kind == "deckbox":
        im = deck_box(face, logo)
    elif kind == "playmat":
        im = playmat(face, logo)
    elif kind == "binder":
        im = binder(face, logo)
    elif kind == "code":
        im = code_card(face, logo)
    elif kind == "cards":
        im = card_backs(face, logo, n, font_fn)
    else:
        return None
    im.save(out_path)
    return out_path
