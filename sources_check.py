"""Read-only check: which news sources can GitHub's servers reach, and do they return usable articles?
Prints one ::notice:: line per source (shows up as annotations on the run). Never posts anything."""
import os
import sys

os.environ.setdefault("CLOUDINARY_URL", "cloudinary://a:b@c")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as M  # noqa: E402

which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
groups = []
if which in ("all", "onepiece"):
    groups.append(("ONE PIECE", M.ONEPIECE_SOURCES + M.ONEPIECE_CANDIDATES))
if which in ("all", "pokemon"):
    groups.append(("POKEMON", M.SOURCES))

for label, sources in groups:
    for src in sources:
        try:
            links = M.list_source(src)
        except Exception as e:
            print(f"::notice title={label} {src['name']}::FAIL list: {str(e)[:150]}")
            continue
        good, sample = 0, ""
        for url, d in links[:4]:
            try:
                a = M.parse_article(src, url, d)
            except Exception as e:
                sample = sample or f"article error {str(e)[:80]}"
                continue
            if a["title"] and a["images"] and a["paras"]:
                good += 1
                sample = sample or f"{a['title'][:70]} | {len(a['images'])} imgs | {len(a['paras'])} paras | {a['published']}"
        print(f"::notice title={label} {src['name']}::{len(links)} links, {good}/4 usable. e.g. {sample}")
