import os
import time
import requests
from supabase import create_client, Client

print("=== STARTING NITRO TYPE SCRAPER (FULL DATA MODE) ===")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[CRITICAL ERROR] Missing SUPABASE_URL or SUPABASE_KEY environment variables!")
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("[INIT] Supabase client initialized successfully.")
except Exception as e:
    print(f"[CRITICAL ERROR] Failed to initialize Supabase client: {e}")
    raise e

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9"
}

def fetch_tracked_entities():
    try:
        response = supabase.table("entities").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[DB ERROR] Exception while fetching entities: {e}")
        return []

def register_entity(identifier: str, entity_type: str, name: str = ""):
    if not identifier:
        return
    clean_id = str(identifier).lower().strip()
    try:
        payload = {"identifier": clean_id, "type": entity_type}
        if name:
            payload["name"] = name
        supabase.table("entities").upsert(payload, on_conflict="identifier").execute()
    except Exception as e:
        print(f"[DB ERROR] Failed to register entity '{clean_id}': {e}")

def scrape_team(team_tag: str):
    clean_tag = str(team_tag).upper().strip()
    url = f"https://www.nitrotype.com/api/v2/teams/{clean_tag}"
    print(f"\n[SCRAPE TEAM] Fetching team: '{clean_tag}'")
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"[FAIL] Could not fetch team '{clean_tag}'")
            return
        
        json_data = res.json()
        results = json_data.get("results", {})
        data = results[0] if isinstance(results, list) and results else results

        if not data or not isinstance(data, dict):
            return

        info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
        stats = data.get("stats", {}) if isinstance(data.get("stats"), dict) else {}
        members = data.get("members", []) if isinstance(data.get("members"), list) else []

        official_name = info.get("name") or clean_tag
        register_entity(clean_tag.lower(), "team", official_name)

        races = int(stats.get("alltime_races", info.get("races", 0)))
        wpm = float(stats.get("avg_wpm", info.get("avgSpeed", 0)))
        accuracy = float(stats.get("avg_acc", info.get("avgAcc", 0)))
        points = int(stats.get("alltime_points", info.get("points", 0)))
        ppr = round(points / races, 2) if races > 0 else 0.00

        team_snapshot = {
            "identifier": clean_tag.lower(),
            "type": "team",
            "races": races,
            "accuracy": accuracy,
            "wpm": wpm,
            "points": points,
            "ppr": ppr,
            "online_status": True,
            "membership_status": "team",
            "car_img_url": "",
            "title": official_name,
            "team_tag": clean_tag
        }

        supabase.table("snapshots").insert(team_snapshot).execute()

        print(f"[ROSTER] Processing {len(members)} team members...")
        for member in members:
            if not isinstance(member, dict):
                continue
            
            m_username = str(member.get("username") or "").lower().strip()
            if not m_username:
                continue

            m_display = member.get("displayName") or member.get("username") or m_username
            register_entity(m_username, "player", m_display)

            m_races = int(member.get("played", member.get("races", 0)))
            m_wpm = float(member.get("avgSpeed", member.get("wpm", 0)))
            m_acc = float(member.get("avgAcc", member.get("accuracy", 0)))
            
            raw_points = int(member.get("points", 0))
            m_points = raw_points if raw_points > 0 else (m_races * 100)
            m_ppr = round(m_points / m_races, 2) if m_races > 0 else 0.00

            m_car_id = member.get("carID", 1)
            m_car_hue = member.get("carHue", 0)
            m_car_url = f"https://www.nitrotype.com/cars/48/{m_car_id}_{m_car_hue}_1.png"

            is_gold = bool(member.get("membership") == "gold" or member.get("isGold"))
            m_membership = "gold" if is_gold else "basic"

            player_snapshot = {
                "identifier": m_username,
                "type": "player",
                "races": m_races,
                "accuracy": m_acc,
                "wpm": m_wpm,
                "points": m_points,
                "ppr": m_ppr,
                "online_status": bool(member.get("online", False)),
                "membership_status": m_membership,
                "car_img_url": m_car_url,
                "title": m_display,
                "team_tag": clean_tag
            }

            try:
                supabase.table("snapshots").insert(player_snapshot).execute()
            except Exception:
                pass

        print(f"[SUCCESS] Processed team [{clean_tag}] and all member snapshots.")

    except Exception as e:
        print(f"[EXCEPTION] Error scraping team '{clean_tag}': {e}")

def main():
    start_time = time.time()
    entities = fetch_tracked_entities()
    for entity in entities:
        identifier = entity.get("identifier")
        entity_type = entity.get("type")

        if identifier and entity_type == "team":
            scrape_team(identifier)
        time.sleep(0.1)

    elapsed = round(time.time() - start_time, 2)
    print(f"\n=== SCRAPE COMPLETED IN {elapsed} SECONDS ===")

if __name__ == "__main__":
    main()