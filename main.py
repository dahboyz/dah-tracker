import os
import time
import requests
from supabase import create_client, Client

print("=== STARTING NITRO TYPE SCRAPER (DEBUG MODE) ===")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[CRITICAL ERROR] Missing SUPABASE_URL or SUPABASE_KEY environment variables!")
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")
else:
    print(f"[INIT] Supabase URL detected: {SUPABASE_URL[:15]}...")

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
    print("[DB] Fetching entities from 'entities' table...")
    try:
        response = supabase.table("entities").select("*").execute()
        entities = response.data if response.data else []
        print(f"[DB SUCCESS] Found {len(entities)} entities registered in database.")
        for idx, ent in enumerate(entities):
            print(f"   -> Entity {idx+1}: type='{ent.get('type')}', identifier='{ent.get('identifier')}'")
        return entities
    except Exception as e:
        print(f"[DB ERROR] Exception while fetching entities: {e}")
        return []

def register_entity(identifier: str, entity_type: str, name: str = ""):
    if not identifier:
        print("[WARN] Attempted to register empty identifier. Skipped.")
        return
    clean_id = identifier.lower().strip()
    try:
        payload = {
            "identifier": clean_id,
            "type": entity_type
        }
        if name:
            payload["name"] = name

        res = supabase.table("entities").upsert(
            payload,
            on_conflict="identifier"
        ).execute()
        print(f"[DB UPSERT] Successfully registered/updated entity -> type: {entity_type}, identifier: {clean_id}")
    except Exception as e:
        print(f"[DB ERROR] Failed to register entity '{clean_id}' ({entity_type}): {e}")

def scrape_player(username: str):
    clean_username = username.lower().strip()
    url = f"https://www.nitrotype.com/api/v2/u/{clean_username}"
    print(f"\n[SCRAPE PLAYER] Requesting Nitro Type API for player: '{clean_username}' -> URL: {url}")
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"[HTTP RESPONSE] Player '{clean_username}' status code: {res.status_code}")
        
        if res.status_code != 200:
            print(f"[FAIL] Could not fetch player '{clean_username}'. Response text: {res.text[:200]}")
            return
        
        json_data = res.json()
        results = json_data.get("results", {})
        
        if isinstance(results, list):
            data = results[0] if len(results) > 0 else {}
        else:
            data = results

        if not data:
            print(f"[WARN] Player API response has no valid data for '{clean_username}'. Raw JSON: {str(json_data)[:300]}")
            return

        profile = data.get("profile", {})
        stats = data.get("stats", {})

        races = int(stats.get("races", profile.get("races", 0)))
        wpm = float(stats.get("wpm", profile.get("avgSpeed", 0)))
        accuracy = float(stats.get("accuracy", profile.get("avgAcc", 0)))
        points = int(stats.get("points", profile.get("points", 0)))
        
        ppr = round(points / races, 2) if races > 0 else 0.00
        online_status = bool(profile.get("online", False) or profile.get("isActive", False))
        
        membership = profile.get("membership", "")
        is_gold = profile.get("isGold", False) or profile.get("gold", False)
        membership_status = "gold" if (membership == "gold" or is_gold) else "basic"
        
        car_id = profile.get("carID", 1)
        car_hue = profile.get("carHue", 0)
        car_img_url = f"https://www.nitrotype.com/cars/48/{car_id}_{car_hue}.png"
        
        title = profile.get("title", "")
        team_tag = profile.get("tag", "")
        display_name = profile.get("displayName", clean_username)

        print(f"[PARSED PLAYER] Name: {display_name} | Races: {races} | WPM: {wpm} | Points: {points} | Gold: {membership_status == 'gold'} | Team: {team_tag}")

        register_entity(clean_username, "player", display_name)

        snapshot = {
            "identifier": clean_username,
            "type": "player",
            "races": races,
            "accuracy": accuracy,
            "wpm": wpm,
            "points": points,
            "ppr": ppr,
            "online_status": online_status,
            "membership_status": membership_status,
            "car_img_url": car_img_url,
            "title": title,
            "team_tag": team_tag
        }

        print(f"[DB INSERT] Inserting player snapshot for '{clean_username}' into 'snapshots' table...")
        supabase.table("snapshots").insert(snapshot).execute()
        print(f"[DB INSERT SUCCESS] Player snapshot saved for '{clean_username}'.")

    except Exception as e:
        print(f"[EXCEPTION] Error occurred while scraping player '{clean_username}': {e}")

def scrape_team(team_tag: str):
    clean_tag = team_tag.upper().strip()
    url = f"https://www.nitrotype.com/api/v2/teams/{clean_tag}"
    print(f"\n[SCRAPE TEAM] Requesting Nitro Type API for team tag: '{clean_tag}' -> URL: {url}")
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        print(f"[HTTP RESPONSE] Team '{clean_tag}' status code: {res.status_code}")
        
        if res.status_code != 200:
            print(f"[FAIL] Could not fetch team '{clean_tag}'. Response text: {res.text[:200]}")
            return
        
        json_data = res.json()
        results = json_data.get("results", {})
        
        if isinstance(results, list):
            data = results[0] if len(results) > 0 else {}
        else:
            data = results

        if not data:
            print(f"[WARN] Team API response has no valid data for '{clean_tag}'. Raw JSON: {str(json_data)[:300]}")
            return

        info = data.get("info", {})
        stats = data.get("stats", {})
        members = data.get("members", [])

        official_team_name = info.get("name") or clean_tag
        print(f"[PARSED TEAM] Official Name: {official_team_name} | Total Members Found in API: {len(members)}")

        register_entity(clean_tag.lower(), "team", official_team_name)

        races = int(stats.get("alltime_races", info.get("races", 0)))
        wpm = float(stats.get("avg_wpm", info.get("avgSpeed", 0)))
        accuracy = float(stats.get("avg_acc", info.get("avgAcc", 0)))
        points = int(stats.get("alltime_points", info.get("points", 0)))
        ppr = round(points / races, 2) if races > 0 else 0.00

        snapshot = {
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
            "title": official_team_name,
            "team_tag": clean_tag
        }

        print(f"[DB INSERT] Inserting team snapshot for '{clean_tag.lower()}' into 'snapshots' table...")
        supabase.table("snapshots").insert(snapshot).execute()
        print(f"[DB INSERT SUCCESS] Team snapshot saved for '{clean_tag.lower()}'.")

        print(f"[AUTO-DISCOVERY] Processing roster members for team [{clean_tag}]...")
        for member in members:
            m_username = member.get("username", "")
            m_display = member.get("displayName", m_username)
            if m_username:
                print(f"   -> Discovered team member: username='{m_username}', display='{m_display}'")
                register_entity(m_username, "player", m_display)
            else:
                print(f"   -> Skipped member entry because username was blank: {member}")

    except Exception as e:
        print(f"[EXCEPTION] Error occurred while scraping team '{clean_tag}': {e}")

def main():
    start_time = time.time()
    print("\n--- BEGIN PASS 1: PROCESSING REGISTERED ENTITIES ---")
    
    initial_entities = fetch_tracked_entities()
    if not initial_entities:
        print("[CRITICAL WARNING] Pass 1 found 0 entities in the 'entities' table!")

    for idx, entity in enumerate(initial_entities):
        identifier = entity.get("identifier")
        entity_type = entity.get("type")

        print(f"\n--- Processing Entity [{idx+1}/{len(initial_entities)}] | Type: {entity_type} | ID: {identifier} ---")

        if not identifier:
            continue

        if entity_type == "player":
            scrape_player(identifier)
        elif entity_type == "team":
            scrape_team(identifier)

        time.sleep(0.2)

    print("\n--- BEGIN PASS 2: SCRAPING AUTO-DISCOVERED TEAM MEMBERS ---")
    updated_entities = fetch_entities_pass2 = fetch_tracked_entities()
    already_scraped = {e.get("identifier") for e in initial_entities if e.get("type") == "player"}
    
    new_players = [
        e.get("identifier") for e in updated_entities 
        if e.get("type") == "player" and e.get("identifier") not in already_scraped
    ]

    print(f"[INFO] Found {len(new_players)} newly discovered players to scrape in Pass 2.")

    if new_players:
        for idx, username in enumerate(new_players):
            print(f"\n--- Scraping New Player [{idx+1}/{len(new_players)}] | Username: {username} ---")
            scrape_player(username)
            time.sleep(0.2)

    elapsed = round(time.time() - start_time, 2)
    print(f"\n=== SCRAPE PASS COMPLETED SUCCESSFULLY IN {elapsed} SECONDS ===")

if __name__ == "__main__":
    main()