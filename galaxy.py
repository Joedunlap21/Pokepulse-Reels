"""
Galaxy backgrounds for every PokePulse post (Oct 16, Joe: no black backgrounds).

galaxy(W, H, seed) -> PIL RGB image: deep purple/blue space, nebula clouds, a star field,
4-point sparkles and a few glowing "energy orbs" in TCG energy-type colours.
Original art only: no Pokemon characters or Poke Ball designs are drawn.
Results are cached, so calling it once per frame/scene is cheap.
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# nebula colour sets (each run picks one, by seed)
PALETTES = [
    [(123, 63, 228), (46, 197, 255), (255, 79, 163)],    # violet / cyan / pink
    [(90, 70, 255), (255, 92, 168), (255, 200, 80)],     # indigo / pink / gold
    [(40, 170, 255), (140, 80, 255), (60, 230, 200)],    # blue / purple / teal
    [(200, 60, 230), (70, 120, 255), (255, 140, 90)],    # magenta / blue / orange
]
# Fire, Water, Grass, Lightning, Psychic energy colours for the glowing orbs
ENERGY = [(255, 90, 60), (60, 160, 255), (90, 220, 110), (255, 215, 40), (200, 100, 255)]

_cache = {}
# one galaxy look per post (set GALAXY_SEED to repeat a look)
RUN_SEED = int(os.getenv("GALAXY_SEED", "").strip() or random.randrange(1_000_000))


def _noise(w, h, rng, octaves=(4, 8, 16, 32, 64)):
    """Smooth fractal noise in 0..1, built from upscaled random grids (fast, no extra deps)."""
    acc = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in octaves:
        gw, gh = max(2, int(o * w / max(w, h)) + 1), max(2, int(o * h / max(w, h)) + 1)
        g = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8), "L")
        acc += np.asarray(g.resize((w, h), Image.BICUBIC), np.float32) / 255 * amp
        total += amp
        amp *= 0.55
    acc /= total
    return (acc - acc.min()) / max(1e-6, acc.max() - acc.min())


def galaxy(W, H, seed=None):
    seed = RUN_SEED if seed is None else seed
    key = (W, H, seed)
    if key in _cache:
        return _cache[key].copy()
    rng = np.random.default_rng(seed)
    r = random.Random(seed)
    pal = PALETTES[seed % len(PALETTES)]

    # work at half size for the soft layers, then upscale
    w, h = W // 2, H // 2
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    base = np.zeros((h, w, 3), np.float32)
    top, bottom = np.array([22, 12, 58], np.float32), np.array([44, 14, 74], np.float32)
    base += top * (1 - yy)[..., None] + bottom * yy[..., None]   # never black: indigo -> plum

    # nebula clouds: three coloured noise layers, made wispy with a power curve
    for k, col in enumerate(pal):
        n = _noise(w, h, rng) ** (3.2 + 0.5 * k)
        mask = _noise(w, h, rng, octaves=(2, 3)) ** 2.2             # where this colour lives
        a = np.clip(n * mask * 2.6, 0, 1)[..., None] * 0.75
        base = base * (1 - a) + np.array(col, np.float32) * a
    # a bright galactic band across the frame
    ang = r.uniform(-0.5, 0.5)
    xs = np.linspace(-1, 1, w, dtype=np.float32)[None, :]
    ys = np.linspace(-1, 1, h, dtype=np.float32)[:, None] * (h / w)
    d = np.abs(ys * math.cos(ang) - xs * math.sin(ang) - r.uniform(-0.3, 0.3))
    band = np.exp(-(d / 0.22) ** 2) * (0.5 + 0.5 * _noise(w, h, rng))
    base += band[..., None] * np.array([110, 80, 160], np.float32) * 0.35
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(1.5))

    # glowing energy orbs (soft, out of focus, like distant planets)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for col in r.sample(ENERGY, 3):
        rad = r.randint(int(W * 0.03), int(W * 0.07))
        cx, cy = r.randint(0, W), r.randint(0, H)
        gd.ellipse([cx - rad * 3, cy - rad * 3, cx + rad * 3, cy + rad * 3], fill=col + (45,))
        gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col + (200,))
        gd.ellipse([cx - rad // 3, cy - rad // 3, cx + rad // 3, cy + rad // 3], fill=(255, 255, 255, 220))
    glow = glow.filter(ImageFilter.GaussianBlur(W // 60))
    img = Image.alpha_composite(img.convert("RGBA"), glow)

    # star field
    stars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stars)
    for _ in range(int(W * H / 700)):
        x, y = r.randrange(W), r.randrange(H)
        b = r.randint(150, 255)
        tint = r.choice([(255, 255, 255), (200, 225, 255), (255, 235, 200)])
        c = tuple(int(t * b / 255) for t in tint) + (b,)
        s = r.random()
        if s < 0.8:
            sd.point((x, y), fill=c)
        else:
            sd.ellipse([x - 1, y - 1, x + 2, y + 2], fill=c)
    halo = stars.filter(ImageFilter.GaussianBlur(2.5))
    img = Image.alpha_composite(img, halo)
    img = Image.alpha_composite(img, stars)

    # a few 4-point sparkles
    sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    spd = ImageDraw.Draw(sp)
    for _ in range(max(6, W * H // 160000)):
        x, y, L = r.randrange(W), r.randrange(H), r.randint(14, 38)
        for dx, dy in ((L, 0), (0, L)):
            spd.line([(x - dx, y - dy), (x + dx, y + dy)], fill=(255, 255, 255, 230), width=2)
        spd.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 255, 255, 255))
    img = Image.alpha_composite(img, sp.filter(ImageFilter.GaussianBlur(4)))
    img = Image.alpha_composite(img, sp.filter(ImageFilter.GaussianBlur(0.8)))

    out = img.convert("RGB")
    _cache[key] = out
    return out.copy()


def tint_fade(W, H, start_y, end_y, max_alpha=170, colour=(30, 12, 60)):
    """Soft purple (not black) wash from start_y down, so captions stay readable."""
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for y in range(start_y, H):
        a = min(max_alpha, int(max_alpha * (y - start_y) / max(1, end_y - start_y)))
        sd.line([(0, y), (W, y)], fill=colour + (a,))
    return shade


if __name__ == "__main__":
    import sys
    galaxy(1080, 1920, int(sys.argv[1]) if len(sys.argv) > 1 else 1).save("galaxy_preview.jpg", quality=90)
