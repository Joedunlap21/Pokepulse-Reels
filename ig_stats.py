"""Daily Instagram stats logger for the 3-week follower case study.

Appends one row per day to stats/daily.csv (followers, posts, account reach/views/
profile views/follows) and rewrites stats/media.csv with the latest numbers for
the last 60 posts (reach, views, likes, comments, shares, saves, follows).
Read-only: it never posts anything.
"""
import csv
import os
from datetime import datetime, timezone, timedelta

import requests

GRAPH = "https://graph.facebook.com/v21.0"
IG = os.environ["IG_USER_ID"]
TOKEN = os.environ["IG_ACCESS_TOKEN"]
os.makedirs("stats", exist_ok=True)
ERRORS = []


def get(path, **params):
    params["access_token"] = TOKEN
    r = requests.get(f"{GRAPH}/{path}", params=params, timeout=60).json()
    if "error" in r:
        raise RuntimeError(r["error"].get("message", r["error"]))
    return r


def media_insights(mid, kind):
    """Ask for every metric we want; drop the ones Instagram rejects for this post type."""
    wanted = ["reach", "views", "likes", "comments", "shares", "saved", "follows",
              "profile_visits", "ig_reels_avg_watch_time"]
    out = {}
    while wanted:
        try:
            data = get(f"{mid}/insights", metric=",".join(wanted))["data"]
            for d in data:
                v = d.get("values", [{}])[0].get("value", d.get("total_value", {}).get("value"))
                out[d["name"]] = v
            break
        except RuntimeError as e:
            msg = str(e)
            bad = [m for m in wanted if m in msg]
            if not bad:
                print(f"  insights failed for {mid} ({kind}): {msg}")
                ERRORS.append(f"media {kind}: {msg}")
                break
            wanted = [m for m in wanted if m not in bad]
    return out


def account_day_totals():
    """Yesterday's account-level totals (ET day)."""
    since = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    until = int(datetime.now(timezone.utc).timestamp())
    out = {}
    for m in ["reach", "views", "profile_views", "follows_and_unfollows", "accounts_engaged"]:
        try:
            r = get(f"{IG}/insights", metric=m, period="day", metric_type="total_value",
                    since=since, until=until)
            for d in r.get("data", []):
                tv = d.get("total_value", {})
                if "breakdowns" in tv:
                    for b in tv["breakdowns"]:
                        for res in b.get("results", []):
                            out[f"{m}_{'_'.join(res.get('dimension_values', []))}".lower()] = res.get("value")
                out[m] = tv.get("value")
        except RuntimeError as e:
            print(f"  account metric {m} unavailable: {e}")
            ERRORS.append(f"account {m}: {e}")
    return out


def main():
    now = datetime.now(timezone.utc)
    prof = get(IG, fields="username,followers_count,follows_count,media_count")
    print(f"@{prof.get('username')}: {prof.get('followers_count')} followers, {prof.get('media_count')} posts")
    acct = account_day_totals()

    row = {"date_utc": now.strftime("%Y-%m-%d %H:%M"), "username": prof.get("username"),
           "followers": prof.get("followers_count"), "following": prof.get("follows_count"),
           "posts": prof.get("media_count"), **acct}
    path = "stats/daily.csv"
    old = []
    if os.path.exists(path):
        with open(path) as f:
            old = list(csv.DictReader(f))
    cols = list(dict.fromkeys([k for r in old for k in r] + list(row)))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(old + [row])

    media = get(f"{IG}/media", fields="id,caption,timestamp,media_product_type,media_type,permalink",
                limit=60).get("data", [])
    rows = []
    for m in media:
        ins = media_insights(m["id"], m.get("media_product_type"))
        cap = (m.get("caption") or "").replace("\n", " ")
        rows.append({"timestamp": m.get("timestamp"), "type": m.get("media_product_type") or m.get("media_type"),
                     "first_line": cap[:90], "permalink": m.get("permalink"), "id": m["id"], **ins})
    mcols = list(dict.fromkeys(k for r in rows for k in r))
    with open("stats/media.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=mcols)
        w.writeheader()
        w.writerows(rows)
    with open("stats/errors.txt", "w") as f:
        f.write("\n".join(sorted(set(ERRORS))) or "none")
    print(f"Logged {len(rows)} posts. Account: {acct}")


if __name__ == "__main__":
    main()
