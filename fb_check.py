"""Checks the Facebook Page token WITHOUT posting anything. Never prints the token."""
import os, requests
G = "https://graph.facebook.com/v21.0"
pid = os.getenv("FB_PAGE_ID", "").strip()
for name in ("FB_PAGE_TOKEN", "IG_ACCESS_TOKEN"):
    t = os.getenv(name, "").strip()
    print(f"\n=== {name}: {'set, ' + str(len(t)) + ' chars' if t else 'NOT SET'} ===")
    if not t:
        continue
    d = requests.get(f"{G}/debug_token", params={"input_token": t, "access_token": t}).json().get("data", {})
    print("valid:", d.get("is_valid"), "| type:", d.get("type"), "| profile_id:", d.get("profile_id"),
          "| expires_at:", d.get("expires_at"), "| app:", d.get("application"))
    print("scopes:", d.get("scopes"))
    for g in d.get("granular_scopes", []):
        print("  granular:", g.get("scope"), "->", g.get("target_ids", "all"))
    if d.get("error"):
        print("error:", d["error"])
    if pid:
        r = requests.get(f"{G}/{pid}", params={"fields": "name,access_token", "access_token": t}).json()
        print("page lookup:", r.get("name"), "| got page token:", bool(r.get("access_token")), "|", r.get("error", {}).get("message", "ok"))
print("\nFB_PAGE_ID:", pid or "NOT SET")
