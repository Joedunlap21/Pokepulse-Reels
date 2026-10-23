"""
Real photos for the things a reel talks about, in this order:
  1. TCGplayer product search  (booster packs, promos, boxes, tins... exact product photos)
  2. Google image search        (playmats, coins, sleeves... "30th Celebration Ultra-Premium Collection playmat")
     needs repo secrets GOOGLE_API_KEY + GOOGLE_CSE_ID (free: 100 searches/day)
  3. nothing found -> caller falls back to the drawn item art
A result is only used when its title really matches what we searched for.
"""
import os
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36", "content-type": "application/json",
      "origin": "https://www.tcgplayer.com", "referer": "https://www.tcgplayer.com/"}
STOP = {"pokemon", "pokémon", "tcg", "the", "and", "with", "card", "cards", "a", "of", "for", "featuring", "1"}
_cache = {}


def _w(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower().replace("é", "e")) if w not in STOP and len(w) > 1}


def _match(query, title):
    q = _w(query)
    return len(q & _w(title)) / len(q) if q else 0


def tcgplayer(query, size=12, line="pokemon"):
    """TCGplayer product search. line: "pokemon" or "one-piece-card-game"."""
    key = ("tcg", query, line)
    if key in _cache:
        return _cache[key]
    body = {"algorithm": "", "from": 0, "size": size,
            "filters": {"term": {"productLineName": [line]}, "range": {}, "match": {}},
            "listingSearch": {"context": {"cart": {}}, "filters": {"term": {"sellerStatus": "Live", "channelId": 0},
                                                                "range": {"quantity": {"gte": 1}},
                                                                "exclude": {"channelExclusion": 0}}},
            "context": {"cart": {}, "shippingCountry": "US", "userProfile": {}},
            "settings": {"useFuzzySearch": False, "didYouMean": {}}, "sort": {}}
    out = []
    try:
        r = requests.post("https://mp-search-api.tcgplayer.com/v1/search/request",
                          params={"q": query, "isList": "false"}, json=body, headers=UA, timeout=20)
        out = (r.json().get("results") or [{}])[0].get("results") or []
    except Exception as e:
        print(f"  TCGplayer search '{query}' failed: {e}")
    _cache[key] = out
    return out


def best_product(query, line="pokemon", want="any", min_match=0.6):
    """Photo URL of the TCGplayer product that best matches `query`, or None.
    want: "sealed" (boxes, packs, tins), "card" (single cards) or "any"."""
    best, best_score = None, 0
    for r in tcgplayer(query, 24, line):
        name = r.get("productName", "")
        low = name.lower()
        if "code card" in low or "case" in low.split() or not r.get("productId"):
            continue
        score = _match(query, name + " " + r.get("setName", ""))
        if score < min_match:
            continue
        sealed = bool(r.get("sealed")) or "sealed" in str(r.get("productTypeName", "")).lower()
        if want == "sealed" and sealed or want == "card" and not sealed:
            score += 0.3
        score += min(float(r.get("marketPrice") or 0), 500) / 5000      # popular / valuable first on ties
        if score > best_score:
            best, best_score = r, score
    if best:
        print(f"  picture '{query}': TCGplayer #{best['productId']} {best.get('productName')}")
        return tcg_img(best["productId"])
    return None


def tcg_img(pid):
    return f"https://tcgplayer-cdn.tcgplayer.com/product/{int(pid)}_in_1000x1000.jpg"


def google_image(query):
    key, cx = os.getenv("GOOGLE_API_KEY", "").strip(), os.getenv("GOOGLE_CSE_ID", "").strip()
    if not key or not cx:
        return None
    ck = ("g", query)
    if ck in _cache:
        return _cache[ck]
    url = None
    try:
        r = requests.get("https://www.googleapis.com/customsearch/v1",
                         params={"key": key, "cx": cx, "q": query, "searchType": "image", "num": 8,
                                 "safe": "active", "imgSize": "large"}, timeout=20).json()
        for it in r.get("items", []):
            title = (it.get("title") or "") + " " + (it.get("image", {}).get("contextLink") or "")
            w, h = it.get("image", {}).get("width", 0), it.get("image", {}).get("height", 0)
            if min(w, h) >= 300 and _match(query, title) >= 0.5 and not it["link"].lower().endswith(".svg"):
                url = it["link"]
                break
        if not url and r.get("error"):
            print(f"  Google image search error: {r['error'].get('message')}")
    except Exception as e:
        print(f"  Google image search '{query}' failed: {e}")
    _cache[ck] = url
    return url


def brave_image(query):
    """Brave Search image API (repo secret BRAVE_API_KEY). Free monthly credit covers this bot's usage."""
    key = os.getenv("BRAVE_API_KEY", "").strip()
    if not key:
        return None
    ck = ("b", query)
    if ck in _cache:
        return _cache[ck]
    url = None
    try:
        r = requests.get("https://api.search.brave.com/res/v1/images/search",
                         params={"q": query, "count": 10, "safesearch": "strict"},
                         headers={"X-Subscription-Token": key, "Accept": "application/json"}, timeout=20).json()
        for it in r.get("results", []):
            title = (it.get("title") or "") + " " + (it.get("url") or "")
            img = (it.get("properties") or {}).get("url") or (it.get("thumbnail") or {}).get("src")
            if img and _match(query, title) >= 0.5 and not img.lower().endswith(".svg"):
                url = img
                break
    except Exception as e:
        print(f"  Brave image search '{query}' failed: {e}")
    _cache[ck] = url
    return url


def find(kind, set_name="", product="", name=""):
    """Best real photo URL for an item, or None. kind: packs | promo | playmat | coin | dice | sleeves |
    deckbox | binder | code | cards | figure"""
    set_name = re.sub(r"^(ME|SV|SWSH)\s*:\s*", "", set_name or "").strip()
    product = re.sub(r"^Pok[eé]mon TCG:\s*", "", product or "").strip()
    # 1. TCGplayer
    if kind == "packs" and set_name:
        q = f"{set_name} Booster Pack"
        for r in tcgplayer(q):
            n = r.get("productName", "")
            if "booster pack" in n.lower() and not n.lower().startswith("code card") \
                    and _match(set_name, n + " " + r.get("setName", "")) >= 0.99 and "case" not in n.lower():
                print(f"  picture '{q}': TCGplayer #{r['productId']} {n}")
                return tcg_img(r["productId"])
    if kind == "promo" and name:
        for q in (f"{name} {set_name} promo".strip(), f"{name} promo"):
            for r in tcgplayer(q):
                n, s = r.get("productName", ""), r.get("setName", "")
                if "promo" in s.lower() and n.lower().startswith(name.lower()):
                    print(f"  picture '{q}': TCGplayer #{r['productId']} {n} ({s})")
                    return tcg_img(r["productId"])
    if kind in ("figure", "binder", "deckbox", "sleeves", "playmat", "coin", "dice") and product:
        pass                                             # TCGplayer only sells these inside the product
    # 2. Google image search
    label = {"packs": "booster pack", "promo": f"{name} promo card", "playmat": "playmat", "coin": "coin",
             "dice": "dice", "sleeves": "card sleeves", "deckbox": "deck box", "binder": "binder",
             "code": "code card", "cards": "cards", "figure": f"{name} figure",
             "oversize": f"{name} oversize card", "display": "acrylic card display"}.get(kind, kind)
    q = f"{product or set_name} {label}".strip()
    url = google_image(q)             # Google's API is closed to new accounts - kept in case yours works
    if url:
        print(f"  picture '{q}': Google image")
        return url
    url = brave_image(q)
    if url:
        print(f"  picture '{q}': Brave image search")
    return url
