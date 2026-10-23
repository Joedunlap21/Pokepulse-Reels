"""
More pictures of the characters a Reel talks about (Joe, Oct 23: "more pictures, characters talked about,
difference of holo and non holos, shiny, different types of characters... One Piece you can use different
character images or manga").

Pokemon (pokemon_gallery):
  official artwork, SHINY artwork, 3D (HOME) render, shiny 3D, other forms (Mega, Gigantamax, Alolan,
  Galarian, Hisuian, Paldean...) + one real card per kind: non-holo, holo, shiny, ex/V/full art, illustration rare
One Piece (onepiece_gallery):
  the character's real cards in different versions from TCGplayer: regular, parallel / alt art, MANGA rare,
  SP / treasure / leader - all official card images (no ripped anime frames: copyright risk to the account)
Sets (set_chase_cards): the most valuable cards in a set the story talks about.
"""
import re
import random
import requests

POKEAPI = "https://pokeapi.co/api/v2"
_cache = {}

# kinds of card, in the order we want to show them (holo vs non-holo vs shiny vs big art)
RARITY_KINDS = [
    ("non-holo", lambda r: r in ("common", "uncommon", "rare")),
    ("holo", lambda r: "holo" in r and not re.search(r"\b(ex|gx|v|vmax|vstar)\b", r)),
    ("shiny", lambda r: "shiny" in r),
    ("ex / full art", lambda r: r in ("double rare", "ultra rare", "rare ultra") or re.search(r"holo (ex|gx|v|vmax|vstar)", r)),
    ("illustration", lambda r: any(k in r for k in ("illustration", "secret", "hyper", "rainbow", "amazing", "radiant"))),
]

# One Piece characters: short name people write -> how the card is named on TCGplayer
OP_CHARACTERS = {
    "luffy": "Monkey.D.Luffy", "zoro": "Roronoa Zoro", "nami": "Nami", "sanji": "Sanji", "usopp": "Usopp",
    "chopper": "Tony Tony.Chopper", "robin": "Nico Robin", "franky": "Franky", "brook": "Brook", "jinbe": "Jinbe",
    "shanks": "Shanks", "ace": "Portgas.D.Ace", "sabo": "Sabo", "law": "Trafalgar Law", "kid": "Eustass\"Captain\"Kid",
    "yamato": "Yamato", "hancock": "Boa Hancock", "kaido": "Kaido", "big mom": "Charlotte Linlin",
    "whitebeard": "Edward.Newgate", "blackbeard": "Marshall.D.Teach", "buggy": "Buggy", "mihawk": "Dracule Mihawk",
    "crocodile": "Crocodile", "doflamingo": "Donquixote Doflamingo", "katakuri": "Charlotte Katakuri", "uta": "Uta",
    "vivi": "Nefeltari Vivi", "carrot": "Carrot", "koby": "Koby", "garp": "Monkey.D.Garp", "smoker": "Smoker",
    "enel": "Enel", "lucci": "Rob Lucci", "kizaru": "Borsalino", "akainu": "Sakazuki", "aokiji": "Kuzan",
    "roger": "Gol.D.Roger", "rayleigh": "Silvers Rayleigh", "perona": "Perona", "bonney": "Jewelry Bonney",
    "vegapunk": "Vegapunk", "dragon": "Monkey.D.Dragon", "imu": "Imu", "rebecca": "Rebecca", "kuma": "Bartholomew Kuma",
    "hody": "Hody Jones", "arlong": "Arlong", "moria": "Gecko Moria", "magellan": "Magellan", "ivankov": "Emporio.Ivankov",
}
OP_VERSIONS = [("manga", ("manga",)), ("parallel / alt art", ("parallel", "alternate art", "alt art")),
               ("special", ("sp ", "(sp)", "special", "treasure", "gold", "red super")),
               ("leader", ("leader",)), ("regular", ())]


def _get(url, **kw):
    key = (url, tuple(sorted(kw.get("params", {}).items())))
    if key in _cache:
        return _cache[key]
    try:
        r = requests.get(url, timeout=20, **kw)
        data = r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"  character art: {url} failed ({e})")
        data = None
    _cache[key] = data
    return data


def _slug(name):
    s = re.sub(r"^(mega|shiny|dark|radiant)\s+", "", name.lower().strip())
    s = re.sub(r"\s+(ex|gx|v|vmax|vstar)$", "", s)
    return s.replace(" ", "-").replace(".", "").replace("'", "").replace("’", "")


def _sprites(poke):
    o = (poke.get("sprites") or {}).get("other") or {}
    oa, home = o.get("official-artwork") or {}, o.get("home") or {}
    return {"art": oa.get("front_default"), "shiny art": oa.get("front_shiny"),
            "3d": home.get("front_default"), "shiny 3d": home.get("front_shiny")}


def pokemon_forms(name, limit=3):
    """Official artwork of the other forms: Mega, Gigantamax, Alolan, Galarian, Hisuian, Paldean..."""
    sp = _get(f"{POKEAPI}/pokemon-species/{_slug(name)}")
    out = []
    for v in (sp or {}).get("varieties", []):
        if v.get("is_default"):
            continue
        p = _get(v["pokemon"]["url"])
        if p:
            u = _sprites(p).get("art")
            if u:
                out.append(u)
                print(f"  character art: {name} form {v['pokemon']['name']}")
        if len(out) >= limit:
            break
    return out


def card_versions(name, want=5):
    """One real card per kind (non-holo, holo, shiny, ex/full art, illustration rare) for this Pokemon."""
    from main import tcg_get
    base = re.sub(r"\s+(ex|gx|v|vmax|vstar)$", "", name.strip(), flags=re.I)
    q = f"name:{base}*" if " " not in base else f'name:"{base}"'
    data = tcg_get("cards", {"q": q, "pageSize": 150, "select": "id,name,rarity,images,set"}).get("data", [])
    random.shuffle(data)
    out = []
    for kind, test in RARITY_KINDS:
        for c in data:
            r = (c.get("rarity") or "").lower()
            img = (c.get("images") or {}).get("large")
            if img and img not in out and test(r):
                out.append(img)
                print(f"  character art: {c['name']} card ({kind}: {c.get('rarity')})")
                break
        if len(out) >= want:
            break
    return out


def pokemon_gallery(name, n=8):
    """Mix of artwork, shiny, 3D, forms and card versions for one Pokemon - most different first."""
    p = _get(f"{POKEAPI}/pokemon/{_slug(name)}")
    sprites = _sprites(p) if p else {}
    cards = card_versions(name)
    forms = pokemon_forms(name) if p else []
    order = [sprites.get("art"), cards[0] if cards else None, sprites.get("shiny art"),
             cards[1] if len(cards) > 1 else None, sprites.get("3d"), cards[2] if len(cards) > 2 else None]
    order += forms[:2] + [sprites.get("shiny 3d")] + cards[3:]
    return [u for u in dict.fromkeys(order) if u][:n]


def op_card_name(name):
    low = name.lower().strip()
    for short, full in OP_CHARACTERS.items():
        if low == short or low == full.lower() or re.search(r"\b" + re.escape(short) + r"\b", low):
            return full
    return name.strip()


def onepiece_gallery(name, n=5):
    """The character's One Piece cards in different versions: manga, parallel/alt art, special, leader, regular."""
    from image_finder import tcgplayer, tcg_img, _match
    card = op_card_name(name)
    res = [r for r in tcgplayer(card, 40, "one-piece-card-game")
           if r.get("productId") and not r.get("sealed") and _match(card, r.get("productName", "")) >= 0.75]
    res.sort(key=lambda r: -float(r.get("marketPrice") or 0))
    out, used = [], set()
    for kind, keys in OP_VERSIONS:
        for r in res:
            text = (r.get("productName", "") + " " + str(r.get("rarityName", ""))).lower()
            if r["productId"] in used:
                continue
            if keys and not any(k in text for k in keys):
                continue
            used.add(r["productId"])
            out.append(tcg_img(r["productId"]))
            print(f"  character art: {r.get('productName')} ({kind})")
            break
    for r in res:                                   # fill with more of their cards, most valuable first
        if len(out) >= n:
            break
        if r["productId"] not in used:
            used.add(r["productId"])
            out.append(tcg_img(r["productId"]))
    return out[:n]


def find_op_characters(text):
    low = text.lower()
    return [full for short, full in OP_CHARACTERS.items()
            if re.search(r"\b" + re.escape(short) + r"\b", low) or full.lower() in low]


def set_chase_cards(name, topic, n=3):
    """Most valuable cards of a set the story talks about (Pokemon set name or One Piece code like OP-14)."""
    if topic == "onepiece":
        from image_finder import tcgplayer, tcg_img
        code = re.sub(r"[^A-Za-z0-9]", "", name).upper()            # OP-14 -> OP14
        res = [r for r in tcgplayer(name, 40, "one-piece-card-game")
               if not r.get("sealed") and code in re.sub(r"[^A-Za-z0-9]", "", (r.get("setName", "") + r.get("productName", "")).upper())]
        res.sort(key=lambda r: -float(r.get("marketPrice") or 0))
        return [tcg_img(r["productId"]) for r in res[:n]]
    from main import all_sets, card_images
    for st in all_sets():
        if st.get("name", "").lower() == name.lower().strip():
            print(f"  character art: chase cards of {st['name']}")
            return card_images(f'set.id:{st["id"]}', n)
    return []
