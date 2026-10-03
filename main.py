import os
import re
import sys
import html
import time
import glob
import random
import subprocess
from datetime import datetime, timezone, timedelta

import cloudinary
import cloudinary.uploader
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL", "").strip()
)

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
# Uses the IG_USER_ID secret if it's set, otherwise the @card.stax account ID below
IG_USER_ID = os.getenv("IG_USER_ID", "").strip() or "17841472317326348"
GRAPH = "https://graph.facebook.com/v21.0"

MAX_ARTICLE_AGE_DAYS = 10

W, H = 1080, 1920
BG = (10, 10, 14)
YELLOW, WHITE, GREEN, RED = "#FFE600", "#FFFFFF", "#00FF66", "#E50914"
LIME = "#D4FF3A"      # pricecharting-style accent for names / prices
ACCENT = YELLOW       # highlight color for key words in headlines (joinsleeved style)

IMG_BOTTOM = 1110   # art area is 0..IMG_BOTTOM
TAG_Y = 1130        # red tag pill
TEXT_TOP = 1230     # text block starts here
TEXT_BOTTOM = 1860  # and must end above here
TEXT_MAX_W = 960

MAX_SCENE_SECONDS = 3.0   # no picture stays on screen longer than this
CTA_SECONDS = 2.2         # newsletter slide at the end (news-style, readable)

# ---------------------------------------------------------------- fonts

# anton = big heavy headline font (the joinsleeved / pricecharting look)
# mont  = Montserrat ExtraBold for small labels, stats and prices
# bebas = old font, still used by the newsletter CTA slide
_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {
    "bebas": ("BebasNeue.ttf", _GF + "bebasneue/BebasNeue-Regular.ttf"),
    "anton": ("Anton.ttf", _GF + "anton/Anton-Regular.ttf"),
    "mont": ("Montserrat.ttf", _GF + "montserrat/Montserrat%5Bwght%5D.ttf"),
}

def ensure_font():
    for path, url in FONTS.values():
        if not os.path.exists(path):
            try:
                r = requests.get(url, headers=API_HEADERS, timeout=20)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print(f"Font download failed {path}: {e}")

ensure_font()

_font_cache = {}
def get_font(size, face="bebas"):
    key = (face, size)
    if key not in _font_cache:
        try:
            f = ImageFont.truetype(FONTS[face][0], size)
            if face == "mont":
                for name in (b"ExtraBold", "ExtraBold", b"Bold", "Bold"):
                    try:
                        f.set_variation_by_name(name)
                        break
                    except Exception:
                        continue
            _font_cache[key] = f
        except Exception:
            try:
                _font_cache[key] = ImageFont.truetype(FONTS["bebas"][0], size)
            except Exception:
                _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]

def clean_text(t):
    t = html.unescape(t or "")
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-").replace("\xa0", " ")
    # strip emojis / symbols the font can't draw
    t = "".join(ch for ch in t if ord(ch) < 0x2000)
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"\s+([,.!?;:])", r"\1", t)

# ---------------------------------------------------------------- text layout

def text_w(draw, text, font, stroke=0):
    b = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return b[2] - b[0]

def wrap_words(draw, text, font, max_w, stroke):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if text_w(draw, trial, font, stroke) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines

def fit_block(draw, text, max_w, max_h, start=150, min_size=58, max_lines=5):
    """Biggest font size where the whole text wraps inside the box. Never cuts words."""
    size = start
    while True:
        font = get_font(size)
        stroke = max(4, size // 18)
        lines = [l for part in text.split("\n") for l in wrap_words(draw, part, font, max_w, stroke)]
        line_h = int(size * 0.98)
        widest = max(text_w(draw, l, font, stroke) for l in lines)
        parts = text.split("\n")
        one_per_line = len(parts) == 1 or len(lines) == len(parts)  # lists: keep each item on its own line
        if (len(lines) <= max_lines and len(lines) * line_h <= max_h and widest <= max_w and one_per_line) or size <= min_size:
            return font, stroke, lines, line_h
        size -= 4

def draw_lines(draw, lines, font, stroke, line_h, top, colors):
    y = top
    for i, line in enumerate(lines):
        x = (W - text_w(draw, line, font, stroke)) // 2
        draw.text((x, y), line, font=font, fill=colors[i % len(colors)],
                  stroke_fill="#000000", stroke_width=stroke)
        y += line_h
    return y

def calculate_reading_duration(scene):
    words = len(scene.get("text", "").split()) + len(scene.get("sub", "").split())
    # quick: ~0.35s a word, 1.2s minimum, never more than MAX_SCENE_SECONDS per picture
    return round(max(1.2, min(0.6 + words * 0.35, MAX_SCENE_SECONDS)), 2)

# ---------------------------------------------------------------- sources

# The bot rotates topics:  news | drops | sales | bulk | chase
#   news  = latest Pokemon TCG news from the 4 outlets below
#   drops = latest preorder / release / retailer drop article (where, when, price, what's inside)
#   sales = big card sales, PSA 10 / graded auction records
#   bulk  = "Bulk Gold": commons & uncommons from a recent set that are worth real money (TCGplayer prices)
#   chase = most valuable cards in a recent set
SOURCES = [
    {"name": "Pokemon.com", "list": "https://www.pokemon.com/us/news", "base": "https://www.pokemon.com",
     "link_re": r'href="((?:https://www\.pokemon\.com)?/us/news/[a-z0-9\-]+)"',
     "start": "<article", "end": ["</article>"]},
    {"name": "PokeBeach", "list": "https://www.pokebeach.com/", "base": "https://www.pokebeach.com",
     "link_re": r'href="(https://www\.pokebeach\.com/20\d\d/\d\d/[a-z0-9\-]+)/?"',
     "start": "entry-content", "end": ["launched PokeBeach", 'class="author', "is a fansite"]},
    {"name": "PokeGuardian", "list": "https://www.pokeguardian.com/", "base": "https://www.pokeguardian.com",
     "link_re": r'href="(https://www\.pokeguardian\.com/\d+_[a-z0-9\-]+)"',
     "start": "<main", "end": ["</main>"]},
    {"name": "Dexerto", "rss": "https://www.dexerto.com/feed/category/pokemon/", "base": "https://www.dexerto.com",
     "start": "<article", "end": ["</article>"], "max_imgs": 2},  # rest are related-article thumbnails
]
PER_SOURCE = 6

TCG_WORDS = ["tcg", "card", "booster", "elite trainer", "expansion", "promo", "collection", "pack", "prerelease",
             "pokemon center", "psa", "graded", "auction", "tin", "binder", "set list", "pull rate", "illustration rare",
             "special illustration", "bundle", "sealed"]
DROP_WORDS = ["preorder", "pre-order", "now available", "now live", "releases", "release date", "launch", "in stores",
              "restock", "exclusive", "pokemon center", "gamestop", "best buy", "target", "walmart", "costco",
              "elite trainer box", "booster bundle", "booster box", "collection", "tin", "gift with purchase", "msrp"]
SALE_WORDS = ["sold for", "sells for", "sale", "auction", "psa 10", "psa", "gem mint", "graded", "record",
              "most expensive", "million", "bids", "cgc", "bgs"]
# Only these earn the "BREAKING NEWS" tag - a monthly roundup is not breaking news
BREAKING_WORDS = ["revealed", "reveal", "announced", "announces", "leak", "leaked", "first look", "officially",
                  "confirmed", "delayed", "cancelled", "canceled", "recall", "banned", "surprise"]
PRODUCT_WORDS = r"box|bundle|tin|collection|pack|blister|binder|portfolio|deck|premium|chest|case|figure|pin|mini"
RETAILERS = ["Pokemon Center", "GameStop", "Best Buy", "Target", "Walmart", "Costco", "Sam's Club", "Amazon",
             "Barnes & Noble", "Five Below", "Hot Topic", "BoxLunch", "Macy's", "EB Games", "JB Hi-Fi", "Meijer",
             "Walgreens", "CVS", "Dollar General", "McDonald's", "Play! Pokemon Stores", "local game stores"]
MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sept?\.?|Oct\.?|Nov\.?|Dec\.?)"
# Articles for tournament players, not collectors - skip these
NOT_COLLECTOR = ["deck list", "decklist", "deck profile", "deck guide", "regional championship", "regionals",
                 "world championships", "tournament report", "top 8", "top cut", "meta", "standard format",
                 "rotation", "strategy", "matchup", "tier list", "carpe diem", "here, and i am", "writing another article",
                 "pokemon tcg live", "pokemon go", "pokemon unite", "video game", "anime episode"]

JUNK = ["open media", "tap to unmute", "follow along with the video", "this feature may not be available",
        "launched pokebeach", "is a fansite", "follow us", "thank you very much", "patreon", "subscribe",
        "click here", "sign up", "newsletter", "cookie", "yesterday at", "{\"@", "please make sure",
        "we do not know", "no information"]

# Marketing filler that says nothing - never put these on screen
FLUFF = ["don't miss out", "dont miss out", "on their way", "there's so much", "theres so much", "so much to discover",
         "check out", "right away", "be sure to", "get ready", "stay tuned", "exciting", "keep an eye"]

def get_html(url):
    r = requests.get(url, headers=API_HEADERS, timeout=15)
    r.raise_for_status()
    return r.text

def meta_all(page, prop):
    pat = r'<meta[^>]+(?:property|name)="%s"[^>]*content="([^"]*)"' % re.escape(prop)
    out = [html.unescape(m) for m in re.findall(pat, page, re.I)]
    pat2 = r'<meta[^>]+content="([^"]*)"[^>]*(?:property|name)="%s"' % re.escape(prop)
    return out + [html.unescape(m) for m in re.findall(pat2, page, re.I)]

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s)
    except Exception:
        return None

def list_source(src):
    """Newest article links for one outlet: [(url, rss_date_or_None)]"""
    if "rss" in src:
        xml = get_html(src["rss"])
        out = []
        for item in re.findall(r"<item>(.*?)</item>", xml, re.S)[:PER_SOURCE]:
            link = re.search(r"<link>(.*?)</link>", item, re.S)
            date = re.search(r"<pubDate>(.*?)</pubDate>", item, re.S)
            if link:
                out.append((link.group(1).strip(), parse_date(date.group(1)) if date else None))
        return out
    page = get_html(src["list"])
    seen, out = set(), []
    for u in re.findall(src["link_re"], page):
        if u.startswith("/"):
            u = src["base"] + u
        u = u.rstrip("/")
        if u not in seen:
            seen.add(u)
            out.append(u)
    if src["name"] == "PokeGuardian":  # its homepage pins old posts; the id in the URL is the real order
        out.sort(key=lambda u: int(re.search(r"/(\d+)_", u).group(1)), reverse=True)
    return [(u, None) for u in out[:PER_SOURCE]]

def full_size(u):
    u = html.unescape(u)
    if u.startswith("//"):
        u = "https:" + u
    u = re.sub(r"-\d{2,4}x\d{2,4}(?=\.(?:jpe?g|png|webp)$)", "", u.split("?")[0]) if "pokebeach.com" in u else u
    return u.replace("-standard.", "-high.")

def good_image(u):
    low = u.lower()
    return u.startswith("http") and not any(b in low for b in [
        "footer", "logo", "avatar", "icon", "banner", "button", "/amyt6x/", "forums/data", "water%20pokemon",
        "gravatar", "pixel", "facebook", "twitter", ".svg", "emoji", "ads."])

def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'$])", text)
    return [p.strip() for p in parts if p.strip()]

def is_fluff(s):
    low = s.lower()
    return any(f in low for f in FLUFF)

_IMG_RE = r'<img[^>]+(?:data-src|src)="([^"]+)"[^>]*>'

def _img_url(src, raw):
    u = full_size(raw)
    if u.startswith("/"):
        u = src["base"] + u
    return u if good_image(u) else None

def _img_alt(tag):
    m = re.search(r'alt="([^"]*)"', tag)
    return clean_text(m.group(1)) if m else ""

def parse_blocks(src, seg):
    """Walk the article in order and pair every heading/paragraph with the picture that sits next to it.

    Returns [{"head", "text", "img", "alt"}]. A paragraph gets the closest image ABOVE it; paragraphs
    before the first image get the first image that follows them. This is what keeps the words on
    screen matching the picture on screen.
    """
    blocks, cur_img, cur_alt, cur_head = [], None, "", ""
    pending = []  # blocks still waiting for an image
    pat = re.compile(_IMG_RE + r'|<(h[2-4]|p|li|figcaption)[^>]*>(.*?)</\2>', re.S)

    def got_image(u, alt):
        nonlocal cur_img, cur_alt
        cur_img, cur_alt = u, alt
        for b in pending:
            b["img"], b["alt"] = u, alt
        pending.clear()

    for m in pat.finditer(seg):
        if m.group(1):
            u = _img_url(src, m.group(1))
            if u:
                got_image(u, _img_alt(m.group(0)))
            continue
        tag, inner = m.group(2), m.group(3)
        # images tucked inside a <p> or <figure> paragraph
        for im in re.finditer(_IMG_RE, inner):
            u = _img_url(src, im.group(1))
            if u:
                got_image(u, _img_alt(im.group(0)))
        t = clean_text(re.sub(r"<[^>]+>", " ", inner))
        if not t or any(j in t.lower() for j in JUNK):
            continue
        if tag.startswith("h"):
            cur_head = t
            # a new product section: the next picture belongs to it, not the old one
            cur_img, cur_alt = None, ""
            continue
        if tag == "figcaption":
            continue
        if len(t.split()) < 3:
            continue
        b = {"head": cur_head, "text": t, "img": cur_img, "alt": cur_alt}
        if cur_img is None:
            pending.append(b)
        blocks.append(b)
    return blocks

_article_cache = {}
def parse_article(src, url, rss_date=None):
    if url in _article_cache:
        return _article_cache[url]
    page = get_html(url)
    i = page.find(src["start"])
    seg = page[i:] if i >= 0 else page
    ends = [seg.find(e) for e in src["end"] if seg.find(e) > 0]
    if ends:
        seg = seg[:min(ends)]

    og_t = meta_all(page, "og:title")
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", page, re.S)
    title = clean_text(re.sub(r"<[^>]+>", " ", h1[0])) if h1 else ""
    if og_t and (not title or len(title) > 160):
        title = clean_text(og_t[0])
    title = re.split(r"\s+[|\-–]\s+(?:PokeBeach|PokeGuardian|Pokemon\.com|Dexerto)", title)[0].strip()

    desc = clean_text((meta_all(page, "og:description") or [""])[0])

    published = rss_date
    for cand in meta_all(page, "article:published_time") + re.findall(r'"datePublished"\s*:\s*"([^"]+)"', page) \
            + meta_all(page, "pkm-modified-date"):
        published = published or parse_date(cand)

    paras, items = [], []
    for tag, inner in re.findall(r"<(p|li)[^>]*>(.*?)</\1>", seg, re.S):
        t = clean_text(re.sub(r"<[^>]+>", " ", inner))
        low = t.lower()
        if not t or any(j in low for j in JUNK):
            continue
        if tag == "li":
            if len(t.split()) >= 2 and not re.fullmatch(r"[#\d\s:]+", t) and len(t) < 140:
                items.append(t)
        elif len(t.split()) >= 5:
            paras.append(t)

    images = []
    for u in meta_all(page, "og:image") + re.findall(r'<img[^>]+(?:data-src|src)="([^"]+)"', seg):
        u = full_size(u)
        if u.startswith("/"):
            u = src["base"] + u
        if good_image(u) and u.split("?")[0] not in [x.split("?")[0] for x in images]:
            images.append(u)

    art = {"source": src["name"], "url": url, "title": title, "desc": desc, "paras": paras,
           "items": items, "images": images[:src.get("max_imgs", 4)], "all_images": images,
           "blocks": parse_blocks(src, seg), "published": published}
    _article_cache[url] = art
    return art

def all_sentences(art):
    out = []
    for para in [art["desc"]] + art["paras"]:
        for s in split_sentences(para):
            if s[-1:] in ".!?" and 5 <= len(s.split()) <= 32 and s not in out \
                    and s.rstrip(".!?").lower() != art["title"].lower():
                out.append(s)
    return out

def word_hits(text, words):
    low = text.lower()
    return sum(1 for w in words if w in low)

def gather_articles():
    """Parsed, recent, TCG-relevant articles from all outlets, newest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    arts = []
    for src in SOURCES:
        try:
            links = list_source(src)
        except Exception as e:
            print(f"[{src['name']}] list failed: {e}")
            continue
        print(f"[{src['name']}] {len(links)} links")
        for url, d in links:
            try:
                a = parse_article(src, url, d)
            except Exception as e:
                print(f"  skip {url}: {e}")
                continue
            if not a["title"] or not a["images"]:
                continue
            if a["published"] and a["published"] < cutoff:
                continue
            blob = " ".join([a["title"], a["desc"]] + a["paras"][:4])
            if word_hits(blob, TCG_WORDS) == 0:
                continue  # skip non-card stuff (Pokemon GO events, video games...)
            arts.append(a)
    far_past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    arts.sort(key=lambda a: a["published"] or far_past, reverse=True)
    return arts

def already_posted(title, posted, captions):
    t = (title or "").lower()
    return t in posted or (bool(t) and any(t in c for c in captions))

def recent_ig_captions():
    token = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if not token:
        return []
    try:
        r = requests.get(f"{GRAPH}/{IG_USER_ID}/media",
                         params={"fields": "caption", "limit": 100, "access_token": token}, timeout=15).json()
        return [(m.get("caption") or "").lower() for m in r.get("data", [])]
    except Exception as e:
        print(f"Couldn't read recent IG posts: {e}")
        return []

# ---------------------------------------------------------------- facts pulled out of a paragraph

def find_date(text):
    m = re.search(MONTHS + r"\s+\d{1,2}(?:st|nd|rd|th)?", text)
    return m.group(0).upper().replace(".", "") if m else ""

def find_price(text):
    m = re.search(r"\$\s?\d[\d,]*(?:\.\d{2})?", text)
    return m.group(0).replace(" ", "") if m else ""

def short_line(s, max_words=9):
    """One punchy on-screen line: first clause of a sentence, max ~9 words, no filler."""
    s = re.split(r"(?<=[a-z0-9])[,;:]\s+|\s+-\s+|\s+\(", s)[0].strip().rstrip(".!?")
    words = s.split()
    if len(words) > max_words:
        s = " ".join(words[:max_words])
    return s

def fact_line(text):
    """Best single fact in a paragraph: prefer the sentence with a number, price, card count or date."""
    sents = [x for x in split_sentences(text) if not is_fluff(x)] or split_sentences(text)
    scored = sorted(sents, key=lambda x: -(bool(re.search(r"\d", x)) * 2
                                         + bool(re.search(r"card|pack|promo|foil|illustration", x, re.I))))
    return short_line(scored[0]) if scored else ""

def is_breaking(art):
    return word_hits(art["title"] + " " + art["desc"], BREAKING_WORDS) > 0

def short_money(p):
    """$96,000 -> $96K, $1,250,000 -> $1.25M (big hook numbers read faster)."""
    try:
        v = float(p.replace("$", "").replace(",", ""))
    except ValueError:
        return p
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if v >= 10_000:
        return f"${v / 1000:.0f}K"
    return p

def set_hook(scene, big, line, say=None):
    """Turn the first slide into the scroll-stopping opener: one HUGE word + a short line."""
    line = " ".join(line.split()[:5])   # hook line stays short - 5 words max on screen
    scene["hook"] = {"big": big.upper(), "line": line.upper()}
    scene["text"] = f"{big} {line}".upper()
    scene["say"] = "Poke Pulse News. " + (say or f"{big} {line}".lower())
    return scene

def news_hook(art, kind):
    title = short_line(art["title"], 5)
    price = find_price(art["title"] + " " + art["desc"])
    if kind == "sales" and price:
        return short_money(price), title, f"{title}, for {price}"
    if is_breaking(art):
        return "BREAKING", title, f"Breaking. {title}"
    hot = [w for w in re.findall(r"[A-Za-z0-9']+", art["title"]) if w.upper() in HOT_WORDS]
    return (hot[0] if hot else "NEW"), title, title

# ---------------------------------------------------------------- topic: news / sales

def fit_list(parts, max_words=26):
    out = []
    for p in parts:
        if len(" ".join(out + [p]).split()) > max_words:
            break
        out.append(p)
    return out

def product_sections(art):
    """Roundup articles (e.g. 'every product releasing in October'): one entry per product heading,
    with that product's own picture and its own facts."""
    secs, seen = [], set()
    for b in art["blocks"]:
        head = b["head"]
        if not head or head in seen or not b["img"]:
            continue
        if not re.search(PRODUCT_WORDS, head, re.I) and not re.search(PRODUCT_WORDS, b["alt"], re.I):
            continue
        seen.add(head)
        body = " ".join(x["text"] for x in art["blocks"] if x["head"] == head)
        secs.append({"name": head, "img": b["img"], "date": find_date(body) or find_date(head),
                     "price": find_price(body), "fact": fact_line(body)})
    return secs

def build_article_story(art, kind):
    sents = all_sentences(art)
    imgs = art["images"]

    if kind == "sales":
        first_tag = "BIG SALE ALERT"
    elif is_breaking(art):
        first_tag = "BREAKING NEWS"
    else:
        first_tag = "POKEPULSE NEWS"

    scenes = [{"tag": first_tag, "img_url": imgs[0], "text": art["title"].upper(), "colors": [YELLOW, WHITE]}]
    set_hook(scenes[0], *news_hook(art, kind))

    # 1) roundup: one scene per product, named, with its own picture + date/price
    secs = product_sections(art) if kind != "sales" else []
    if len(secs) >= 2:
        if len(secs) > 2:
            mon = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)",
                            art["title"], re.I)
            if mon:
                set_hook(scenes[0], mon.group(1), f"{min(len(secs), 5)} new Pokemon drops",
                         f"Every Pokemon card drop coming in {mon.group(1)}")
            else:
                set_hook(scenes[0], f"{min(len(secs), 5)} NEW", "Pokemon drops coming",
                         f"{min(len(secs), 5)} new Pokemon card drops you need to know")
        for i, s in enumerate(secs[:5]):
            sub = "  •  ".join(x for x in [s["date"], s["price"]] if x)
            sc = {"tag": f"DROP {i + 1} OF {min(len(secs), 5)}", "img_url": s["img"], "text": s["name"].upper(),
                  "colors": [WHITE, YELLOW], "matched": True}
            if sub:
                sc["sub"], sc["sub_size"] = sub, 80
            sc["say"] = ". ".join(x for x in [s["name"], s["date"].title(), s["price"]] if x)
            scenes.append(sc)
        caption_facts = [f"• {s['name']}" + (f" - {s['date'].title()}" if s["date"] else "")
                         + (f" - {s['price']}" if s["price"] else "") for s in secs]
        return {"story_id": art["title"][:40], "key": art["title"].lower(), "scenes": scenes,
                "caption_full": article_caption(art, caption_facts, lead="🚨" if first_tag == "BREAKING NEWS" else "📦")}

    # 2) normal article: each fact uses the picture printed next to that paragraph
    paired = []
    for b in art["blocks"]:
        if not b["img"] or is_fluff(b["text"]):
            continue
        line = fact_line(b["text"])
        if line and len(line.split()) >= 3 and line.lower() not in [p[0].lower() for p in paired]:
            paired.append((line, b["img"]))
    if kind == "sales":
        paired.sort(key=lambda p: -(("$" in p[0]) * 2 + ("psa" in p[0].lower())))
    tags = ["THE SALE", "THE DETAILS", "WHY IT MATTERS"] if kind == "sales" else ["THE DETAILS", "WHAT TO KNOW", "KEY INFO"]

    if paired:
        for i, (line, img) in enumerate(paired[:3]):
            scenes.append({"tag": tags[i], "img_url": img, "text": line.upper(),
                           "colors": [WHITE, YELLOW] if i % 2 == 0 else [YELLOW, WHITE], "matched": True})
    else:
        details = [s for s in sents if not is_fluff(s)][:3]
        if not details:
            return None
        for i, s in enumerate(details):
            scenes.append({"tag": tags[i], "img_url": imgs[(i + 1) % len(imgs)], "text": short_line(s).upper(),
                           "colors": [WHITE, YELLOW] if i % 2 == 0 else [YELLOW, WHITE]})
    facts = ["• " + sc["text"].capitalize() for sc in scenes[1:]]
    return {"story_id": art["title"][:40], "key": art["title"].lower(), "scenes": scenes,
            "caption_full": article_caption(art, facts, lead="💰" if kind == "sales" else "🚨")}

def article_caption(art, facts, lead="🚨"):
    """Short caption in our own words: title + the facts shown in the reel + credit.
    (Pasting the source's paragraphs word-for-word reads as a repost and gets less reach.)"""
    body = "\n".join(facts[:8])
    return (f"{lead} {art['title']}\n\n{body}\n\nSource: {art['source']}\n\n"
            f"Which one are you grabbing? 👇\n\n"
            f"📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!\n\n"
            f"#PokemonCards #PokemonTCG #CardStax #PokemonReels #PokePulse #PokemonNews")

# ---------------------------------------------------------------- topic: drops

def build_drop_story(art):
    sents = all_sentences(art)
    blob = " ".join([art["title"], art["desc"]] + art["paras"] + art["items"])
    lowblob = blob.lower().replace("pokémon", "pokemon")
    where = [r for r in RETAILERS if r.lower() in lowblob]
    when = [s for s in sents if re.search(MONTHS + r"\s+\d{1,2}", s)]
    price = [s for s in sents if re.search(r"\$\s?\d", s)] + [i for i in art["items"] if re.search(r"\$\s?\d", i)]
    inside = [s for s in sents if re.search(r"\b(contains?|includes?|comes with|booster packs?|promo cards?)\b", s, re.I)]
    products = [i for i in art["items"] if re.search(PRODUCT_WORDS, i, re.I)]

    imgs = art["images"]

    def img_for(text):
        """Picture printed next to the paragraph this fact came from (falls back to the main image)."""
        key = text[:60].lower()
        for b in art["blocks"]:
            if b["img"] and key in b["text"].lower():
                return b["img"], True
        return imgs[0], False

    scenes = [{"tag": "DROP REPORT", "img_url": imgs[0], "text": art["title"].upper(), "colors": [YELLOW, WHITE]}]
    tl = art["title"].lower()
    big = "PREORDER" if "pre" in tl and "order" in tl else ("RESTOCK" if "restock" in tl else "NEW DROP")
    set_hook(scenes[0], big, short_line(art["title"], 7))
    def add(tag, text, colors, source_text=None):
        img, matched = img_for(source_text or text)
        scenes.append({"tag": tag, "img_url": img, "text": text.upper(), "colors": colors, "matched": matched})
    if where:
        add("WHERE", "\n".join(fit_list(where, 14)), [YELLOW, WHITE])
    if when:
        add("WHEN", short_line(when[0]), [WHITE, YELLOW], when[0])
    if products:
        add("WHAT'S DROPPING", "\n".join(fit_list(products, 24)), [WHITE, YELLOW], products[0])
    if price:
        add("PRICE", short_line(price[0]), [YELLOW, WHITE], price[0])
    if inside:
        add("WHAT'S INSIDE", short_line(inside[0]), [WHITE, YELLOW], inside[0])
    if len(scenes) < 3:
        return None  # not enough real drop facts in this article

    lines = [f"🛒 DROP REPORT: {art['title']}", ""]
    if where:
        lines.append("📍 Where: " + ", ".join(where))
    if when:
        lines.append("📅 When: " + short_line(when[0]))
    if products:
        lines.append("📦 Products: " + "; ".join(products[:8]))
    if price:
        lines.append("💲 Price: " + short_line(price[0]))
    if inside:
        lines.append("🎁 Inside: " + short_line(inside[0]))
    lines += ["", f"Source: {art['source']}", "",
              "Which one are you grabbing? 👇", "",
              "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!", "",
              "#PokemonCards #PokemonTCG #CardStax #PokemonRestock #PokePulse #PokemonNews"]
    return {"story_id": art["title"][:40], "key": art["title"].lower(), "scenes": scenes,
            "caption_full": "\n".join(lines)}

# ---------------------------------------------------------------- topic: bulk gold

TCG_API = "https://api.pokemontcg.io/v2"

def tcg_get(path, params):
    headers = dict(API_HEADERS)
    key = os.getenv("POKEMONTCG_API_KEY", "").strip()
    if key:
        headers["X-Api-Key"] = key
    for attempt in range(3):
        try:
            r = requests.get(f"{TCG_API}/{path}", params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"pokemontcg.io retry {attempt+1}: {e}")
        time.sleep(3)
    return {}

def best_market(card):
    best, variant = 0.0, ""
    for v, p in ((card.get("tcgplayer") or {}).get("prices") or {}).items():
        m = (p or {}).get("market") or 0
        if m > best:
            best, variant = m, v
    return best, variant

VARIANT_NAMES = {"normal": "", "holofoil": "HOLO", "reverseHolofoil": "REVERSE HOLO",
                 "1stEditionNormal": "1ST EDITION", "1stEditionHolofoil": "1ST EDITION HOLO"}

def build_bulk_story(captions):
    sets = tcg_get("sets", {"orderBy": "-releaseDate", "pageSize": 15}).get("data", [])
    sets = [s for s in sets if (s.get("total") or 0) >= 60 and "promo" not in s.get("name", "").lower()]
    for st in sets[:10]:
        key = f"bulk gold: {st['name']}".lower()
        if any(key in c for c in captions):
            print(f"Bulk Gold already done for {st['name']}")
            continue
        cards = tcg_get("cards", {"q": f'set.id:{st["id"]} (rarity:Common OR rarity:Uncommon)',
                                  "pageSize": 250,
                                  "select": "id,name,number,rarity,images,set,tcgplayer"}).get("data", [])
        ranked = []
        for c in cards:
            m, v = best_market(c)
            img = (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small")
            if m > 0 and img:
                ranked.append((m, v, c, img))
        ranked.sort(key=lambda x: -x[0])
        top = ranked[:4]
        if len(top) < 3 or top[0][0] < 1.0:
            print(f"{st['name']}: no commons/uncommons worth $1+ yet")
            continue

        updated = (top[0][2].get("tcgplayer") or {}).get("updatedAt", "")
        scenes = [{"tag": "BULK GOLD", "img_url": top[0][3],
                   "text": f"CHECK YOUR BULK! {st['name'].upper()} COMMONS & UNCOMMONS WORTH REAL MONEY",
                   "colors": [YELLOW, WHITE], "matched": True}]
        set_hook(scenes[0], "BULK GOLD", f"{st['name']} commons worth money",
                 f"Check your bulk. These {st['name']} commons are worth real money")
        cap = [f"💰 Bulk Gold: {st['name']} - don't toss these commons & uncommons!", ""]
        for rank, (m, v, c, img) in enumerate(top, 1):
            vname = VARIANT_NAMES.get(v, v.upper())
            rarity = (c.get("rarity") or "").upper()
            tag = f"#{rank}  {rarity}" + (f"  {vname}" if vname else "")
            scenes.append({"tag": tag, "img_url": img, "text": c["name"].upper(), "matched": True,
                           "colors": [WHITE], "sub": f"${m:,.2f} MARKET  •  #{c['number']}", "sub_size": 110,
                           "card": {"name": c["name"], "number": c["number"], "rank": f"#{rank}",
                                    "info": f"{(c.get('rarity') or 'Common').title()} · {st['name']}"
                                            + (f" · {vname.title()}" if vname else ""),
                                    "price": f"${m:,.2f}", "total": st.get("printedTotal") or st.get("total")},
                           "say": f"Number {rank}. {c['name']}. ${m:,.2f}."})
            cap.append(f"{rank}. {c['name']} #{c['number']} ({c.get('rarity','')}{', ' + vname.title() if vname else ''}) - ${m:,.2f}")
        cap += ["", f"Prices: TCGplayer market price{(' updated ' + updated) if updated else ''}. Prices move daily.", "",
                "Check your bulk and tell us what you found 👇", "",
                "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!", "",
                "#PokemonCards #PokemonTCG #CardStax #PokemonBulk #PokePulse #PokemonInvesting"]
        return {"story_id": f"bulk {st['name']}", "key": key, "scenes": scenes, "caption_full": "\n".join(cap)}
    return None


def build_chase_story(captions):
    """Top Chase Cards: the most valuable cards in a recent set (TCGplayer market price)."""
    sets = tcg_get("sets", {"orderBy": "-releaseDate", "pageSize": 15}).get("data", [])
    sets = [s for s in sets if (s.get("total") or 0) >= 60 and "promo" not in s.get("name", "").lower()]
    for st in sets[:10]:
        key = f"top chase cards: {st['name']}".lower()
        if any(key in c for c in captions):
            print(f"Chase cards already done for {st['name']}")
            continue
        cards = tcg_get("cards", {"q": f'set.id:{st["id"]}', "pageSize": 250,
                                  "select": "id,name,number,rarity,images,set,tcgplayer"}).get("data", [])
        ranked = []
        for c in cards:
            m, v = best_market(c)
            img = (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small")
            if m > 0 and img:
                ranked.append((m, v, c, img))
        ranked.sort(key=lambda x: -x[0])
        top = ranked[:5]
        if len(top) < 3 or top[0][0] < 5:
            print(f"{st['name']}: no price data for chase cards yet")
            continue
        top = list(reversed(top))   # count down: #5 -> #1
        updated = (top[-1][2].get("tcgplayer") or {}).get("updatedAt", "")
        scenes = [{"tag": "TOP CHASE CARDS", "img_url": top[-1][3], "matched": True,
                   "text": f"THE {len(top)} MOST VALUABLE CARDS IN {st['name'].upper()}",
                   "colors": [YELLOW, WHITE]}]
        set_hook(scenes[0], f"TOP {len(top)}", f"{st['name']} chase cards",
                 f"The top {len(top)} most valuable {st['name']} cards right now")
        cap = [f"🔥 Top Chase Cards: {st['name']} - the most valuable pulls right now", ""]
        for i, (m, v, c, img) in enumerate(top):
            rank = len(top) - i
            rarity = (c.get("rarity") or "").upper()
            scenes.append({"tag": f"#{rank}  {rarity}", "img_url": img, "text": c["name"].upper(), "matched": True,
                           "colors": [WHITE], "sub": f"${m:,.2f} MARKET  •  #{c['number']}", "sub_size": 110,
                           "card": {"name": c["name"], "number": c["number"], "rank": f"#{rank}",
                                    "info": f"{(c.get('rarity') or '').title()} · {st['name']}",
                                    "price": f"${m:,.2f}", "total": st.get("printedTotal") or st.get("total")},
                           "say": f"Number {rank}. {c['name']}. ${m:,.2f}."})
        for i, (m, v, c, img) in enumerate(reversed(top), 1):
            cap.append(f"{i}. {c['name']} #{c['number']} ({c.get('rarity','')}) - ${m:,.2f}")
        cap += ["", f"Prices: TCGplayer market price{(' updated ' + updated) if updated else ''}. Prices move daily.", "",
                "Which one are you chasing? 👇", "",
                "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!", "",
                "#PokemonCards #PokemonTCG #CardStax #PokemonInvesting #PokePulse #ChaseCards"]
        return {"story_id": f"chase {st['name']}", "key": key, "scenes": scenes, "caption_full": "\n".join(cap)}
    return None


# ---------------------------------------------------------------- extra images

_POKEMON_NAMES = None

def pokemon_names():
    global _POKEMON_NAMES
    if _POKEMON_NAMES is None:
        try:
            r = requests.get("https://pokeapi.co/api/v2/pokemon-species?limit=1200", timeout=20).json()
            _POKEMON_NAMES = [x["name"].replace("-", " ") for x in r.get("results", [])]
        except Exception as e:
            print(f"Couldn't load Pokemon names ({e})")
            _POKEMON_NAMES = []
    return _POKEMON_NAMES


def card_images(query, n=6):
    data = tcg_get("cards", {"q": query, "pageSize": 60, "orderBy": "-set.releaseDate",
                             "select": "id,name,rarity,images,tcgplayer"}).get("data", [])
    good = [c for c in data if (c.get("rarity") or "").lower() not in ("common", "uncommon", "")]
    good = good or data
    good.sort(key=lambda c: -best_market(c)[0])
    pool = good[:max(n * 2, 10)]
    random.shuffle(pool)
    return [(c.get("images") or {}).get("large") for c in pool[:n] if (c.get("images") or {}).get("large")]


def scene_card_image(text):
    """A real card of a Pokemon named in this slide's own text (so the art matches the words)."""
    low = text.lower().replace("pokémon", "pokemon")
    names = [nm for nm in pokemon_names() if len(nm) > 3 and re.search(r"\b" + re.escape(nm) + r"\b", low)]
    names.sort(key=lambda nm: low.find(nm))
    for nm in names[:2]:
        imgs = card_images(f'name:"{nm}"', 1)
        if imgs:
            return imgs[0]
    return None


def vary_images(story, art):
    """Fix up pictures WITHOUT breaking the text<->image match.

    Old version overwrote every slide with pool[i % len(pool)] - that's why the binder showed up
    under 'additional products' and tins showed up under 'illustration rare cards'.
    Now: slides already paired with their own picture keep it. Only unmatched slides or repeats
    get a new one - and that one is picked from a Pokemon named in that slide's own text.
    """
    used = set()
    for i, sc in enumerate(story["scenes"]):
        if sc.get("matched") and sc.get("img_url") and sc["img_url"] not in used:
            used.add(sc["img_url"])
            continue
        if i == 0 and sc.get("img_url"):
            used.add(sc["img_url"])
            continue
        new = scene_card_image(sc["text"])
        if not new:
            # article picture whose alt text / paragraph mentions a word from this slide
            words = {w for w in re.findall(r"[a-z]{4,}", sc["text"].lower())} - {"pokemon", "with", "from", "this", "that"}
            for b in art.get("blocks", []):
                if b["img"] and b["img"] not in used and words & set(re.findall(r"[a-z]{4,}", (b["alt"] + " " + b["text"]).lower())):
                    new = b["img"]
                    break
        if new:
            sc["img_url"] = new
        used.add(sc["img_url"])

# ---------------------------------------------------------------- topic picker

TOPICS = ["news", "drops", "sales", "bulk", "chase"]

def topic_for_now():
    forced = os.getenv("REEL_TOPIC", "").strip().lower()
    if forced in TOPICS:
        return forced
    h = datetime.now(timezone.utc).hour
    if 12 <= h <= 15:
        return "news"      # 9:30am ET run
    if 16 <= h <= 19:
        return "drops"     # 12:30pm ET run
    if 20 <= h <= 23:
        return "sales"     # 5:30pm ET run
    # 9:30pm ET run: alternate Bulk Gold and Top Chase Cards day by day
    return "bulk" if datetime.now(timezone.utc).toordinal() % 2 == 0 else "chase"

def build_story():
    posted = set()
    if os.path.exists("posted_news.txt"):
        with open("posted_news.txt") as f:
            posted = {l.strip().lower() for l in f if l.strip()}
    captions = recent_ig_captions()
    first = topic_for_now()
    order = [first] + [t for t in ["news", "drops", "bulk", "chase", "sales"] if t != first]
    articles = None

    for topic in order:
        print(f"--- Trying topic: {topic}")
        if topic in ("bulk", "chase"):
            story = build_bulk_story(captions) if topic == "bulk" else build_chase_story(captions)
            if story:
                story["topic"] = topic
                return story
            continue
        if articles is None:
            articles = gather_articles()
            print(f"{len(articles)} recent card-related articles found")
        for art in articles:
            if already_posted(art["title"], posted, captions):
                continue
            head = (art["title"] + " " + art["desc"] + " " + " ".join(art["paras"][:2])).lower()
            if any(re.search(r"\b" + re.escape(w) + r"\b", head) for w in NOT_COLLECTOR):
                print(f"Skipping (not collector news): {art['title']}")
                continue
            blob = " ".join([art["title"], art["desc"]] + art["paras"][:6] + art["items"])
            if topic == "drops":
                if word_hits(blob, DROP_WORDS) < 2:
                    continue
                story = build_drop_story(art)
            elif topic == "sales":
                if word_hits(art["title"] + " " + art["desc"], SALE_WORDS) < 1 or "$" not in blob:
                    continue
                story = build_article_story(art, "sales")
            else:
                story = build_article_story(art, "news")
            if story:
                print(f"Picked [{topic}] {art['source']}: {art['title']}")
                story["topic"] = topic
                # voiceover/captions should read what's ON the slides, not the source's intro fluff
                story["context"] = art["title"] + ". " + " ".join(sc["text"].capitalize() + "."
                                                                  for sc in story["scenes"][1:])
                try:
                    vary_images(story, art)
                except Exception as e:
                    print(f"Couldn't fix up images ({e})")
                for sc in story["scenes"]:
                    print(f"  slide: [{sc['tag']}] {sc['text'][:50]}  <-  {sc['img_url'][-60:]}")
                return story
    return None

# ---------------------------------------------------------------- rendering

def load_image(url):
    try:
        if url and os.path.exists(url):
            return Image.open(url).convert("RGB")
        data = requests.get(url, headers=API_HEADERS, timeout=15).content
        with open("temp_raw", "wb") as f:
            f.write(data)
        im = Image.open("temp_raw")
        im.load()
        return im.convert("RGB")
    except Exception as e:
        print(f"Error loading image {url}: {e}")
        return None

HOT_WORDS = {"NEW", "RARE", "CHASE", "PSA", "GOLD", "RECORD", "BIGGEST", "EXCLUSIVE", "SECRET", "ILLUSTRATION",
             "SPECIAL", "PROMO", "LIMITED", "FREE", "BANNED", "LEAKED", "LEAK", "REVEALED", "DELAYED", "RESTOCK",
             "PREORDER", "PRE-ORDER", "SOLD", "MILLION", "VALUABLE", "WORTH", "MONEY", "TOP", "BULK", "DROPS",
             "DROP", "30TH", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER",
             "OCTOBER", "NOVEMBER", "DECEMBER"}
GENERIC_TAGS = {"THE DETAILS", "WHAT TO KNOW", "KEY INFO", "WHY IT MATTERS", "THE SALE"}
STOP = {"THE", "AND", "WITH", "FROM", "THIS", "THAT", "YOUR", "WILL", "HAVE", "INTO", "POKEMON", "POKÉMON", "TCG"}
TEXT_SAFE_BOTTOM = 1520   # keep words above the news ticker + Instagram's caption / buttons
TICKER_Y, TICKER_H = 1560, 62   # scrolling news ticker band
BUG_Y = 150                     # "POKEPULSE NEWS" corner bug (below Instagram's top bar)
SIDE = 60

def _is_hot(word, names):
    core = re.sub(r"[^A-Z0-9$#%\-]", "", word.upper())
    if not core:
        return False
    return bool(re.search(r"[\d$%#]", core)) or core in HOT_WORDS or core.lower() in names

def highlight_flags(words):
    """Which words get the accent color: numbers/prices, hype words, Pokemon names.
    If nothing qualifies, the longest real word gets it (like 'GOLDSTAR' on joinsleeved)."""
    try:
        names = set(n for n in pokemon_names() if " " not in n)
    except Exception:
        names = set()
    flags = [_is_hot(w, names) for w in words]
    # max 2 highlighted words, otherwise nothing stands out: numbers/prices first, then names, then hype words
    def rank(i):
        core = re.sub(r"[^A-Z0-9$#%\-]", "", words[i].upper())
        return 0 if re.search(r"[\d$%#]", core) else (1 if core.lower() in names else 2)
    keep = sorted([i for i, f in enumerate(flags) if f], key=lambda i: (rank(i), i))[:2]
    flags = [i in keep for i in range(len(words))]
    if not any(flags) and words:
        cands = [(len(re.sub(r"[^A-Z]", "", w.upper())), i) for i, w in enumerate(words)
                 if re.sub(r"[^A-Z]", "", w.upper()) not in STOP]
        if cands:
            flags[max(cands)[1]] = True
    return flags

def fit_rich(draw, text, max_w, max_h, face="anton", start=180, min_size=80, max_lines=2):
    words = text.split()
    size = start
    while True:
        font = get_font(size, face)
        lines = wrap_words(draw, text, font, max_w, 0)
        line_h = int(size * 1.02)
        if (len(lines) <= max_lines and len(lines) * line_h <= max_h) or size <= min_size:
            return font, lines, line_h
        size -= 6

def draw_rich_lines(layer, lines, font, line_h, top, accent=ACCENT, align="center", x0=SIDE):
    """Draw headline word by word (hot words in accent color) with a soft drop shadow."""
    words = " ".join(lines).split()
    flags = highlight_flags(words)
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    d = ImageDraw.Draw(layer)
    space = text_w(d, " ", font) or int(font.size * 0.25)
    y, k = top, 0
    for line in lines:
        lw = line.split()
        total = sum(text_w(d, w, font) for w in lw) + space * (len(lw) - 1)
        x = (W - total) // 2 if align == "center" else x0
        for w in lw:
            color = accent if flags[k] else WHITE
            sd.text((x + 6, y + 10), w, font=font, fill=(0, 0, 0, 230))
            d.text((x, y), w, font=font, fill=color, stroke_width=2, stroke_fill="#000000")
            x += text_w(d, w, font) + space
            k += 1
        y += line_h
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    out = Image.alpha_composite(shadow, layer)
    layer.paste(out, (0, 0))
    return y

def spaced(draw, xy, text, font, fill, spacing=4):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += text_w(draw, ch, font) + spacing
    return x

def spaced_w(draw, text, font, spacing=4):
    return sum(text_w(draw, ch, font) + spacing for ch in text) - spacing

def _blur_cover(raw, darken=0.6):
    cover = raw.copy()
    scale = max(W / cover.width, H / cover.height)
    cover = cover.resize((int(cover.width * scale) + 1, int(cover.height * scale) + 1), Image.Resampling.LANCZOS)
    left, top = (cover.width - W) // 2, (cover.height - H) // 2
    cover = cover.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(34))
    return Image.blend(cover, Image.new("RGB", cover.size, BG), darken)

def _paste_with_shadow(base, im, x, y, radius=24):
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x + 10, y + 18, x + im.width + 10, y + im.height + 18],
                                         radius=radius, fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    base = Image.alpha_composite(base.convert("RGBA"), sh)
    base.paste(im, (x, y))
    return base

def _bottom_fade(img, start, end):
    fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    for y in range(start, H):
        a = 255 if y >= end else int(255 * ((y - start) / (end - start)) ** 1.3)
        fd.line([(0, y), (W, y)], fill=BG + (a,))
    return Image.alpha_composite(img.convert("RGBA"), fade)

def _brand(d):
    """Branding now lives in the persistent news frame (see make_news_frame)."""
    return

def render_card_layers(scene, raw, bg_path, txt_path, accent=LIME):
    """pricecharting-style card slide: huge lime name, faded #number behind, big card, price row."""
    c = scene["card"]
    bg = _blur_cover(raw, 0.78).convert("RGBA") if raw is not None else Image.new("RGBA", (W, H), BG + (255,))
    bd = ImageDraw.Draw(bg)  # only used for measuring
    # faded card number watermark top-right
    wm = f"#{c['number']}"
    wf = get_font(360, "anton")
    # (big faded #number watermark removed - it read as a glitch behind the name)
    if raw is not None:
        art = raw.copy()
        art.thumbnail((620, 760), Image.Resampling.LANCZOS)
        bg = _paste_with_shadow(bg, art, (W - art.width) // 2, 520)
    bg.convert("RGB").save(bg_path)

    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    _brand(d)
    # name, left aligned, as big as fits on 1-2 lines
    name = c["name"].upper()
    size = 230
    size = 200
    while size > 90:
        nf = get_font(size, "anton")
        lines = wrap_words(d, name, nf, W - 2 * SIDE, 0)
        if len(lines) <= 2 and len(lines) * size * 1.0 <= 230:
            break
        size -= 8
    y = 230
    for line in lines:
        d.text((SIDE, y), line, font=nf, fill=accent, stroke_width=2, stroke_fill="#000000")
        y += int(size * 1.0)
    inf = get_font(44, "mont")
    d.text((SIDE + 4, y + 6), c["info"], font=inf, fill=WHITE, stroke_width=2, stroke_fill="#000000")

    # stat row
    top = 1320
    d.line([(SIDE, top), (W - SIDE, top)], fill=(255, 255, 255, 110), width=2)
    d.line([(SIDE, top + 190), (W - SIDE, top + 190)], fill=(255, 255, 255, 110), width=2)
    cols = [("RANK", c["rank"]), ("MARKET PRICE", c["price"]),
            ("CARD", f"{c['number']}/{c['total']}" if c.get("total") else f"#{c['number']}")]
    cw = (W - 2 * SIDE) // 3
    lf, vf = get_font(30, "mont"), get_font(84, "mont")
    for i, (label, val) in enumerate(cols):
        cx = SIDE + cw * i + cw // 2
        if i:
            d.line([(SIDE + cw * i, top + 28), (SIDE + cw * i, top + 162)], fill=(255, 255, 255, 110), width=2)
        vfi = vf
        while text_w(d, val, vfi) > cw - 20 and vfi.size > 40:
            vfi = get_font(vfi.size - 6, "mont")
        d.text((cx - text_w(d, label, lf) // 2, top + 30), label, font=lf, fill=WHITE)
        d.text((cx - text_w(d, val, vfi) // 2, top + 72), val, font=vfi,
               fill=accent if i == 1 else WHITE)
    txt.save(txt_path)

def accent_from_image(raw, fallback=YELLOW):
    """Pick the picture's strongest vivid color and brighten it, so the text color matches the art
    (green Celebi -> lime text, blue Giratina -> icy blue, Charizard -> orange...)."""
    if raw is None:
        return fallback
    import colorsys
    small = raw.copy().convert("RGB")
    small.thumbnail((72, 72))
    bins = {}
    for r, g, b in small.getdata():
        h, sat, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if sat < 0.45 or v < 0.45:
            continue
        k = int(h * 24) % 24
        w = sat * v
        acc = bins.setdefault(k, [0.0, 0.0, 0.0])
        acc[0] += w; acc[1] += h * w; acc[2] += 1
    if not bins:
        return fallback
    k, (w, hw, n) = max(bins.items(), key=lambda kv: kv[1][0])
    if n < 25:   # a few stray pixels isn't a theme color
        return fallback
    h = hw / w
    r, g, b = colorsys.hsv_to_rgb(h, 0.78, 1.0)
    # dark hues (pure blue/purple/red) get lifted toward white so they still pop on black
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if lum < 0.55:
        mix = (0.55 - lum) / 0.45 * 0.6
        r, g, b = (r + (1 - r) * mix, g + (1 - g) * mix, b + (1 - b) * mix)
    return "#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))

def render_hook_text(txt, hook, accent):
    """pricecharting-style opener: one HUGE word in the picture's color, a smaller line under it
    (key words highlighted), and an accent underline bar."""
    d = ImageDraw.Draw(txt)
    big, line = hook["big"].upper(), hook.get("line", "").upper()
    max_w = W - 2 * SIDE
    size = 430
    while size > 120:
        bf = get_font(size, "anton")
        if text_w(d, big, bf) <= max_w:
            break
        size -= 8
    lf, lines, lh = fit_rich(d, line, max_w, 260, start=112, min_size=64, max_lines=2) if line else (None, [], 0)
    big_h = d.textbbox((0, 0), big, font=bf)[3] + 18   # real glyph bottom, so the line never overlaps
    bar_h = 60
    y = TEXT_SAFE_BOTTOM - bar_h - len(lines) * lh - big_h
    # shadow + big word
    sh = Image.new("RGBA", txt.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text(((W - text_w(d, big, bf)) // 2 + 8, y + 14), big, font=bf, fill=(0, 0, 0, 235))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    txt.paste(Image.alpha_composite(sh, txt), (0, 0))
    d = ImageDraw.Draw(txt)
    d.text(((W - text_w(d, big, bf)) // 2, y), big, font=bf, fill=accent, stroke_width=3, stroke_fill="#000000")
    y += big_h
    if lines:
        y = draw_rich_lines(txt, lines, lf, lh, y, accent=accent)
    d = ImageDraw.Draw(txt)
    d.rounded_rectangle([SIDE + 120, y + 24, W - SIDE - 120, y + 32], radius=4, fill=accent)

def render_scene_layers(scene, bg_path, txt_path):
    """bg = artwork (gets the slow zoom), txt = text layer (stays sharp, fades in).

    Look: big full-bleed picture on top, heavy Anton headline over a dark fade, key words in a
    color pulled from the picture. Opener = pricecharting hook. Card slides = pricecharting card layout.
    """
    raw = load_image(scene["img_url"])
    accent = scene.get("accent") or accent_from_image(raw)
    scene["accent"] = accent
    if scene.get("card"):
        return render_card_layers(scene, raw, bg_path, txt_path, accent)

    img_bottom = 1380  # picture fills the top ~70% of the screen
    if raw is not None:
        bg = _blur_cover(raw, 0.55)
        art = raw.copy()
        if art.width / art.height >= 0.8:
            # wide/square picture: fill the full width, crop to the picture area (full-bleed)
            scale = max(W / art.width, img_bottom / art.height)
            art = art.resize((int(art.width * scale) + 1, int(art.height * scale) + 1), Image.Resampling.LANCZOS)
            left = (art.width - W) // 2
            top = max(0, (art.height - img_bottom) // 2)
            art = art.crop((left, top, left + W, top + img_bottom))
            bg.paste(art, (0, 0))
        else:
            # tall picture (a single card): as big as possible, centered
            art.thumbnail((W - 120, img_bottom - 120), Image.Resampling.LANCZOS)
            bg = _paste_with_shadow(bg, art, (W - art.width) // 2, 110 + (img_bottom - 120 - art.height) // 2)
    else:
        bg = Image.new("RGB", (W, H), BG)
    bg = _bottom_fade(bg, img_bottom - 420, img_bottom + 40)
    bg.convert("RGB").save(bg_path)

    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    _brand(d)

    if scene.get("hook"):
        render_hook_text(txt, scene["hook"], accent)
        txt.save(txt_path)
        return

    render_chyron(txt, scene, accent)
    txt.save(txt_path)


def render_chyron(txt, scene, accent):
    """TV-news lower third: accent label block + dark headline bar (max 4 words) + price/date line."""
    d = ImageDraw.Draw(txt)
    tag = (scene.get("tag") or "").upper()
    show_tag = bool(tag) and tag not in GENERIC_TAGS
    sub = scene.get("sub", "")
    pad = 34
    bar_w = W - 2 * SIDE
    font, lines, line_h = fit_rich(d, scene["text"], bar_w - 2 * pad - 14, 250, start=128, min_size=72)
    sub_font = get_font(54, "mont")
    while sub and text_w(d, sub, sub_font) > bar_w - 2 * pad and sub_font.size > 32:
        sub_font = get_font(sub_font.size - 4, "mont")
    bar_h = pad + len(lines) * line_h + (sub_font.size + 40 if sub else 0) + 14
    bar_top = TEXT_SAFE_BOTTOM - bar_h
    # label block sitting on top of the bar
    if show_tag:
        tf = get_font(38, "mont")
        tw = spaced_w(d, tag, tf, 4)
        d.rectangle([SIDE, bar_top - 66, SIDE + tw + 44, bar_top], fill=accent)
        spaced(d, (SIDE + 22, bar_top - 58), tag, tf, "#000000", 4)
    # bar: dark glass with an accent stripe on the left
    d.rectangle([SIDE, bar_top, SIDE + bar_w, bar_top + bar_h], fill=(8, 8, 12, 225))
    d.rectangle([SIDE, bar_top, SIDE + 14, bar_top + bar_h], fill=accent)
    # headline, left aligned like a real chyron
    words = " ".join(lines).split()
    flags = highlight_flags(words)
    space = text_w(d, " ", font) or 20
    y, k = bar_top + pad - int(line_h * 0.08), 0
    for line in lines:
        x = SIDE + 14 + pad
        for w in line.split():
            d.text((x, y), w, font=font, fill=accent if flags[k] else WHITE)
            x += text_w(d, w, font) + space
            k += 1
        y += line_h
    if sub:
        d.text((SIDE + 14 + pad, y + 22), sub, font=sub_font, fill=accent)


SEGMENTS = {"news": "POKÉ NEWS", "drops": "DROP ALERT", "sales": "MARKET WATCH",
            "bulk": "BULK GOLD", "chase": "CHASE REPORT"}

def make_news_frame(story, out_png="news_frame.png"):
    """Everything that stays on screen for the whole segment: corner bug + ticker band."""
    fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fr)
    seg = SEGMENTS.get(story.get("topic", "news"), "POKÉ NEWS")
    bf = get_font(40, "mont")
    # corner bug:  [● POKÉPULSE] [DROP ALERT]
    x, y = SIDE, BUG_Y
    w1 = spaced_w(d, "POKÉPULSE", bf, 3) + 92
    d.rectangle([x, y, x + w1, y + 64], fill=RED)
    d.ellipse([x + 22, y + 22, x + 42, y + 42], fill=WHITE)
    spaced(d, (x + 58, y + 10), "POKÉPULSE", bf, WHITE, 3)
    x2 = x + w1
    w2 = spaced_w(d, seg, bf, 3) + 44
    d.rectangle([x2, y, x2 + w2, y + 64], fill=(8, 8, 12, 235))
    spaced(d, (x2 + 22, y + 10), seg, bf, WHITE, 3)
    date = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-4))).strftime("%b %d").upper()
    df = get_font(30, "mont")
    d.rectangle([x2 + w2, y, x2 + w2 + text_w(d, date, df) + 36, y + 64], fill=(255, 255, 255, 235))
    d.text((x2 + w2 + 18, y + 15), date, font=df, fill="#000000")
    # ticker band + red "LATEST" label
    d.rectangle([0, TICKER_Y, W, TICKER_Y + TICKER_H], fill=(8, 8, 12, 235))
    lf = get_font(34, "mont")
    lw = spaced_w(d, "LATEST", lf, 3) + 40
    d.rectangle([0, TICKER_Y, lw, TICKER_Y + TICKER_H], fill=RED)
    spaced(d, (20, TICKER_Y + 12), "LATEST", lf, WHITE, 3)
    fr.save(out_png)
    return out_png, lw

def make_ticker_strip(story, out_png="ticker.png"):
    """Long strip of headlines that crawls across the ticker band."""
    items = []
    for sc in story["scenes"][1:]:
        t = (sc.get("card") or {}).get("name") or sc.get("text", "")
        items.append(t.upper())
    items.append("FREE WEEKLY POKÉPULSE NEWSLETTER - LINK IN BIO")
    unit = "   •   ".join(items) + "   •   "
    f = get_font(36, "mont")
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    text = unit
    while text_w(tmp, text, f) < W * 1.2:
        text += unit
    tw = text_w(tmp, text, f) + 40
    strip = Image.new("RGBA", (tw * 2, TICKER_H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    for i in range(2):  # doubled so it loops seamlessly
        sd.text((i * tw, 10), text, font=f, fill=WHITE)
    strip.save(out_png)
    return out_png, tw


NEWSLETTER_URL = "pokemonnews.beehiiv.com"
CTA_IMAGE = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"   # your newsletter promo graphic

def newsletter_art(out_path="cta_art.png"):
    """Your newsletter promo graphic; if it can't be downloaded, a clean built-in version."""
    img = load_image(CTA_IMAGE)
    if img is not None:
        return CTA_IMAGE
    im = Image.new("RGB", (1000, 1000), (16, 14, 34))
    d = ImageDraw.Draw(im)
    for r in range(520, 0, -8):  # soft glow
        c = int(40 + (520 - r) * 0.12)
        d.ellipse([500 - r, 420 - r, 500 + r, 420 + r], fill=(c, int(c * 0.8), min(255, c + 60)))
    d.rounded_rectangle([250, 120, 750, 880], radius=60, fill=(250, 250, 255), outline=YELLOW, width=10)
    d.rounded_rectangle([290, 180, 710, 300], radius=24, fill=YELLOW)
    t = get_font(80, "anton")
    d.text((500 - text_w(d, "POKÉPULSE", t) // 2, 190), "POKÉPULSE", font=t, fill="#111111")
    m = get_font(34, "mont")
    for i, line in enumerate(["PRICE MOVERS", "NEW DROPS", "RESTOCKS", "CHASE CARDS"]):
        y = 360 + i * 110
        d.rounded_rectangle([300, y, 700, y + 80], radius=16, fill=(235, 236, 245))
        d.ellipse([318, y + 22, 354, y + 58], fill=YELLOW)
        d.text((376, y + 20), line, font=m, fill="#222222")
    im.save(out_path)
    return out_path

def cta_scene():
    return {"tag": "FREE EVERY WEEK", "img_url": newsletter_art(), "accent": YELLOW,
            "text": "JOIN THE FREE NEWSLETTER", "sub": "LINK IN BIO  •  " + NEWSLETTER_URL.upper(),
            "say": "Get the free Poke Pulse newsletter. Link in bio."}

def find_cta_slide():
    """Your own end slide from the repo. Set CTA_SLIDE=path/to/file.png to pick it exactly;
    otherwise the first image in the repo with 'cta' or 'newsletter' in its name is used;
    otherwise your hosted CTA graphic."""
    forced = os.getenv("CTA_SLIDE", "").strip()
    if forced and os.path.exists(forced):
        return forced
    pats = ["*cta*", "*CTA*", "*Cta*", "*newsletter*", "*Newsletter*", "*NEWSLETTER*"]
    found = []
    for pat in pats:
        for ext in ("png", "jpg", "jpeg", "webp"):
            found += glob.glob(f"**/{pat}.{ext}", recursive=True)
    found = [f for f in dict.fromkeys(found) if not os.path.basename(f).startswith(("f_cta", "txt_cta", "bg_cta", "cta_art"))]
    if found:
        print(f"End slide: {found[0]}")
        return found[0]
    return CTA_IMAGE

def make_cta_slide(out_path="f_cta.png"):
    """YOUR designated end slide, shown as-is (full screen, nothing drawn on top).
    If it isn't 9:16 it's centered on a blurred copy of itself."""
    img = load_image(find_cta_slide())
    base = Image.new("RGB", (W, H), BG)
    if img is not None:
        base = _blur_cover(img, 0.45)
        sc = min(W / img.width, H / img.height)   # fit the whole slide on screen (up or down)
        art = img.resize((int(img.width * sc), int(img.height * sc)), Image.Resampling.LANCZOS)
        base.paste(art, ((W - art.width) // 2, (H - art.height) // 2))
    else:
        print("Couldn't load your end slide - using the built-in newsletter slide")
        render_scene_layers(cta_scene(), out_path, "f_cta_txt.png")
        base = Image.alpha_composite(Image.open(out_path).convert("RGBA"),
                                     Image.open("f_cta_txt.png").convert("RGBA")).convert("RGB")
    base.save(out_path)

def render_scene_clip(bg_path, texts, dur, out_vid, zoom_in=True, pan=0):
    """ONE continuous camera move over the picture for the whole slide, while the text beats swap on top.
    (Before, each beat restarted the zoom on the same picture - that was the jumpy 'glitch'.)
    texts = [(txt_png, start, end), ...]"""
    frames = max(int(dur * 30), 1)
    z = f"1+0.12*on/{frames}" if zoom_in else f"1.12-0.12*on/{frames}"
    xexpr = f"(iw-iw/zoom)*(0.5+{0.5 * pan}*on/{frames})" if pan else "iw/2-(iw/zoom/2)"
    inputs = ["-framerate", "30", "-loop", "1", "-t", str(dur), "-i", bg_path]
    fc = f"[0]scale=2160:3840,zoompan=z='{z}':x='{xexpr}':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30[b0];"
    last = "b0"
    for i, (tp, st, en) in enumerate(texts, 1):
        inputs += ["-framerate", "30", "-loop", "1", "-t", str(dur), "-i", tp]
        fc += (f"[{i}]format=rgba,fade=t=in:st={st}:d=0.12:alpha=1[t{i}];"
               f"[{last}][t{i}]overlay=0:0:enable='between(t,{st},{en})'[b{i}];")
        last = f"b{i}"
    fc += f"[{last}]format=yuv420p[v]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
        "-filter_complex", fc, "-map", "[v]", "-t", str(dur),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30", out_vid], check=True)

def render_motion_clip(bg_path, txt_path, dur, out_vid, zoom_in=True, pan=0, still=False):
    """Zoom + sideways drift on the art (pan -1 left, 0 center, 1 right) + text popping in on top.
    Every beat moves a different way so the reel never sits still."""
    frames = max(int(dur * 30), 1)
    z = f"1+0.12*on/{frames}" if zoom_in else f"1.12-0.12*on/{frames}"
    if still:
        z = "1"   # your end slide: no zoom, nothing cropped
    xexpr = f"(iw-iw/zoom)*(0.5+{0.5 * pan}*on/{frames})" if pan else "iw/2-(iw/zoom/2)"
    inputs = ["-framerate", "30", "-loop", "1", "-t", str(dur), "-i", bg_path]
    if txt_path:
        inputs += ["-framerate", "30", "-loop", "1", "-t", str(dur), "-i", txt_path]
        fc = (f"[0]scale=2160:3840,zoompan=z='{z}':x='{xexpr}':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30[bg];"
              f"[1]format=rgba,fade=t=in:st=0:d=0.12:alpha=1[tx];"
              f"[bg][tx]overlay=0:0,format=yuv420p[v]")
    else:
        fc = (f"[0]scale=2160:3840,zoompan=z='{z}':x='{xexpr}':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30,"
              f"format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
        "-filter_complex", fc, "-map", "[v]", "-t", str(dur),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30", out_vid
    ], check=True)

# ---------------------------------------------------------------- voiceover (free: Microsoft Edge voices via edge-tts)

VOICE = os.getenv("TTS_VOICE", "en-US-AndrewNeural")
VOICE_RATE = os.getenv("TTS_RATE", "+12%")

def want_voice():
    """Voiceover on 3 out of every 4 posts. VOICEOVER=on/off forces it."""
    forced = os.getenv("VOICEOVER", "").strip().lower()
    if forced in ("on", "1", "true", "yes"):
        return True
    if forced in ("off", "0", "false", "no"):
        return False
    n = os.getenv("GITHUB_RUN_NUMBER", "").strip()
    n = int(n) if n.isdigit() else datetime.now(timezone.utc).toordinal() * 4 + datetime.now(timezone.utc).hour // 6
    return n % 4 != 0

def say_text(scene):
    t = scene.get("say") or scene.get("text", "")
    t = t.replace("\n", ", ").replace("•", ",").replace("#", "number ").replace("&", "and")
    t = re.sub(r"\s+", " ", t).strip()
    return t[0].upper() + t[1:].lower() if t.isupper() else t

def tts(text, out_mp3):
    """Returns clip length in seconds, or None if the voice couldn't be made."""
    try:
        subprocess.run(["edge-tts", "--voice", VOICE, f"--rate={VOICE_RATE}", "--text", text,
                        "--write-media", out_mp3], check=True, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return audio_len(out_mp3)
    except Exception as e:
        print(f"TTS failed ({e})")
        return None

def audio_len(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else None

def build_voice_track(story):
    """One voice clip per slide. Slide length follows its clip so the picture changes when the
    voice moves on (capped so nothing drags). Returns (durations, voice_wav) or (None, None)."""
    durs, parts = [], []
    for i, sc in enumerate(story["scenes"]):
        clip = f"vo_{i + 1}.mp3"
        L = tts(say_text(sc), clip)
        if L is None:
            return None, None
        cap = 4.4 if sc.get("hook") else MAX_SCENE_SECONDS + 0.2   # the intro gets a little longer
        dur = round(min(max(L + 0.25, 1.6), cap), 2)
        durs.append(dur)
        padded = f"vo_{i + 1}.wav"
        # tempo-up a hair if the line runs long, then pad to the slide length
        tempo = max(1.0, min(1.3, (L + 0.1) / max(dur - 0.15, 0.1)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", clip, "-af",
                        f"atempo={tempo:.3f},apad,atrim=0:{dur}", "-ar", "44100", "-ac", "2", padded], check=True)
        parts.append(padded)
    with open("vo_list.txt", "w") as f:
        for ptxt in parts:
            f.write(f"file '{ptxt}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "vo_list.txt",
                    "-c", "copy", "voice.wav"], check=True)
    return durs, "voice.wav"

def pick_music(total_duration):
    audio_candidates = glob.glob("audio/*.mp3") + glob.glob("audio/*.wav") + glob.glob("*.mp3")
    audio_candidates = [f for f in audio_candidates if f not in ["bg_audio.mp3", "pokemon_beat.mp3"]
                        and not os.path.basename(f).startswith("vo_")]
    if audio_candidates:
        audio_file = random.choice(audio_candidates)
        print(f"Using rotated soundtrack: {audio_file}")
        return audio_file
    audio_file = "bg_audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=220:sample_rate=44100",
                    "-t", str(total_duration), "-c:a", "pcm_s16le", audio_file], check=True)
    return audio_file

WORDS_PER_BEAT = 4      # never more than this many words on screen at once
BEATS_PER_PICTURE = 2   # a picture holds for at most 2 quick text beats (<= 3s), then the next picture

def split_beats(text, max_words=WORDS_PER_BEAT, max_beats=BEATS_PER_PICTURE):
    """'GENGAR PREMIUM BLISTER COLLECTION DROPS OCTOBER 24' -> ['GENGAR PREMIUM BLISTER', 'COLLECTION DROPS OCTOBER 24']
    Splits at punctuation when it can, keeps chunks even, drops anything past the beat limit."""
    words = text.replace("\n", " ").split()
    words = words[:max_words * max_beats]
    if len(words) <= max_words:
        return [" ".join(words)]
    n = -(-len(words) // max_words)
    cut = len(words) // n
    for i, w in enumerate(words[:-1]):
        if w[-1:] in ",:;-" and abs((i + 1) - cut) <= 1:
            cut = i + 1
            break
    first, rest = words[:cut], words[cut:]
    return [" ".join(first).rstrip(",:;- ")] + split_beats(" ".join(rest), max_words, max_beats - 1)

def scene_beats(sc, dur):
    """One slide -> 1-2 beats sharing its picture. Hook + card slides stay one beat."""
    if sc.get("hook") or sc.get("card"):
        return [(sc, dur)]
    chunks = split_beats(sc["text"])
    total = sum(len(c.split()) for c in chunks) or 1
    beats = []
    for i, ch in enumerate(chunks):
        b = dict(sc)
        b["text"] = ch
        if i > 0:
            b["tag"] = ""                      # label only on the first beat
        if i < len(chunks) - 1:
            b.pop("sub", None)                 # price/date only on the last beat
        beats.append((b, max(0.8, round(dur * len(ch.split()) / total, 2))))
    return beats

def compile_reel(story, output_mp4="pokepulse_reel.mp4", voice=None):
    """Renders every slide in the new style, adds music, and (3 of 4 posts) a voiceover on top."""
    if voice is None:
        voice = want_voice()
    durs, voice_file = (build_voice_track(story) if voice else (None, None))
    if voice and not voice_file:
        print("Voiceover unavailable - music only this time")
    print(f"Voiceover: {'ON' if voice_file else 'OFF'}")

    scene_vids, total_duration, k = [], 0.0, 0
    pans = [0, 1, -1, 1, 0, -1]
    for idx, sc in enumerate(story["scenes"]):
        dur = durs[idx] if durs else min(calculate_reading_duration(sc), MAX_SCENE_SECONDS)
        beats = scene_beats(sc, dur)
        if durs:  # keep beats in sync with the voice clip length
            scale = dur / sum(d for _, d in beats)
            beats = [(b, round(d * scale, 2)) for b, d in beats]
        texts, t0 = [], 0.0
        for j, (beat, bdur) in enumerate(beats):
            print(f"Rendering scene {idx+1}.{j+1} ({bdur}s): {beat['text'][:40]}")
            render_scene_layers(beat, f"bg_{idx+1}.png" if j == 0 else "bg_tmp.png", f"txt_{idx+1}_{j+1}.png")
            if j == 0:
                sc["accent"] = beat.get("accent")
            texts.append((f"txt_{idx+1}_{j+1}.png", round(t0, 2), round(t0 + bdur, 2) if j < len(beats) - 1 else 999))
            t0 += bdur
        if idx == 0:
            # cover image = the hook slide
            Image.alpha_composite(Image.open("bg_1.png").convert("RGBA"),
                                  Image.open("txt_1_1.png").convert("RGBA")).convert("RGB").save("cover.jpg", quality=92)
        k += 1
        total_duration += round(t0, 2)
        out_vid = f"scene_{idx+1}.mp4"
        render_scene_clip(f"bg_{idx+1}.png", texts, round(t0, 2), out_vid,
                          zoom_in=(k % 2 == 1), pan=pans[k % len(pans)])
        scene_vids.append(out_vid)

    cta_dur = CTA_SECONDS
    cta_voice = None
    if voice_file:
        L = tts(cta_scene()["say"], "vo_cta.mp3")
        if L:
            cta_dur = round(max(CTA_SECONDS, L + 0.3), 2)
            cta_voice = "vo_cta.mp3"
    print(f"Rendering your end slide ({cta_dur}s)...")
    make_cta_slide("f_cta.png")
    render_motion_clip("f_cta.png", None, cta_dur, "scene_cta.mp4", still=True)
    scene_vids.append("scene_cta.mp4")
    total_duration = round(total_duration + cta_dur, 2)

    with open("playlist.txt", "w") as f:
        for v in scene_vids:
            f.write(f"file '{v}'\n")

    if cta_voice:
        content = total_duration - cta_dur
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", voice_file, "-i", cta_voice, "-filter_complex",
                        f"[0:a]apad,atrim=0:{content}[a];[1:a]aformat=sample_rates=44100:channel_layouts=stereo[b];"
                        f"[a][b]concat=n=2:v=0:a=1[o]", "-map", "[o]", "voice_full.wav"], check=True)
        voice_file = "voice_full.wav"

    music = pick_music(total_duration)
    fade_start = max(0.5, round(total_duration - 1.2, 2))
    if voice_file:
        # music ducked under the voice
        fc = (f"[1:a]volume=0.16,afade=t=out:st={fade_start}:d=1.2[m];"
              f"[2:a]volume=1.6,apad[v];"
              f"[m][v]amix=inputs=2:duration=first:dropout_transition=0,"
              f"atrim=0:{total_duration}[aout]")
        inputs = ["-stream_loop", "-1", "-i", music, "-i", voice_file]
    else:
        fc = f"[1:a]afade=t=out:st={fade_start}:d=1.2[aout]"
        inputs = ["-stream_loop", "-1", "-i", music]
    # persistent news frame + crawling ticker over the whole segment (not the CTA)
    frame_png, label_w = make_news_frame(story)
    strip_png, strip_w = make_ticker_strip(story)
    seg_end = round(total_duration - cta_dur, 2)
    n_in = 3 if voice_file else 2
    fi, si = n_in, n_in + 1
    speed = 170  # px per second
    vf = (f"[{si}:v]crop={W - label_w}:{TICKER_H}:'mod(t*{speed},{strip_w})':0[tk];"
          f"[0:v][{fi}:v]overlay=0:0:enable='lt(t,{seg_end})'[v1];"
          f"[v1][tk]overlay={label_w}:{TICKER_Y}:enable='lt(t,{seg_end})',format=yuv420p[vout];")
    inputs += ["-loop", "1", "-framerate", "30", "-i", frame_png, "-loop", "1", "-framerate", "30", "-i", strip_png]
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        *inputs,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", vf + fc,
        "-map", "[vout]", "-map", "[aout]",
        "-t", str(total_duration),
        output_mp4
    ], check=True)
    return output_mp4

def compile_live_action_reel(story, output_mp4="pokepulse_reel.mp4"):
    """Old name kept so anything that imports it still works (no voice)."""
    return compile_reel(story, output_mp4, voice=False)

# ---------------------------------------------------------------- publishing

def publish_to_account(video_url, caption, graph, user_id, access_token, label, cover_url=None):
    print(f"\n===== Posting to {label} =====")
    print("Step 1: Publishing Reel to Instagram...")
    res = requests.post(f"{graph}/{user_id}/media", data={
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        **({"cover_url": cover_url} if cover_url else {}),
        "access_token": access_token
    }).json()

    published = False
    if "id" in res:
        cid = res["id"]
        print(f"Reel Container: {cid}. Transcoding...")
        for _ in range(18):
            time.sleep(10)
            status = requests.get(f"{graph}/{cid}", params={"fields": "status_code", "access_token": access_token}).json()
            code = status.get("status_code")
            print(f"Status: {code}")
            if code == "FINISHED":
                break
            elif code == "ERROR":
                print("Encoding error on Instagram.")
                break

        pub = requests.post(f"{graph}/{user_id}/media_publish", data={
            "creation_id": cid,
            "access_token": access_token
        }).json()
        print(f"Reel Publish Result: {pub}")
        published = "id" in pub
    else:
        print("Reel Error:", res)

    print("\nStep 2: Publishing to Story...")
    s_res = requests.post(f"{graph}/{user_id}/media", data={
        "media_type": "STORIES",
        "video_url": video_url,
        "access_token": access_token
    }).json()

    if "id" in s_res:
        sid = s_res["id"]
        for _ in range(12):
            time.sleep(8)
            s_status = requests.get(f"{graph}/{sid}", params={"fields": "status_code", "access_token": access_token}).json()
            if s_status.get("status_code") == "FINISHED":
                break
        s_pub = requests.post(f"{graph}/{user_id}/media_publish", data={
            "creation_id": sid,
            "access_token": access_token
        }).json()
        print(f"Story Publish Result: {s_pub}")
    else:
        print("Story Error:", s_res)
    return published

def second_account():
    """@pokepulse.io - same Facebook-login setup as card.stax (never-expiring Page token)."""
    token = os.getenv("IG_TOKEN_2", "").strip()
    user_id = os.getenv("IG_USER_ID_2", "").strip()
    if not token or not user_id:
        print("IG_TOKEN_2 / IG_USER_ID_2 not set - only posting to the main account.")
        return None
    return (GRAPH, user_id, token, "second account (@pokepulse.io)")

def publish_content(video_url, caption, cover_url=None):
    accounts = []
    token1 = os.getenv("IG_ACCESS_TOKEN", "").strip()
    if token1:
        accounts.append((GRAPH, IG_USER_ID, token1, "main account (IG_ACCESS_TOKEN)"))
    acct2 = second_account()
    if acct2:
        accounts.append(acct2)

    any_ok = False
    for graph, uid, tok, label in accounts:
        try:
            ok = publish_to_account(video_url, caption, graph, uid, tok, label, cover_url)
        except Exception as e:
            print(f"{label} failed: {e}")
            ok = False
        any_ok = any_ok or ok
    return any_ok

if __name__ == "__main__":
    story = build_story()
    if story is None:
        print("Nothing new to post on any topic right now - skipping this run (nothing repeated).")
        sys.exit(0)

    print(f"Producing Reel: {story['story_id']}")
    # New look + voiceover on 3 of every 4 posts is built right here now.
    # The old reel_v2.py engine only runs if you set USE_REEL_V2=1.
    mp4_file = None
    if os.getenv("USE_REEL_V2", "").strip().lower() in ("1", "true", "yes"):
        try:
            from reel_v2 import compile_voiced_reel
            mp4_file = compile_voiced_reel(story, "pokepulse_reel.mp4")
            print("Built voiced reel (v2)")
        except Exception as e:
            print(f"reel_v2 failed ({e}) - using the built-in engine")
    if mp4_file is None:
        mp4_file = compile_reel(story, "pokepulse_reel.mp4")

    cover_url = None
    if os.path.exists("cover.jpg"):
        try:
            cover_url = cloudinary.uploader.upload("cover.jpg", folder="pokepulse_covers").get("secure_url")
            print(f"Cover uploaded: {cover_url}")
        except Exception as e:
            print(f"Cover upload failed ({e}) - posting without custom cover")

    if os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes"):
        print("DRY RUN - nothing posted.")
        sheet_url = vid_url = ""
        try:
            # contact sheet: one frame every second, so the whole reel can be reviewed at a glance
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4_file, "-vf",
                            "fps=1,scale=270:-1,tile=6x4:padding=4:color=white", "-frames:v", "1",
                            "test_sheet.jpg"], check=True)
            sheet_url = cloudinary.uploader.upload("test_sheet.jpg", folder="pokepulse_tests").get("secure_url")
            vid_url = cloudinary.uploader.upload_large(mp4_file, resource_type="video",
                                                       folder="pokepulse_tests").get("secure_url")
        except Exception as e:
            print(f"Couldn't upload test preview: {e}")
        print(f"TEST SHEET: {sheet_url}\nTEST VIDEO: {vid_url}\nTEST COVER: {cover_url}")
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as f:
                f.write(f"## Test reel: {story['story_id']}\n\n**Topic:** {story.get('topic')}\n\n"
                        f"[▶ Watch the video]({vid_url})\n\n**Cover:**\n\n![cover]({cover_url})\n\n"
                        f"**Every second of the reel:**\n\n![sheet]({sheet_url})\n\n"
                        f"**Caption:**\n\n```\n{story['caption_full']}\n```\n")
        sys.exit(0)

    print("Uploading to Cloudinary CDN...")
    upload_res = cloudinary.uploader.upload_large(mp4_file, resource_type="video", folder="pokepulse_reels")
    video_cdn_url = upload_res.get("secure_url")
    print(f"CDN URL: {video_cdn_url}")

    if publish_content(video_cdn_url, story["caption_full"], cover_url):
        with open("posted_news.txt", "a") as f:
            f.write(story["key"] + "\n")
