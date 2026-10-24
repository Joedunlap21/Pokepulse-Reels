"""
Two formats added Oct 20 (Joe: "min of 6 posts per day: news, drops, one piece, games, character fun fact videos"):

  games   - Pokemon VIDEO GAME news (Pokemon GO events, Switch games, Pokopia, Unite, Sleep...).
            Same rules as card news: facts only from the article, pictures of what's discussed,
            no celebrity stories, no fan-made games, no finance pieces.
  funfact - "Did you know?" about one Pokemon character. Every fact comes from PokeAPI (official Pokedex
            data: category, type, size, Pokedex entries, evolution). Never runs dry, so it's the last
            fallback: a timer slot always posts something.
            Pictures: official artwork, shiny artwork, 3D model art, the Pokemon it evolves from, and its
            real card art = 5-8 different visuals.
"""
import re
import random
import requests

from main import YELLOW, WHITE, card_images

# ---------------------------------------------------------------- games

GAMES_SOURCES = [
    {"name": "Pokemon GO", "list": "https://pokemongo.com/news", "base": "https://pokemongo.com",
     "link_re": r'href="((?:https://pokemongo\.com)?/(?:en/)?news/[a-z0-9\-]+)"',
     "start": "<main", "end": ["</main>"], "max_imgs": 6},
    {"name": "Leek Duck", "list": "https://leekduck.com/events/", "base": "https://leekduck.com",
     "link_re": r'href="((?:https://leekduck\.com)?/events/[a-z0-9\-]+/)"',
     "start": "<article", "end": ["</article>"], "max_imgs": 6},
    {"name": "Pokemon.com", "list": "https://www.pokemon.com/us/news", "base": "https://www.pokemon.com",
     "link_re": r'href="((?:https://www\.pokemon\.com)?/us/news/[a-z0-9\-]+)"',
     "start": "<article", "end": ["</article>"], "max_imgs": 6},
    {"name": "Dexerto", "rss": "https://www.dexerto.com/feed/category/pokemon/", "base": "https://www.dexerto.com",
     "start": "<article", "end": ["</article>"], "max_imgs": 3},
    {"name": "Bing News", "rss": "https://www.bing.com/news/search?q=%22Pokemon+GO%22+event&format=rss",
     "base": "", "start": "<article", "end": ["</article>"], "max_imgs": 4},
    {"name": "Bing News", "rss": "https://www.bing.com/news/search?q=Pokemon+game+update+Nintendo+Switch&format=rss",
     "base": "", "start": "<article", "end": ["</article>"], "max_imgs": 4},
]
GAME_WORDS = ["pokemon go", "pokémon go", "scarlet", "violet", "legends", "z-a", "pokopia", "unite", "pokemon sleep",
              "pokémon sleep", "champions", "nintendo switch", "switch 2", "dlc", "update", "raid", "community day",
              "spotlight hour", "max battle", "dynamax", "gigantamax", "mega raid", "shiny", "event", "research",
              "tcg pocket", "pokemon masters", "café remix", "game freak", "nintendo direct", "presents"]
# fan games / finance stay out (same as card news); TCG paper-card stories belong to the news slots
GAMES_SKIP = ["fan game", "fan-made game", "fangame", "browser game", "megabonk", "fundamental analysis",
              "stock price", "share price", "shareholders", "earnings report", "fiscal year", "operating profit",
              "net sales", "booster box", "elite trainer box", "psa 10", "graded card", "prerelease"]


# Oct 23: housekeeping notices (a GO "Stamp Rallies Clarification", PokeCoin store notes) went out as
# games Reels on 0-gain days. Skip them by title so the slot posts a real event/game story (or falls back).
GAMES_NOTICE_SKIP = ["clarification", "clarify", "known issue", "maintenance", "bug fix", "error",
                     "pokécoin", "pokecoin", "web store", "terms of service", "privacy"]


def is_game_story(art):
    blob = " ".join([art["title"], art["desc"]] + art["paras"][:4]).lower()
    if any(w in blob for w in GAMES_SKIP):
        return False
    if any(w in art["title"].lower() for w in GAMES_NOTICE_SKIP):
        return False
    return sum(1 for w in GAME_WORDS if w in blob) >= 1 and ("pokemon" in blob or "pokémon" in blob)


def build_games_story(art):
    from main import all_sentences
    sents = all_sentences(art)
    details = sents[:3]
    if not details or not art["images"]:
        return None
    imgs = art["images"]
    tags = ["THE DETAILS", "WHAT TO KNOW", "KEY INFO"]
    scenes = [{"tag": "POKEMON GAMES NEWS", "img_url": imgs[0], "text": art["title"].upper(), "raw": art["title"],
               "colors": [YELLOW, WHITE], "sub": "POKEPULSE EXCLUSIVE"}]
    for i, s in enumerate(details):
        scenes.append({"tag": tags[i], "img_url": imgs[(i + 1) % len(imgs)], "text": s.upper(), "raw": s,
                       "colors": [WHITE, YELLOW] if i % 2 == 0 else [YELLOW, WHITE]})
    text = ""
    for s in sents:
        if len(text) + len(s) + 1 > 900:
            break
        text = (text + " " + s).strip()
    cap = (f"🎮 POKÉMON GAMES: {art['title']}\n\n{text}\n\nSource: {art['source']}\n\n"
           "#Pokemon #PokemonGO #PokemonGames #NintendoSwitch #CardStax #PokePulse")
    return {"story_id": art["title"][:40], "key": art["title"].lower(), "scenes": scenes, "caption_full": cap}


# ---------------------------------------------------------------- character fun fact

API = "https://pokeapi.co/api/v2"
# Fan favourites first (more views); after these it picks any Pokemon not posted yet
FAVORITES = ["pikachu", "eevee", "charizard", "umbreon", "gengar", "mewtwo", "mew", "lucario", "sylveon", "snorlax",
             "greninja", "rayquaza", "espeon", "dragonite", "gardevoir", "lugia", "jigglypuff", "bulbasaur",
             "squirtle", "charmander", "psyduck", "vaporeon", "jolteon", "flareon", "leafeon", "glaceon", "ditto",
             "magikarp", "gyarados", "mimikyu", "zorua", "zoroark", "garchomp", "tyranitar", "blastoise",
             "venusaur", "arcanine", "lapras", "cubone", "togepi", "piplup", "bidoof", "wooper", "slowpoke",
             "celebi", "jirachi", "darkrai", "giratina", "arceus", "latios", "latias", "kyogre", "groudon",
             "duraludon", "chandelure", "pumpkaboo", "dragapult", "sprigatito", "fuecoco", "quaxly", "pawmi",
             "koraidon", "miraidon", "ceruledge", "armarouge", "tinkaton", "gholdengo"]
REGION = {"generation-i": "Kanto", "generation-ii": "Johto", "generation-iii": "Hoenn", "generation-iv": "Sinnoh",
          "generation-v": "Unova", "generation-vi": "Kalos", "generation-vii": "Alola", "generation-viii": "Galar",
          "generation-ix": "Paldea"}


def _get(url):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def _flavor(species):
    out = []
    for e in species.get("flavor_text_entries", []):
        if (e.get("language") or {}).get("name") != "en":
            continue
        t = re.sub(r"\s+", " ", e["flavor_text"].replace("\f", " ").replace("­", "")).strip()
        t = t.replace("POKéMON", "Pokémon").replace("POKEMON", "Pokémon")
        if 6 <= len(t.split()) <= 30 and t.lower() not in [x.lower() for x in out]:
            out.append(t)
    random.shuffle(out)
    return out


def _art(poke):
    o = (poke.get("sprites") or {}).get("other") or {}
    oa, home = o.get("official-artwork") or {}, o.get("home") or {}
    return [u for u in (oa.get("front_default"), home.get("front_default"), oa.get("front_shiny"),
                        home.get("front_shiny")) if u]


def _feet(dm):
    inches = round(dm * 3.937)
    return f"{inches // 12} foot {inches % 12}" if inches % 12 else f"{inches // 12} feet"


def build_funfact_story(posted, captions=()):
    """posted: lower-case keys already used; captions: recent IG captions (lower-case)."""
    names = [n for n in FAVORITES if f"funfact {n}" not in posted]
    if not names:
        names = [str(i) for i in random.sample(range(1, 1026), 40)]
    head = names[:12]
    random.shuffle(head)          # a bit of variety among the next favourites
    names = head + names[12:]
    for name in names[:15]:
        try:
            species = _get(f"{API}/pokemon-species/{name}")
            key = f"funfact {species['name']}"
            if key in posted:
                continue
            poke = _get(f"{API}/pokemon/{species['id']}")
        except Exception as e:
            print(f"  fun fact: {name} lookup failed ({e})")
            continue
        disp = next((n["name"] for n in species.get("names", []) if (n.get("language") or {}).get("name") == "en"),
                    species["name"].title())
        genus = next((g["genus"] for g in species.get("genera", []) if (g.get("language") or {}).get("name") == "en"), "")
        types = [t["type"]["name"].title() for t in sorted(poke.get("types", []), key=lambda t: t["slot"])]
        region = REGION.get((species.get("generation") or {}).get("name"), "")
        if any(f"fun fact: {disp.lower()}" in c for c in captions):
            print(f"  fun fact: {disp} already posted")
            continue
        flav = _flavor(species)
        if len(flav) < 2 or not genus:
            continue
        # pictures: artwork + what it evolves from + its real cards
        imgs = _art(poke)
        prev = species.get("evolves_from_species")
        prev_name = ""
        if prev:
            try:
                pp = _get(f"{API}/pokemon/{prev['name']}")
                prev_name = prev["name"].replace("-", " ").title()
                imgs += _art(pp)[:1]
            except Exception:
                pass
        try:   # Oct 23 (Joe): other forms + holo vs non-holo vs shiny vs full-art cards
            from character_art import card_versions, pokemon_forms
            imgs += pokemon_forms(species["name"], 2) + card_versions(disp, 5)
        except Exception as e:
            print(f"  fun fact: card versions failed ({e})")
            try:
                imgs += card_images(f'name:"{disp}"', 4)
            except Exception as e2:
                print(f"  fun fact: card art failed ({e2})")
        imgs = list(dict.fromkeys(u for u in imgs if u))
        if len(imgs) < 5:
            print(f"  fun fact: {disp} only has {len(imgs)} pictures, trying another")
            continue

        t_join = " and ".join(types)
        tag_line = f"{disp.upper()} IS THE {genus.upper()}"
        size = f"{disp} stands about {_feet(poke['height'])} tall and weighs {round(poke['weight'] * 0.2205)} pounds."
        extra = []
        if species.get("is_legendary"):
            extra.append(f"It's a Legendary Pokémon.")
        elif species.get("is_mythical"):
            extra.append(f"It's a Mythical Pokémon.")
        elif prev_name:
            extra.append(f"It evolves from {prev_name}.")
        scenes = [
            {"tag": "POKEMON FUN FACT", "img_url": imgs[0], "text": f"DID YOU KNOW THIS ABOUT {disp.upper()}?",
             "colors": [YELLOW, WHITE], "say": f"Did you know this about {disp}?"},
            {"tag": "THE BASICS", "img_url": imgs[1], "text": tag_line, "colors": [WHITE, YELLOW],
             "say": f"{disp} is called the {genus}. It's a {t_join} type"
                    + (f" from the {region} region." if region else ".")},
            {"tag": "POKEDEX SAYS", "img_url": imgs[2], "text": flav[0].upper(), "colors": [YELLOW, WHITE],
             "say": flav[0]},
            {"tag": "SIZE CHECK", "img_url": imgs[3], "text": size.upper(), "colors": [WHITE, YELLOW],
             "say": size + (" " + extra[0] if extra else "")},
            {"tag": "ONE MORE", "img_url": imgs[4], "text": flav[1].upper(), "colors": [YELLOW, WHITE],
             "say": flav[1]},
        ]
        for i, sc in enumerate(scenes):            # every slide starts with its own picture, then cuts
            sc["imgs"] = [imgs[i % len(imgs)]] + [u for u in imgs if u != imgs[i % len(imgs)]][:4]
        tagname = re.sub(r"[^A-Za-z0-9]", "", disp)
        cap = (f"🧠 POKÉMON FUN FACT: {disp}\n\n"
               f"{disp} is the {genus}, a {t_join} type{' from ' + region if region else ''}. "
               f"{size} {' '.join(extra)}\n\nPokédex: “{flav[0]}”\n\nSource: official Pokédex data (PokéAPI)\n\n"
               f"#Pokemon #PokemonFacts #Pokedex #{tagname} #PokemonCards #CardStax #PokePulse")
        print(f"Fun fact: {disp} ({len(imgs)} pictures)")
        return {"story_id": f"funfact {species['name']}", "key": key, "scenes": scenes, "topic": "funfact",
                "caption_full": cap, "thumb_text": f"{disp.upper()} FACTS",
                "image_pool": imgs, "context": f"{disp}, the {genus}. " + " ".join(flav[:3])}
    return None
