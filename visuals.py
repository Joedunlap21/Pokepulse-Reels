"""
Every Reel gets at least 3 different visuals, 5+ whenever the sources have them (Joe, Oct 20:
"some of the reels only have one photo the entire video").

ensure_visuals(story) runs right before the video is built:
  1. collects every picture the story already has (article photos, per-slide pictures, image pool)
  2. drops pictures that don't load or are tiny
  3. tops up from on-topic sources when there are fewer than 5 (card art for the Pokemon named in the
     story, Wikipedia photos of the people/places/products it names - never Pokemon art on One Piece)
  4. last resort (still under 3): close-up crops of the story's own picture, saved as local files
  5. spreads them over the slides so each slide opens on a NEW picture and cuts to another one
"""
import os
import re
import random

MIN_VISUALS = 3
TARGET_VISUALS = 6
PER_SLIDE = 4


def _ok(url, cache={}):
    if url in cache:
        return cache[url]
    from main import load_image
    im = load_image(url)
    # Oct 23 (Joe: "bad images"): no tiny pictures, no thin banners / logo strips
    good = im is not None and min(im.size) >= 400 and 0.4 <= im.size[0] / im.size[1] <= 2.6
    cache[url] = good
    return good


def _collect(story):
    urls = []
    for sc in story.get("scenes", []):
        urls += [sc.get("img_url")] + list(sc.get("imgs") or [])
    urls += list(story.get("image_pool") or []) + list(story.get("article_images") or [])
    seen, out = set(), []
    for u in urls:
        if not u:
            continue
        k = u.split("?")[0]
        if k in seen:
            continue
        seen.add(k)
        out.append(u)
    return out


def _top_up(story, have):
    """More on-topic pictures. Pokemon stories: card art for Pokemon named in the story.
    Everything: Wikipedia photo of the things the slides name (no Pokemon art on One Piece)."""
    topic = story.get("topic")
    # only Pokemon the SLIDES actually talk about (not every name buried in the article)
    text = " ".join(sc.get("text", "") for sc in story.get("scenes", [])).lower()
    text = text.replace("pokémon", "pokemon")
    found = []
    if topic not in ("onepiece",):
        try:
            from main import pokemon_names, card_images
            names = [n for n in pokemon_names() if len(n) > 3 and re.search(r"\b" + re.escape(n) + r"\b", text)]
            for nm in names[:3]:
                found += card_images(f'name:"{nm}"', 3)
                print(f"  visuals: + {nm} card art")
                if len(have) + len(found) >= TARGET_VISUALS + 2:
                    break
        except Exception as e:
            print(f"  visuals: card art failed ({e})")
    if len(have) + len(found) < TARGET_VISUALS:
        try:
            from story_images import ai_entities, wiki_image
            ents = ai_entities(story) or []
            for el in ents:
                for e in (el or []):
                    typ = str(e.get("type", "")).lower()
                    if topic == "onepiece" and typ in ("pokemon", "card"):
                        continue
                    if typ in ("pokemon", "card"):
                        continue          # card art handled above
                    u = wiki_image(str(e.get("name", "")).strip())
                    if u:
                        found.append(u)
                        print(f"  visuals: + photo of {e.get('name')}")
                if len(have) + len(found) >= TARGET_VISUALS + 2:
                    break
        except Exception as e:
            print(f"  visuals: name photos failed ({e})")
    return found


def _crops(url, n_needed):
    """Close-up crops of one real picture (left, centre, right / top, middle, bottom)."""
    from main import load_image
    im = load_image(url)
    if im is None:
        return []
    w, h = im.size
    boxes = ([(0, 0, int(w * .62), h), (int(w * .19), 0, int(w * .81), h), (int(w * .38), 0, w, h)]
             if w >= h else
             [(0, 0, w, int(h * .62)), (0, int(h * .19), w, int(h * .81)), (0, int(h * .38), w, h)])
    out = []
    for k, b in enumerate(boxes[:n_needed]):
        p = os.path.abspath(f"vis_crop_{k}.jpg")
        im.crop(b).save(p, quality=92)
        out.append(p)
    print(f"  visuals: + {len(out)} close-up crops (story only had {MIN_VISUALS - n_needed} picture(s))")
    return out


def ensure_visuals(story):
    scenes = story.get("scenes") or []
    if not scenes:
        return story
    # remember each slide's own on-topic pictures (story_images.enrich) before we rebuild the lists
    specific = [[u for u in ([sc.get("img_url")] + list(sc.get("imgs") or [])) if u] for sc in scenes]
    pool = [u for u in _collect(story) if _ok(u)]
    if len(pool) < TARGET_VISUALS:
        for u in _top_up(story, pool):
            if u and u.split("?")[0] not in {p.split("?")[0] for p in pool} and _ok(u):
                pool.append(u)
    if len(pool) < MIN_VISUALS and pool:
        pool += _crops(pool[0], MIN_VISUALS - len(pool))
    if not pool:
        print("  visuals: no usable pictures at all")
        return story
    print(f"Visuals: {len(pool)} different pictures for {len(scenes)} slides")

    # each slide opens on a picture not shown yet (its own on-topic one first), then cuts to more new ones
    shown, queue = set(), list(pool)

    def nxt(prefer=()):
        for u in list(prefer) + queue:
            if u in pool and u not in shown:
                shown.add(u)
                return u
        return None

    lists = []
    for i, sc in enumerate(scenes):
        first = nxt(specific[i]) or pool[i % len(pool)]
        lst = [first]
        second = nxt()
        if second:
            lst.append(second)
        lists.append(lst)
    # third pass: anything still unseen goes to slides in turn
    i = 0
    while len(shown) < len(pool):
        u = nxt()
        lists[i % len(lists)].append(u)
        i += 1
    for i, sc in enumerate(scenes):
        lst = lists[i]
        # pad each slide so long slides keep switching (re-using pictures only after all were shown)
        spare = [u for u in pool if u not in lst]
        random.shuffle(spare)
        lst = (lst + spare)[:max(PER_SLIDE, len(lst))]
        sc["img_url"], sc["imgs"] = lst[0], lst
    story["image_pool"] = pool
    return story


def count_visuals(story):
    return len({u for sc in story.get("scenes", []) for u in (sc.get("imgs") or [sc.get("img_url")]) if u})
