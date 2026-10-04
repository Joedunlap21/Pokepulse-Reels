import os
import json
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

IMG_BOTTOM = 1110   # art area is 0..IMG_BOTTOM
TAG_Y = 1130        # red tag pill
TEXT_TOP = 1230     # text block starts here
TEXT_BOTTOM = 1860  # and must end above here
TEXT_MAX_W = 960

# ---------------------------------------------------------------- fonts

def ensure_font():
    if not os.path.exists("BebasNeue.ttf"):
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf"
        r = requests.get(url, headers=API_HEADERS, timeout=20)
        with open("BebasNeue.ttf", "wb") as f:
            f.write(r.content)

ensure_font()

_font_cache = {}
def get_font(size):
    if size not in _font_cache:
        try:
            _font_cache[size] = ImageFont.truetype("BebasNeue.ttf", size)
        except Exception:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]

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
    # shorter slides: ~2s for a headline, max 4s for the longest text
    return round(max(1.8, min(0.9 + words * 0.2, 4.0)), 2)

# ---------------------------------------------------------------- sources

# The bot rotates 4 topics:  news | drops | sales | bulk
#   news  = latest Pokemon TCG news from the 4 outlets below
#   drops = latest preorder / release / retailer drop article (where, when, price, what's inside)
#   sales = big card sales, PSA 10 / graded auction records
#   bulk  = "Bulk Gold": commons & uncommons from a recent set that are worth real money (TCGplayer prices)
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
    # only pictures that are ABOUT this story: the article's main image, plus in-article images whose
    # alt text / file name shares a real word with the headline (drops related-article thumbnails etc.)
    topic_words = {w for w in re.findall(r"[a-z0-9]{4,}", (title + " " + desc).lower().replace("pokémon", "pokemon"))
                   if w not in ("pokemon", "cards", "card", "with", "from", "that", "this", "have", "just", "more",
                                "after", "their", "they", "will", "into", "about", "what", "your")}
    cands = [(u, "", True) for u in meta_all(page, "og:image")]
    for tag in re.findall(r"<img[^>]+>", seg):
        m = re.search(r'(?:data-src|src)="([^"]+)"', tag)
        if m:
            alt = (re.search(r'alt="([^"]*)"', tag) or [None, ""])[1]
            cands.append((m.group(1), html.unescape(alt), False))
    for u, alt, is_main in cands:
        u = full_size(u)
        if u.startswith("/"):
            u = src["base"] + u
        if not good_image(u) or u.split("?")[0] in [x.split("?")[0] for x in images]:
            continue
        if not is_main:
            words = set(re.findall(r"[a-z0-9]{4,}", (alt + " " + u.rsplit("/", 1)[-1]).lower().replace("pokémon", "pokemon")))
            if not (words & topic_words):
                continue
        images.append(u)

    art = {"source": src["name"], "url": url, "title": title, "desc": desc, "paras": paras,
           "items": items, "images": images[:src.get("max_imgs", 4)], "published": published}
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

# ---------------------------------------------------------------- topic: news / sales

def fit_list(parts, max_words=26):
    out = []
    for p in parts:
        if len(" ".join(out + [p]).split()) > max_words:
            break
        out.append(p)
    return out

def build_article_story(art, kind):
    sents = all_sentences(art)
    if kind == "sales":
        money = [s for s in sents if "$" in s or "psa" in s.lower() or "million" in s.lower()]
        details = (money + [s for s in sents if s not in money])[:3]
        first_tag, tags = "BIG SALE ALERT", ["THE SALE", "THE DETAILS", "WHY IT MATTERS"]
    else:
        details = sents[:3]
        first_tag, tags = "BREAKING NEWS", ["THE DETAILS", "WHAT TO KNOW", "KEY INFO"]
    if not details:
        return None
    imgs = art["images"]
    scenes = [{"tag": first_tag, "img_url": imgs[0], "text": art["title"].upper(),
               "colors": [YELLOW, WHITE], "sub": "POKEPULSE EXCLUSIVE"}]
    for i, s in enumerate(details):
        scenes.append({"tag": tags[i], "img_url": imgs[(i + 1) % len(imgs)], "text": s.upper(),
                       "colors": [WHITE, YELLOW] if i % 2 == 0 else [YELLOW, WHITE]})
    return {"story_id": art["title"][:40], "key": art["title"].lower(), "scenes": scenes,
            "caption_full": article_caption(art, sents)}

def article_caption(art, sents, lead="🚨"):
    text = ""
    for s in sents:
        if len(text) + len(s) + 1 > 900:
            break
        text = (text + " " + s).strip()
    return (f"{lead} {art['title']}\n\n{text}\n\nSource: {art['source']}\n\n"
            f"What are your thoughts on this? Drop your reaction below! 👇\n\n"
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
    products = [i for i in art["items"] if re.search(r"box|bundle|tin|collection|pack|blister|binder|limit|deck", i, re.I)]

    imgs = art["images"]
    scenes = [{"tag": "DROP REPORT", "img_url": imgs[0], "text": art["title"].upper(), "colors": [YELLOW, WHITE]}]
    def add(tag, text, colors):
        scenes.append({"tag": tag, "img_url": imgs[len(scenes) % len(imgs)], "text": text.upper(), "colors": colors})
    if where:
        add("WHERE", "\n".join(fit_list(where, 14)), [YELLOW, WHITE])
    if when:
        add("WHEN", when[0], [WHITE, YELLOW])
    if products:
        add("WHAT'S DROPPING", "\n".join(fit_list(products, 24)), [WHITE, YELLOW])
    if price:
        add("PRICE", " ".join(fit_list(price, 28)), [YELLOW, WHITE])
    if inside:
        add("WHAT'S INSIDE", inside[0], [WHITE, YELLOW])
    if len(scenes) < 3:
        return None  # not enough real drop facts in this article

    lines = [f"🛒 DROP REPORT: {art['title']}", ""]
    if where:
        lines.append("📍 Where: " + ", ".join(where))
    if when:
        lines.append("📅 When: " + when[0])
    if products:
        lines.append("📦 Products: " + "; ".join(products[:8]))
    if price:
        lines.append("💲 Price: " + " ".join(price[:3]))
    if inside:
        lines.append("🎁 Inside: " + inside[0])
    lines += ["", f"Source: {art['source']}", "",
              "Which one are you grabbing? 👇", "",
              "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!", "",
              "#PokemonCards #PokemonTCG #CardStax #PokemonRestock #PokePulse #PokemonNews"]
    return {"story_id": art["title"][:40], "key": art["title"].lower(), "scenes": scenes,
            "caption_full": "\n".join(lines)}

# ---------------------------------------------------------------- topic: upcoming drop - what's inside

INSIDE_RE = r"\b(contains?|includes?|including|comes with|inside|booster packs?|promo cards?|foil|sleeves|dice|coin|playmat)\b"
UPCOMING_RE = r"\b(upcoming|pre-?orders?|will (?:be )?release|releases?|releasing|launch(?:es|ing)?|coming|available (?:on|starting)|hits? (?:shelves|stores))\b"

def build_inside_story(art):
    """Upcoming product + exactly what's in the box (packs, promos, accessories) + price/date when given."""
    sents = all_sentences(art)
    blob = " ".join([art["title"], art["desc"]] + art["paras"] + art["items"])
    if not re.search(UPCOMING_RE, blob, re.I):
        return None
    inside = [s for s in sents if re.search(INSIDE_RE, s, re.I)]
    contents = [i for i in art["items"] if re.search(r"pack|promo|card|sleeve|dice|coin|marker|box|pin|figure|playmat|binder|sticker", i, re.I)]
    when = [s for s in sents if re.search(MONTHS + r"\s+\d{1,2}", s)]
    price = [s for s in sents if re.search(r"\$\s?\d", s)] + [i for i in art["items"] if re.search(r"\$\s?\d", i)]
    if not inside and len(contents) < 2:
        return None
    imgs = art["images"]
    scenes = [{"tag": "WHAT'S INSIDE", "img_url": imgs[0], "text": art["title"].upper(), "colors": [YELLOW, WHITE]}]
    def add(tag, text, colors):
        scenes.append({"tag": tag, "img_url": imgs[len(scenes) % len(imgs)], "text": text.upper(), "colors": colors})
    if contents:
        add("WHAT'S INSIDE", "\n".join(fit_list(contents, 26)), [WHITE, YELLOW])
    for s in inside[:2]:
        add("WHAT'S INSIDE", s, [WHITE, YELLOW])
    if when:
        add("RELEASE DATE", when[0], [YELLOW, WHITE])
    price = [p for p in price if p not in inside[:2]]
    if price:
        add("PRICE", " ".join(fit_list(price, 28)), [YELLOW, WHITE])
    if len(scenes) < 3:
        return None
    lines = [f"📦 WHAT'S INSIDE: {art['title']}", ""]
    if contents:
        lines += ["Inside the box:"] + [f"• {c}" for c in contents[:10]] + [""]
    for s in inside[:3]:
        lines.append(s)
    if when:
        lines.append("📅 Release: " + when[0])
    if price:
        lines.append("💲 Price: " + " ".join(price[:2]))
    lines += ["", f"Source: {art['source']}", "",
              "Are you picking this one up? 👇", "",
              "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!", "",
              "#PokemonCards #PokemonTCG #CardStax #PokemonRestock #PokePulse #PokemonNews"]
    return {"story_id": art["title"][:40], "key": art["title"].lower(), "scenes": scenes,
            "caption_full": "\n".join(lines)}

# Official product pages: launch date + exact "includes" list + official pictures
GALLERY = "https://www.pokemon.com/us/pokemon-tcg/product-gallery"

def parse_gallery(url):
    page = get_html(url)
    i = page.find("<article")
    art = page[i:page.find("</article>", i)] if i >= 0 else page
    h1 = re.findall(r"<h1[^>]*>(.*?)</h1>", art, re.S)
    title = clean_text(re.sub(r"<[^>]+>", " ", h1[0])) if h1 else clean_text((meta_all(page, "og:title") or [""])[0])
    title = re.split(r"\s+\|\s+", title)[0].strip()
    m = re.search(r"Launch:\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})", re.sub(r"<[^>]+>", " ", art))
    launch = None
    if m:
        try:
            launch = datetime.strptime(re.sub(r"\s+", " ", m.group(1)), "%B %d, %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    items = [clean_text(re.sub(r"<[^>]+>", " ", x)) for x in re.findall(r"<li[^>]*>(.*?)</li>", art, re.S)]
    items = [x for x in items if x and len(x) < 140]
    paras = [clean_text(re.sub(r"<[^>]+>", " ", x)) for x in re.findall(r"<p[^>]*>(.*?)</p>", art, re.S)]
    paras = [p for p in paras if len(p.split()) >= 5]
    imgs = []
    for u in re.findall(r'<img[^>]+src="([^"]+)"', art):
        u = html.unescape(u)
        u = "https://www.pokemon.com" + u if u.startswith("/") else u
        if "/inline/" in u and u not in imgs:
            imgs.append(u)
    og = (meta_all(page, "og:image") or [""])[0]
    return {"url": url, "title": title, "launch": launch, "items": items, "paras": paras, "images": imgs, "og": og}

CACHE_FILE = "products_cache.json"

def _load_product_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f).get("products", {})
        for v in data.values():
            v["launch"] = datetime.fromisoformat(v["launch"]).replace(tzinfo=timezone.utc) if v.get("launch") else None
        return data
    except Exception as e:
        print(f"No product cache ({e})")
        return {}

def build_gallery_inside_story(captions, posted):
    """Next upcoming official product we haven't posted yet, with exactly what's inside.
    Uses products_cache.json first and only visits Pokemon.com pages it hasn't seen,
    so the bot makes 1-3 requests a run instead of 14 (Pokemon.com blocks heavy crawling)."""
    products = _load_product_cache()
    links = []
    try:
        listing = get_html(GALLERY)
        for h in re.findall(r'href="((?:https://www\.pokemon\.com)?/us/pokemon-tcg/product-gallery/[a-z0-9\-]+)"', listing):
            h = h if h.startswith("http") else "https://www.pokemon.com" + h
            if h not in links:
                links.append(h)
    except Exception as e:
        print(f"Product gallery listing failed ({e}) - using the saved product list")
    new_links = [u for u in links if u not in products][:5]
    for u in new_links:          # only brand-new products get fetched, slowly
        time.sleep(1.5)
        try:
            products[u] = parse_gallery(u)
            print(f"  new product page: {products[u]['title']}")
        except Exception as e:
            print(f"  gallery page failed {u}: {e}")
            break
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cands = []
    for p in products.values():
        if not p.get("launch") or p["launch"] < today or len(p.get("items") or []) < 2 \
                or not (p.get("images") or p.get("og")):
            continue
        if already_posted(p["title"], posted, captions):
            print(f"  already posted: {p['title']}")
            continue
        cands.append(p)
    if not cands:
        print("No upcoming official products left to post")
        return None
    p = min(cands, key=lambda x: x["launch"])
    when = p["launch"].strftime("%B ") + str(p["launch"].day)
    name = re.sub(r"^Pok[eé]mon TCG:\s*", "", p["title"])
    pool = p["images"] + ([p["og"]] if p["og"] else [])
    scenes = [{"tag": "WHAT'S INSIDE", "img_url": pool[0], "text": name.upper(), "colors": [YELLOW, WHITE]},
              {"tag": "WHAT'S INSIDE", "img_url": pool[0], "text": "\n".join(fit_list(p["items"], 30)).upper(),
               "colors": [WHITE, YELLOW]},
              {"tag": "RELEASE DATE", "img_url": pool[-1], "text": f"LAUNCHES {when.upper()}", "colors": [YELLOW, WHITE]}]
    context = (f"{p['title']}. Launch: {p['launch'].strftime('%B %d, %Y')} ({when}). Includes: "
               + "; ".join(p["items"]) + ". " + " ".join(p.get("paras") or []))
    if p.get("msrp"):
        context += f" MSRP: ${p['msrp']:,.2f}."
    cap = [f"📦 WHAT'S INSIDE: {p['title']}", "", "Inside the box:"] + [f"• {x}" for x in p["items"]] + \
          ["", f"📅 Launches {p['launch'].strftime('%B %d, %Y')}", "", "Source: Pokemon.com", "",
           "Are you picking this one up? 👇", "",
           "📬 Free Weekly Pokémon Market & Restock Reports -> Link in Bio!", "",
           "#PokemonCards #PokemonTCG #CardStax #PokemonRestock #PokePulse #PokemonNews"]
    # set logo + the set's top popular chase cards (real TCGplayer prices) for extra frames
    logo_url, chase, chase_txt = None, [], ""
    try:
        sets = tcg_get("sets", {"orderBy": "-releaseDate", "pageSize": 40}).get("data", [])
        low = p["title"].lower()
        match = sorted([st for st in sets if st.get("name") and st["name"].lower() in low],
                       key=lambda st: -len(st["name"]))
        if match:
            st = match[0]
            logo_url = (st.get("images") or {}).get("logo")
            cards = tcg_get("cards", {"q": f'set.id:{st["id"]}', "pageSize": 250,
                                      "select": "id,name,number,rarity,images,tcgplayer"}).get("data", [])
            ranked = []
            for c in cards:
                m_, v_ = best_market(c)
                img = (c.get("images") or {}).get("large")
                if m_ >= CHASE_MIN_PRICE and img and is_popular(c):
                    ranked.append({"name": c["name"], "price": round(m_, 2), "img": img})
            ranked.sort(key=lambda x: -x["price"])
            chase = ranked[:3]
            if chase:
                chase_txt = (f" TOP CHASE CARDS in {st['name']} (TCGplayer market): "
                             + "; ".join(f"{c['name']} ${c['price']:,.2f}" for c in chase) + ".")
                print(f"  set {st['name']}: chase {[c['name'] for c in chase]}")
    except Exception as e:
        print(f"  set/chase lookup failed: {e}")
    context += chase_txt
    print(f"Picked [inside] official product: {p['title']} (launch {when})")
    return {"story_id": p["title"][:40], "key": p["title"].lower(), "scenes": scenes, "topic": "inside",
            "context": context, "image_pool": pool, "bg_url": p["og"] or None,
            "logo_url": logo_url, "chase": chase, "msrp": p.get("msrp"),
            "caption_full": "\n".join(cap)}

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

def price_info(card, variant, market):
    """Numbers for the price box next to the card: TCGplayer low / market / high
    + 30-day trend (Cardmarket 1-day avg vs 30-day avg, shown only as a %)."""
    p = ((card.get("tcgplayer") or {}).get("prices") or {}).get(variant) or {}
    cm = (card.get("cardmarket") or {}).get("prices") or {}
    trend = None
    a1, a30 = cm.get("avg1") or cm.get("avg7"), cm.get("avg30")
    if a1 and a30:
        trend = (a1 / a30 - 1) * 100
    return {"market": market, "low": p.get("low"), "high": p.get("high"), "trend": trend}

def say_dollars(m):
    """$12.34 -> '12 dollars and 34 cents' so the voiceover says dollars."""
    d, c = int(m), int(round((m - int(m)) * 100))
    if c == 100:
        d, c = d + 1, 0
    return f"{d:,} dollars" + (f" and {c} cents" if c else "")

VARIANT_NAMES = {"normal": "", "holofoil": "HOLO", "reverseHolofoil": "REVERSE HOLO",
                 "1stEditionNormal": "1ST EDITION", "1stEditionHolofoil": "1ST EDITION HOLO"}

# Only post cards collectors actually care about (popular Pokemon / trainers) at real prices.
# Edit these lists / numbers any time.
POPULAR = ["charizard", "pikachu", "raichu", "mewtwo", "mew", "eevee", "umbreon", "espeon", "sylveon", "vaporeon",
           "jolteon", "flareon", "leafeon", "glaceon", "gengar", "lugia", "rayquaza", "gardevoir", "greninja",
           "lucario", "snorlax", "dragonite", "gyarados", "blastoise", "venusaur", "bulbasaur", "charmander",
           "squirtle", "gholdengo", "mimikyu", "ditto", "arcanine", "tyranitar", "garchomp", "giratina", "dialga",
           "palkia", "zekrom", "reshiram", "kyogre", "groudon", "suicune", "ho-oh", "celebi", "jirachi", "darkrai",
           "alakazam", "dragapult", "ceruledge", "pecharunt", "terapagos", "ogerpon", "iron valiant", "roaring moon",
           "psyduck", "jigglypuff", "lapras", "articuno", "zapdos", "moltres", "magikarp", "togepi", "piplup",
           "lillie", "iono", "marnie", "cynthia", "misty", "erika", "n's", "team rocket", "ethan", "hop"]
BULK_MIN_PRICE = 5.0     # every card in a Bulk Gold reel must be worth at least this
CHASE_MIN_PRICE = 20.0   # every card in a Top Chase reel must be worth at least this

def is_popular(card):
    name = (card.get("name") or "").lower()
    return any(re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", name) for p in POPULAR)

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
                                  "select": "id,name,number,rarity,images,set,tcgplayer,cardmarket"}).get("data", [])
        ranked = []
        for c in cards:
            m, v = best_market(c)
            img = (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small")
            if m >= BULK_MIN_PRICE and img and is_popular(c):
                ranked.append((m, v, c, img))
        ranked.sort(key=lambda x: -x[0])
        top = ranked[:3]   # 3 cards keeps the reel short
        if len(top) < 3:
            print(f"{st['name']}: not 3 popular commons/uncommons worth ${BULK_MIN_PRICE:.0f}+ yet")
            continue

        updated = (top[0][2].get("tcgplayer") or {}).get("updatedAt", "")
        scenes = [{"tag": "BULK GOLD", "img_url": top[0][3],
                   "text": f"CHECK YOUR BULK! {st['name'].upper()} COMMONS & UNCOMMONS WORTH REAL MONEY",
                   "colors": [YELLOW, WHITE]}]
        cap = [f"💰 Bulk Gold: {st['name']} - don't toss these commons & uncommons!", ""]
        for rank, (m, v, c, img) in enumerate(top, 1):
            vname = VARIANT_NAMES.get(v, v.upper())
            rarity = (c.get("rarity") or "").upper()
            tag = f"#{rank}  {rarity}" + (f"  {vname}" if vname else "")
            scenes.append({"tag": tag, "img_url": img, "text": c["name"].upper(),
                           "colors": [WHITE], "sub": f"${m:,.2f} MARKET  •  #{c['number']}", "sub_size": 110,
                           "prices": price_info(c, v, m),
                           "say": f"Number {rank}. {c['name']}. {say_dollars(m)}."})
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
                                  "select": "id,name,number,rarity,images,set,tcgplayer,cardmarket"}).get("data", [])
        ranked = []
        for c in cards:
            m, v = best_market(c)
            img = (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small")
            if m >= CHASE_MIN_PRICE and img and is_popular(c):
                ranked.append((m, v, c, img))
        ranked.sort(key=lambda x: -x[0])
        top = ranked[:3]   # top 3 keeps the reel short
        if len(top) < 3:
            print(f"{st['name']}: not 3 popular chase cards worth ${CHASE_MIN_PRICE:.0f}+ yet")
            continue
        top = list(reversed(top))   # count down: #5 -> #1
        updated = (top[-1][2].get("tcgplayer") or {}).get("updatedAt", "")
        scenes = [{"tag": "TOP CHASE CARDS", "img_url": top[-1][3],
                   "text": f"THE {len(top)} MOST VALUABLE CARDS IN {st['name'].upper()}",
                   "colors": [YELLOW, WHITE]}]
        cap = [f"🔥 Top Chase Cards: {st['name']} - the most valuable pulls right now", ""]
        for i, (m, v, c, img) in enumerate(top):
            rank = len(top) - i
            rarity = (c.get("rarity") or "").upper()
            scenes.append({"tag": f"#{rank}  {rarity}", "img_url": img, "text": c["name"].upper(),
                           "colors": [WHITE], "sub": f"${m:,.2f} MARKET  •  #{c['number']}", "sub_size": 110,
                           "prices": price_info(c, v, m),
                           "say": f"Number {rank}. {c['name']}. {say_dollars(m)}."})
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


def extra_images(art, need):
    """Real card art to fill slides when an article doesn't have enough pictures."""
    text = (art["title"] + " " + art["desc"] + " " + " ".join(art["paras"][:6])).lower().replace("pokémon", "pokemon")
    found = []
    # 1. a set the article talks about
    sets = tcg_get("sets", {"orderBy": "-releaseDate", "pageSize": 40}).get("data", [])
    for st in sets:
        if st.get("name") and st["name"].lower() in text:
            found += card_images(f'set.id:{st["id"]}', need)
            print(f"Extra images: cards from {st['name']}")
            break
    # 2. Pokemon named in the title / first paragraphs
    if len(found) < need:
        title = (art["title"] + " " + art["desc"]).lower()
        names = [nm for nm in pokemon_names() if len(nm) > 3 and re.search(r"\b" + re.escape(nm) + r"\b", title)]
        for nm in names[:3]:
            found += card_images(f'name:"{nm}"', 3)
            print(f"Extra images: {nm} cards")
            if len(found) >= need:
                break
    # (no random "hot cards" filler - every picture must be about the story)
    return found


def vary_images(story, art):
    """Give every slide its own picture: article images first, then card art."""
    scenes = story["scenes"]
    own = list(dict.fromkeys(art["images"]))
    need = len(scenes) - len(own)
    extras = extra_images(art, max(need, 0) + 6)
    pool = own + [u for u in extras if u not in own]
    story["image_pool"] = pool
    if len(pool) < 2:
        return
    for i, sc in enumerate(scenes):
        sc["img_url"] = pool[i % len(pool)]

# ---------------------------------------------------------------- topic picker

TOPICS = ["news", "drops", "sales", "inside", "chase"]   # bulk removed; chase only when run by hand

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
    # 9:30pm ET run: Upcoming Drop - What's Inside
    return "inside"

def build_story():
    posted = set()
    if os.path.exists("posted_news.txt"):
        with open("posted_news.txt") as f:
            posted = {l.strip().lower() for l in f if l.strip()}
    captions = recent_ig_captions()
    first = topic_for_now()
    order = [first] + [t for t in ["news", "drops", "inside", "sales"] if t != first]
    if first == "inside":                       # no upcoming product? post a drop before plain news
        order = ["inside", "drops", "news", "sales"]
    articles = None

    for topic in order:
        print(f"--- Trying topic: {topic}")
        if topic in ("bulk", "chase"):
            story = build_bulk_story(captions) if topic == "bulk" else build_chase_story(captions)
            if story:
                story["topic"] = topic
                return story
            continue
        if topic == "inside":
            story = build_gallery_inside_story(captions, posted)
            if story:
                return story
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
            elif topic == "inside":
                if word_hits(blob, DROP_WORDS) < 2 or not re.search(INSIDE_RE, blob, re.I):
                    continue
                story = build_inside_story(art)
            elif topic == "sales":
                if word_hits(art["title"] + " " + art["desc"], SALE_WORDS) < 1 or "$" not in blob:
                    continue
                story = build_article_story(art, "sales")
            else:
                story = build_article_story(art, "news")
            if story:
                print(f"Picked [{topic}] {art['source']}: {art['title']}")
                story["topic"] = topic
                story["article_images"] = list(art["images"])     # the article's own pictures
                story["context"] = art["title"] + ". " + " ".join(all_sentences(art)[:12])
                try:
                    vary_images(story, art)
                except Exception as e:
                    print(f"Couldn't add extra images ({e})")
                if topic in ("news", "sales"):
                    try:                          # pictures of the people / places / Pokemon each slide mentions
                        from story_images import enrich
                        enrich(story)
                    except Exception as e:
                        print(f"Story pictures failed ({e}) - using article photos")
                return story
    return None

# ---------------------------------------------------------------- rendering

def load_image(url):
    try:
        data = requests.get(url, headers=API_HEADERS, timeout=15).content
        with open("temp_raw", "wb") as f:
            f.write(data)
        im = Image.open("temp_raw")
        im.load()
        return im.convert("RGB")
    except Exception as e:
        print(f"Error loading image {url}: {e}")
        return None

def render_scene_layers(scene, bg_path, txt_path):
    """bg = artwork (gets the slow zoom), txt = text layer (stays sharp, fades in)."""
    bg = Image.new("RGB", (W, H), BG)
    raw = load_image(scene["img_url"])
    if raw is not None:
        # blurred, darkened fill behind the art so wide/tall images never leave empty bars
        cover = raw.copy()
        scale = max(W / cover.width, IMG_BOTTOM / cover.height)
        cover = cover.resize((int(cover.width * scale) + 1, int(cover.height * scale) + 1), Image.Resampling.LANCZOS)
        left = (cover.width - W) // 2
        top = (cover.height - IMG_BOTTOM) // 2
        cover = cover.crop((left, top, left + W, top + IMG_BOTTOM)).filter(ImageFilter.GaussianBlur(28))
        cover = Image.blend(cover, Image.new("RGB", cover.size, BG), 0.55)
        bg.paste(cover, (0, 0))

        art = raw.copy()
        if scene.get("prices"):
            # card on the left, price box on the right
            art.thumbnail((600, IMG_BOTTOM - 120), Image.Resampling.LANCZOS)
            bg.paste(art, (40 + (600 - art.width) // 2, 60 + (IMG_BOTTOM - 120 - art.height) // 2))
        else:
            art.thumbnail((1000, IMG_BOTTOM - 70), Image.Resampling.LANCZOS)
            bg.paste(art, ((W - art.width) // 2, 40 + (IMG_BOTTOM - 70 - art.height) // 2))

    # real fade from the art into the dark text area (alpha composite, not solid lines)
    fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    f_start = IMG_BOTTOM - 300
    for y in range(f_start, H):
        a = 255 if y >= IMG_BOTTOM else int(255 * ((y - f_start) / 300) ** 1.4)
        fd.line([(0, y), (W, y)], fill=BG + (a,))
    bg = Image.alpha_composite(bg.convert("RGBA"), fade).convert("RGB")
    if scene.get("prices"):
        bg = draw_price_box(bg, scene["prices"])
    bg.save(bg_path)

    # text layer
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)

    tag = scene["tag"]
    tf = get_font(54)
    aw = text_w(d, tag, tf) + 60
    ah = 72
    ax = (W - aw) // 2
    d.rounded_rectangle([ax + 4, TAG_Y + 5, ax + aw + 4, TAG_Y + ah + 5], radius=8, fill=(0, 0, 0, 255))
    d.rounded_rectangle([ax, TAG_Y, ax + aw, TAG_Y + ah], radius=8, fill=RED)
    d.text((ax + 30, TAG_Y + 7), tag, font=tf, fill=WHITE)

    sub = scene.get("sub", "")
    sub_size = scene.get("sub_size", 70)
    sub_h = sub_size + 24 if sub else 0
    font, stroke, lines, line_h = fit_block(d, scene["text"], TEXT_MAX_W, TEXT_BOTTOM - TEXT_TOP - sub_h)
    block_h = len(lines) * line_h + sub_h
    top = TEXT_TOP + max(0, (TEXT_BOTTOM - TEXT_TOP - block_h) // 2)
    y = draw_lines(d, lines, font, stroke, line_h, top, scene["colors"])
    if sub:
        sf = get_font(sub_size)
        d.text(((W - text_w(d, sub, sf, 5)) // 2, y + 14), sub, font=sf, fill=GREEN,
               stroke_fill="#000000", stroke_width=5)
    txt.save(txt_path)

def draw_price_box(img, pr):
    """Price panel beside the card: MARKET (big), LOW, HIGH and the 30-day trend arrow."""
    x0, y0, x1, y1 = 670, 170, W - 40, 990
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y0, x1, y1], radius=26, fill=(8, 8, 12, 215), outline=(255, 255, 255, 60), width=3)
    cx = (x0 + x1) // 2
    def center(text, y, size, color):
        f = get_font(size)
        while text_w(d, text, f) > (x1 - x0) - 40 and size > 30:
            size -= 4
            f = get_font(size)
        d.text((cx - text_w(d, text, f) // 2, y), text, font=f, fill=color)
    def rule(y):
        d.line([(x0 + 30, y), (x1 - 30, y)], fill=(255, 255, 255, 70), width=2)
    money = lambda v: f"${v:,.2f}" if v else "—"
    center("MARKET PRICE", y0 + 30, 46, (255, 255, 255, 200))
    center(money(pr["market"]), y0 + 82, 104, GREEN)
    rule(y0 + 210)
    center("LOW", y0 + 232, 40, (255, 255, 255, 170))
    center(money(pr.get("low")) if pr.get("low") else "N/A", y0 + 272, 70, WHITE)
    rule(y0 + 370)
    center("HIGH", y0 + 392, 40, (255, 255, 255, 170))
    center(money(pr.get("high")) if pr.get("high") else "N/A", y0 + 432, 70, WHITE)
    rule(y0 + 530)
    center("30-DAY TREND", y0 + 552, 40, (255, 255, 255, 170))
    t = pr.get("trend")
    if t is None:
        center("N/A", y0 + 600, 70, WHITE)
    else:
        up = t >= 0
        col = GREEN if up else RED
        label = f"{abs(t):.1f}%"
        f = get_font(80)
        tw = text_w(d, label, f)
        tx = cx - (tw + 60) // 2 + 60
        ty = y0 + 598
        ax = tx - 50
        if up:   # triangle arrow (drawn, since the font has no arrow glyph)
            d.polygon([(ax, ty + 62), (ax + 40, ty + 62), (ax + 20, ty + 22)], fill=col)
        else:
            d.polygon([(ax, ty + 24), (ax + 40, ty + 24), (ax + 20, ty + 64)], fill=col)
        d.text((tx, ty), label, font=f, fill=col)
    center("TCGPLAYER • TREND: CARDMARKET", y1 - 70, 30, (255, 255, 255, 120))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

COVER_LABELS = {"news": "POKÉMON NEWS", "drops": "DROP ALERT", "sales": "BIG SALE", "inside": "WHAT'S INSIDE",
                "bulk": "BULK GOLD", "chase": "CHASE CARDS"}

def make_cover(story, out_path="cover.jpg"):
    """Scroll-stopping thumbnail: big art, red label, huge 2-3 line headline with one yellow word,
    and the top price for card posts. Key stuff sits in the middle so the 3:4 profile-grid crop keeps it."""
    topic = story.get("topic", "news")
    first = story["scenes"][0]
    raw = load_image(first["img_url"])
    base = Image.new("RGB", (W, H), BG)
    if raw is not None:
        cover = raw.copy()
        sc = max(W / cover.width, H / cover.height)
        cover = cover.resize((int(cover.width * sc) + 1, int(cover.height * sc) + 1), Image.Resampling.LANCZOS)
        l, t = (cover.width - W) // 2, (cover.height - H) // 2
        base = Image.blend(cover.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(30)),
                           Image.new("RGB", (W, H), BG), 0.45)
        art = raw.copy()
        art.thumbnail((880, 740), Image.Resampling.LANCZOS)
        ax, ay = (W - art.width) // 2, 390 + (740 - art.height) // 2
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle([ax + 12, ay + 20, ax + art.width + 12, ay + art.height + 20],
                                             radius=20, fill=(0, 0, 0, 210))
        base = Image.alpha_composite(base.convert("RGBA"), sh.filter(ImageFilter.GaussianBlur(24))).convert("RGB")
        base.paste(art, (ax, ay))
    # dark fade behind the headline
    fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    for y in range(1000, H):
        a = min(255, int(255 * ((y - 1000) / 320) ** 1.2))
        fd.line([(0, y), (W, y)], fill=BG + (a,))
    base = Image.alpha_composite(base.convert("RGBA"), fade)
    d = ImageDraw.Draw(base)

    # red label pill near the top of the grid-safe area
    label = COVER_LABELS.get(topic, "POKÉPULSE")
    lf = get_font(76)
    lw = text_w(d, label, lf) + 70
    lx = (W - lw) // 2
    d.rounded_rectangle([lx + 5, 265, lx + lw + 5, 365], radius=12, fill=(0, 0, 0, 255))
    d.rounded_rectangle([lx, 260, lx + lw, 360], radius=12, fill=RED)
    d.text((lx + 35, 268), label, font=lf, fill=WHITE)

    # headline
    prices = [sc_["prices"]["market"] for sc_ in story["scenes"] if sc_.get("prices")]
    set_name = ""
    m = re.search(r"IN (.+)$|^CHECK YOUR BULK! (.+?) COMMONS", first.get("text", ""))
    if m:
        set_name = (m.group(1) or m.group(2) or "").strip()
    if topic == "chase":
        head, small = f"TOP {len(prices) or 3} CHASE CARDS", set_name
    elif topic == "bulk":
        head, small = "YOUR BULK IS WORTH MONEY", set_name
    else:
        words = first.get("text", "").split()
        head, small = " ".join(words[:7]), ""
    words = head.split()
    hot = [i for i, w in enumerate(words) if re.search(r"[\d$]", w)] or \
          [max(range(len(words)), key=lambda i: len(words[i]))]
    extra = (110 if prices else 0) + (70 if small else 0)
    size = 200
    while size > 90:   # biggest size that fits under the art (1160..1670) in max 3 lines
        hf = get_font(size)
        lines = wrap_words(d, head, hf, W - 100, 8)
        if len(lines) <= 3 and len(lines) * int(size * 0.95) + extra <= 510:
            break
        size -= 6
    lh = int(size * 0.95)
    block = len(lines) * lh + extra
    y = 1670 - block
    k = 0
    for line in lines:
        lw_ = text_w(d, line, hf, 8)
        x = (W - lw_) // 2
        for w in line.split():
            d.text((x, y), w, font=hf, fill=YELLOW if k in hot else WHITE, stroke_width=8, stroke_fill="#000000")
            x += text_w(d, w + " ", hf, 8)
            k += 1
        y += lh
    if prices:
        pt = f"UP TO ${max(prices):,.0f}" if max(prices) >= 10 else f"UP TO ${max(prices):,.2f}"
        pf = get_font(110)
        d.text(((W - text_w(d, pt, pf, 6)) // 2, y + 6), pt, font=pf, fill=GREEN, stroke_width=6, stroke_fill="#000000")
        y += 110
    if small:
        sf = get_font(64)
        d.text(((W - text_w(d, small, sf, 4)) // 2, y + 10), small, font=sf, fill=WHITE, stroke_width=4,
               stroke_fill="#000000")
    base.convert("RGB").save(out_path, quality=92)
    return out_path

def make_cta_slide(out_path="f_cta.png"):
    cta_url = "https://i.ibb.co/WpYzjR5T/Carousel-CTA-Slide-2.png"
    base = Image.new("RGB", (W, H), BG)
    cta_img = load_image(cta_url)
    if cta_img is not None:
        cta_img.thumbnail((1080, 1350), Image.Resampling.LANCZOS)
        base.paste(cta_img, ((W - cta_img.width) // 2, 160))
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle([80, 1620, W - 80, 1730], radius=55, fill=YELLOW, outline=WHITE, width=3)
    label = "JOIN FREE WEEKLY POKÉPULSE NEWSLETTER"
    c_font = get_font(52)
    draw.text(((W - text_w(draw, label, c_font)) // 2, 1644), label, font=c_font, fill="#000000")
    base.save(out_path)

def render_motion_clip(bg_path, txt_path, dur, out_vid, zoom_in=True):
    """Slow Ken Burns zoom on the art + text fading in on top."""
    frames = int(dur * 30)
    z = f"1+0.07*on/{frames}" if zoom_in else f"1.07-0.07*on/{frames}"
    inputs = ["-framerate", "30", "-loop", "1", "-t", str(dur), "-i", bg_path]
    if txt_path:
        inputs += ["-framerate", "30", "-loop", "1", "-t", str(dur), "-i", txt_path]
        fc = (f"[0]scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30[bg];"
              f"[1]format=rgba,fade=t=in:st=0.05:d=0.25:alpha=1[tx];"
              f"[bg][tx]overlay=0:0,format=yuv420p[v]")
    else:
        fc = (f"[0]scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps=30,"
              f"format=yuv420p[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + inputs + [
        "-filter_complex", fc, "-map", "[v]", "-t", str(dur),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30", out_vid
    ], check=True)

def compile_live_action_reel(story, output_mp4="pokepulse_reel.mp4"):
    scene_vids = []
    total_duration = 0.0

    for idx, sc in enumerate(story["scenes"]):
        dur = calculate_reading_duration(sc)
        total_duration += dur
        print(f"Rendering scene {idx+1} ({dur}s): {sc['text'][:50]}...")
        render_scene_layers(sc, f"bg_{idx+1}.png", f"txt_{idx+1}.png")
        out_vid = f"scene_{idx+1}.mp4"
        render_motion_clip(f"bg_{idx+1}.png", f"txt_{idx+1}.png", dur, out_vid, zoom_in=(idx % 2 == 0))
        scene_vids.append(out_vid)

    cta_dur = 2.2
    total_duration += cta_dur
    print(f"Rendering newsletter CTA ({cta_dur}s)...")
    make_cta_slide("f_cta.png")
    render_motion_clip("f_cta.png", None, cta_dur, "scene_cta.mp4")
    scene_vids.append("scene_cta.mp4")

    with open("playlist.txt", "w") as f:
        for v in scene_vids:
            f.write(f"file '{v}'\n")

    audio_candidates = glob.glob("audio/*.mp3") + glob.glob("audio/*.wav") + glob.glob("*.mp3")
    audio_candidates = [f for f in audio_candidates if f not in ["bg_audio.mp3", "pokemon_beat.mp3"]]
    if audio_candidates:
        audio_file = random.choice(audio_candidates)
        print(f"Using rotated soundtrack: {audio_file}")
    else:
        audio_file = "bg_audio.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "sine=frequency=220:sample_rate=44100",
                        "-t", str(total_duration), "-c:a", "pcm_s16le", audio_file], check=True)

    fade_start = max(0.5, round(total_duration - 1.2, 2))
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "playlist.txt",
        "-stream_loop", "-1", "-i", audio_file,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-filter_complex", f"[1:a]afade=t=out:st={fade_start}:d=1.2[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-shortest", "-t", str(total_duration),
        output_mp4
    ], check=True)
    return output_mp4

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
    mp4_file = None
    # Drops get the drop-alert format (drops_reel.py). Set repo variable DROPS_STYLE=classic to turn it off.
    if story.get("topic") in ("drops", "inside") and \
            os.getenv("DROPS_STYLE", "").strip().lower() != "classic":
        try:
            from drops_reel import compile_drop_reel
            mp4_file = compile_drop_reel(story, "pokepulse_reel.mp4")
            print("Built drop-alert reel")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Drop-alert reel failed ({e}) - using the normal reel")
            mp4_file = None
    if mp4_file is None:
        try:
            from reel_v2 import compile_voiced_reel
            mp4_file = compile_voiced_reel(story, "pokepulse_reel.mp4")
            print("Built voiced reel (v2)")
        except Exception as e:
            print(f"Voiced reel failed ({e}) - falling back to classic slideshow")
            mp4_file = compile_live_action_reel(story, "pokepulse_reel.mp4")

    try:
        make_cover(story, "cover.jpg")   # our own thumbnail (replaces any auto cover)
        print("Built thumbnail cover.jpg")
    except Exception as e:
        print(f"Thumbnail failed ({e}) - using whatever cover exists")

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
