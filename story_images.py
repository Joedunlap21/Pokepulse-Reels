"""
Pictures of the exact things each slide talks about (Joe, Oct 23: "show the things we are talking about
as pictures... they aren't related or are bad images, make them more correlated with the post").

For every slide we work out WHAT it mentions (Gemini, or a no-AI fallback) and fetch a picture of that
exact thing from the source that has the right kind of photo:
  product / set (booster box, ETB, tin, One Piece OP-14...) -> TCGplayer product photo (Pokemon or One Piece)
  card                                                     -> the real card (pokemontcg.io / TCGplayer One Piece)
  Pokemon species                                          -> official Pokemon artwork (PokeAPI) + its card art
  One Piece character                                      -> that character's One Piece card (TCGplayer)
  video game / person / company / event / venue            -> Wikipedia main photo (title must really match)
  anything else still missing                              -> Brave image search (only if BRAVE_API_KEY is set)
Generic stuff is skipped on purpose: no city skylines for "London", no random hot cards.
The article's own photos fill in after that, and slide 1 always opens on the article's main photo.
"""
import os
import re
import json
import time
import requests

UA = {"User-Agent": "PokePulseBot/1.0 (https://github.com/Joedunlap21/Pokepulse-Reels)"}
WIKI = "https://en.wikipedia.org/w/api.php"
_cache = {}
VENUE_WORDS = ("center", "centre", "store", "shop", "stadium", "convention", "hall", "arena", "museum", "cafe",
               "café", "park", "mall", "expo", "con")
PRODUCT_RE = re.compile(
    r"((?:[A-Z][\w'’.:&-]*\s+){1,5}?(?:Elite Trainer Box|Booster Bundle|Booster Box|Booster Pack|Premium Collection|"
    r"Ultra[- ]Premium Collection|Collection Box|Collection|Tin|Blister|Build & Battle(?: Box| Stadium)?|"
    r"Starter Deck|Double Pack|Premium Booster|Extra Booster|Gift Box|Binder Collection|Poster Collection))")
OP_CODE_RE = re.compile(r"\b(OP|EB|ST|PRB)[- ]?(\d{1,2})\b")


def _words(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 1}


def wiki_image(term):
    """Main photo of the Wikipedia page that matches `term` (only if the page title really matches)."""
    if term in _cache:
        return _cache[term]
    url = None
    try:
        r = requests.get(WIKI, params={"action": "query", "list": "search", "srsearch": term, "srlimit": 3,
                                       "format": "json"}, headers=UA, timeout=15).json()
        for hit in r.get("query", {}).get("search", []):
            title = hit["title"]
            tw, qw = _words(title), _words(term)
            if not qw or len(tw & qw) / len(qw) < 0.6:      # page must really be about this name
                continue
            p = requests.get(WIKI, params={"action": "query", "titles": title, "prop": "pageimages",
                                           "piprop": "original|thumbnail", "pithumbsize": 1200, "format": "json"},
                             headers=UA, timeout=15).json()
            for page in p.get("query", {}).get("pages", {}).values():
                img = (page.get("thumbnail") or page.get("original") or {})
                src = img.get("source", "")
                if src and img.get("width", 0) >= 400 and not src.lower().endswith(".svg"):
                    url = src
                    break
            if url:
                break
    except Exception as e:
        print(f"  wiki image '{term}' failed: {e}")
    _cache[term] = url
    return url


def pokemon_image(name, n=2):
    from main import card_images
    try:
        return card_images(f'name:"{name}"', n)
    except Exception as e:
        print(f"  card art '{name}' failed: {e}")
        return []


def official_art(name):
    """Official Pokemon artwork from PokeAPI, e.g. 'Mega Lucario' -> Lucario's artwork."""
    base = re.sub(r"^(mega|shiny|galarian|alolan|hisuian|paldean|dark|radiant)\s+", "", name.lower().strip())
    base = re.sub(r"\s+(ex|gx|v|vmax|vstar|x|y)$", "", base).replace(" ", "-").replace(".", "").replace("'", "")
    key = ("art", base)
    if key in _cache:
        return _cache[key]
    url = None
    try:
        r = requests.get(f"https://pokeapi.co/api/v2/pokemon/{base}", timeout=15)
        if r.status_code == 200:
            o = (r.json().get("sprites") or {}).get("other") or {}
            url = (o.get("official-artwork") or {}).get("front_default") or (o.get("home") or {}).get("front_default")
    except Exception as e:
        print(f"  official art '{name}' failed: {e}")
    _cache[key] = url
    return url


def brave(query):
    try:
        from image_finder import brave_image
        return brave_image(query)
    except Exception:
        return None


def picture_for(name, typ, topic):
    """Pictures of exactly this thing (several versions for characters), or []."""
    from image_finder import best_product
    op = topic == "onepiece"
    line = "one-piece-card-game" if op else "pokemon"
    name = name.strip()
    got = []
    from character_art import pokemon_gallery, onepiece_gallery, card_versions, set_chase_cards
    if typ == "pokemon" and not op:
        # artwork + shiny + 3D + other forms + non-holo / holo / shiny / full-art / illustration cards
        got = pokemon_gallery(name.split(" ex")[0], 5) or [official_art(name)]
    elif typ in ("card", "character"):
        if op:
            # the character's cards in different versions: manga, parallel / alt art, special, regular
            got = [best_product(name, line, want="card", min_match=0.75)] + onepiece_gallery(name, 4)
        else:
            got = pokemon_image(name, 1) + card_versions(name, 3) or [official_art(name)]
    elif typ in ("product", "set"):
        got = [best_product(name, line, want="sealed")]
        if not got[0] and typ == "set":
            got = [best_product(f"{name} booster box", line, want="sealed", min_match=0.5)]
        if not got[0]:
            got = [brave(f"{name} {'One Piece Card Game' if op else 'Pokemon TCG'}")]
        if typ == "set":
            got += set_chase_cards(name, topic, 3)          # the set's biggest cards
    elif typ in ("game", "person", "company", "event", "venue", "place"):
        if typ == "place" and not any(w in name.lower() for w in VENUE_WORDS):
            return []                         # "London" -> no skyline photos; only real venues/stores
        got = [wiki_image(name)]
        if not got[0] and typ in ("game", "event", "venue"):
            got = [brave(name)]
    return [u for u in dict.fromkeys(got) if u]


def ai_entities(story):
    """Ask Gemini which concrete, picturable things each slide mentions."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    from reel_v2 import gemini_models
    slides = [sc["text"] for sc in story["scenes"]]
    op = story.get("topic") == "onepiece"
    kind = "One Piece Card Game (Bandai)" if op else "Pokemon"
    types = ("person|venue|company|event|game|product|set|card|character" if op else
             "person|venue|company|event|game|product|set|card|pokemon")
    prompt = (
        f"For each slide of a {kind} news Reel, list the concrete things it mentions that a viewer would want "
        "to SEE a picture of, most important first, max 3 per slide. Use full official names from the article: "
        "products with their full name (e.g. 'Mega Evolution Elite Trainer Box', 'OP-14 Booster Box'), "
        "sets by set name, cards by card name, "
        + ("One Piece characters by card name (e.g. 'Monkey.D.Luffy'), " if op else "Pokemon by species name (e.g. 'Lucario'), ")
        + "video games by title, real people by full name, venues/stores by full name. "
        "Skip generic things (cards, fans, collectors, store, city or country names). "
        "If a slide names nothing picturable, give the main product or subject of the whole article.\n"
        f'Reply JSON only: {{"slides": [[{{"name": "...", "type": "{types}"}}], ...]}}\n\n'
        f"ARTICLE:\n{story.get('context', '')[:2500]}\n\nSLIDES:\n"
        + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(slides))
    )
    for model in gemini_models(key)[:3]:
        for attempt in range(2):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  params={"key": key},
                                  json={"contents": [{"parts": [{"text": prompt}]}],
                                        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}},
                                  timeout=60)
                if r.status_code in (429, 500, 503):
                    time.sleep(5 * (attempt + 1))
                    continue
                if r.status_code != 200:
                    break
                txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
                out = data.get("slides") or []
                if len(out) == len(slides):
                    return out
            except Exception as e:
                print(f"  entities: {model} error ({e})")
    return None


def fallback_entities(story):
    """No-AI version: products, set names, One Piece set codes, Pokemon names, people's names."""
    op = story.get("topic") == "onepiece"
    names = []
    if not op:
        try:
            from main import pokemon_names
            names = [n for n in pokemon_names() if len(n) > 3]
        except Exception:
            names = []
    try:
        from main import all_sets
        set_names = [] if op else [s["name"] for s in all_sets() if len(s.get("name", "")) > 5]
    except Exception:
        set_names = []
    title = story.get("context", "").split(". ")[0]
    out = []
    for sc in story["scenes"]:
        raw = sc.get("raw") or sc["text"]
        t = raw if raw != raw.upper() else raw.title()
        ents = [{"name": re.sub(r"^(?:New|The|A|An|This|Upcoming|Latest)\s+", "", m.strip()), "type": "product"}
                for m in PRODUCT_RE.findall(t)][:2]
        ents += [{"name": f"{a.upper()}-{int(b):02d}", "type": "set"} for a, b in OP_CODE_RE.findall(t)][:1]
        ents += [{"name": sn, "type": "set"} for sn in set_names if sn.lower() in t.lower()][:1]
        ents += [{"name": n.title(), "type": "pokemon"} for n in names
                 if re.search(r"\b" + re.escape(n) + r"\b", t.lower())][:2]
        if op:
            from character_art import find_op_characters
            ents += [{"name": c, "type": "character"} for c in find_op_characters(t)][:2]
        taken = " ".join(e["name"].lower() for e in ents)
        for m in re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", t):
            if len(ents) < 3 and m.lower() not in ("pokemon center", "one piece") \
                    and not any(w in taken for w in m.lower().split()):
                ents.append({"name": m, "type": "person"})
        if not ents:                         # nothing on this slide -> the story's main product, if any
            ents = [{"name": m.strip(), "type": "product"} for m in PRODUCT_RE.findall(title)][:1]
        out.append(ents[:3])
    return out


def enrich(story):
    """Give every slide its own list of on-topic pictures: sc['imgs'] (first = main picture)."""
    article = list(story.get("article_images") or [])
    topic = story.get("topic")
    ents = ai_entities(story) or fallback_entities(story)
    seen = set()
    for i, (sc, el) in enumerate(zip(story["scenes"], ents)):
        imgs = [article[0]] if i == 0 and article else []     # slide 1 opens on the story's own main photo
        for e in (el or [])[:3]:
            name, typ = str(e.get("name", "")).strip(), str(e.get("type", "")).lower()
            if not name:
                continue
            if typ in ("pokemon",) and topic == "onepiece":
                continue                      # never Pokemon art on a One Piece Reel
            for u in picture_for(name, typ, topic):
                if len(imgs) >= 7:
                    break
                if u not in imgs and u not in seen:
                    imgs.append(u)
                    print(f"  slide {i + 1}: {name} ({typ}) -> picture")
        for u in article:                     # the article's own photos fill in, so a slide is never empty
            if len(imgs) >= 3:
                break
            if u not in imgs:
                imgs.append(u)
        if imgs:
            sc["imgs"] = imgs
            sc["img_url"] = imgs[0]
            seen.update(imgs)
    story["image_pool"] = list(dict.fromkeys(article + list(seen)))
    return story
