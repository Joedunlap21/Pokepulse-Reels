"""
Pictures of the exact things a news story talks about - per slide.
  "Kanye West shops at LA Sports Cards in Burbank"  -> Kanye West photo, Burbank photo (Wikipedia)
  "Saint pulled a Kyogre from Storm Emerald"        -> Kyogre card art (pokemontcg.io)
Free sources only: Wikipedia/Wikimedia (no key) + pokemontcg.io + the article's own photos.
Every picture is looked up BY NAME for something the slide actually mentions - nothing random.
"""
import os
import re
import json
import time
import requests

UA = {"User-Agent": "PokePulseBot/1.0 (https://github.com/Joedunlap21/Pokepulse-Reels)"}
WIKI = "https://en.wikipedia.org/w/api.php"
_cache = {}


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
                if src and img.get("width", 0) >= 300 and not src.lower().endswith(".svg"):
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


def ai_entities(story):
    """Ask Gemini which concrete things each slide mentions (people, places, stores, Pokemon, products)."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    from reel_v2 import gemini_models
    slides = [sc["text"] for sc in story["scenes"]]
    prompt = (
        "For each slide of a Pokemon card news Reel, list the concrete things it mentions that a viewer would "
        "want to SEE a picture of: real people (full name), places (city, venue), stores/companies, events, "
        "Pokemon (species name only, e.g. Kyogre), card names. Max 3 per slide, most important first. "
        "Only names that appear in or are clearly referred to by that slide (use the article for full names, "
        "e.g. 'Kanye' -> 'Kanye West'). No generic words like 'cards' or 'store'.\n"
        'Reply JSON only: {"slides": [[{"name": "...", "type": "person|place|company|event|pokemon|card|product"}], ...]}\n\n'
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
    from main import pokemon_names
    names = [n for n in pokemon_names() if len(n) > 3]
    out = []
    for sc in story["scenes"]:
        t = sc["text"]
        ents = [{"name": n.title(), "type": "pokemon"} for n in names
                if re.search(r"\b" + re.escape(n) + r"\b", t.lower())][:2]
        for m in re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", sc.get("raw", t.title())):
            if len(ents) < 3:
                ents.append({"name": m, "type": "person"})
        out.append(ents)
    return out


def enrich(story):
    """Give every slide its own list of on-topic pictures: sc['imgs'] (first = main picture)."""
    article = list(story.get("article_images") or [])
    ents = ai_entities(story) or fallback_entities(story)
    seen = set()
    for i, (sc, el) in enumerate(zip(story["scenes"], ents)):
        imgs = []
        for e in (el or [])[:3]:
            name, typ = str(e.get("name", "")).strip(), str(e.get("type", "")).lower()
            if not name:
                continue
            if typ in ("pokemon", "card"):
                got = pokemon_image(name.split(" ex")[0] if typ == "pokemon" else name, 2)
            else:
                u = wiki_image(name)
                got = [u] if u else []
            for u in got:
                if u and u not in imgs:
                    imgs.append(u)
                    print(f"  slide {i + 1}: {name} ({typ}) -> picture")
        # the article's own photos fill in, so a slide is never empty
        for u in article:
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
