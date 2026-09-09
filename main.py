import os
import time
import requests
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_tracked_entities():
    try:
        response = supabase.table("entities").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching entities: {e}")
        return []

def register_entity(identifier: str, entity_type: str, name: str = ""):
    """
    Registers or updates an entity. Automatically populates display name
    when retrieved from live Nitro Type endpoints.
    """
    if not identifier:
        return
    try:
        payload = {
            "identifier": identifier.lower().strip(),
            "type": entity_type
        }
        if name:
            payload["name"] = name

        supabase.table("entities").upsert(
            payload,
            on_conflict="identifier"
        ).execute()
    except Exception as e:
        print(f"Error registering entity {identifier}: {e}")

def scrape_player(username: str):
    clean_username = username.lower().strip()
    url = f"https://www.nitrotype.com/api/v2/u/{clean_username}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"Failed player {clean_username}: HTTP {res.status_code}")
            return
        
        data = res.json().get("results", {})
        profile = data.get("profile", {})
        stats = data.get("stats", {})

        races = int(stats.get("races", profile.get("races", 0)))
        wpm = float(stats.get("wpm", profile.get("avgSpeed", 0)))
        accuracy = float(stats.get("accuracy", profile.get("avgAcc", 0)))
        points = int(stats.get("points", profile.get("points", 0)))
        
        ppr = round(points / races, 2) if races > 0 else 0.00
        online_status = bool(profile.get("online", False) or profile.get("isActive", False))
        
        membership = profile.get("membership", "")
        is_gold = profile.get("isGold", False)
        membership_status = "gold" if (membership == "gold" or is_gold) else "basic"
        
        car_id = profile.get("carID", 1)
        car_hue = profile.get("carHue", 0)
        car_img_url = f"https://www.nitrotype.com/cars/48/{car_id}_{car_hue}.png"
        
        title = profile.get("title", "")
        team_tag = profile.get("tag", "")
        display_name = profile.get("displayName", clean_username)

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

        supabase.table("snapshots").insert(snapshot).execute()
        print(f"[PLAYER] {display_name} (@{clean_username}): {races} races | {wpm} WPM | [{team_tag}]")

    except Exception as e:
        print(f"Exception scraping player {clean_username}: {e}")

def scrape_team(team_tag: str):
    clean_tag = team_tag.lower().strip()
    url = f"https://www.nitrotype.com/api/v2/teams/{clean_tag}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"Failed team {clean_tag}: HTTP {res.status_code}")
            return
        
        data = res.json().get("results", {})
        info = data.get("info", {})
        stats = data.get("stats", {})
        members = data.get("members", [])

        official_team_name = info.get("name") or clean_tag.upper()
        register_entity(clean_tag, "team", official_team_name)

        races = int(stats.get("alltime_races", info.get("races", 0)))
        wpm = float(stats.get("avg_wpm", info.get("avgSpeed", 0)))
        accuracy = float(stats.get("avg_acc", info.get("avgAcc", 0)))
        points = int(stats.get("alltime_points", info.get("points", 0)))
        ppr = round(points / races, 2) if races > 0 else 0.00

        snapshot = {
            "identifier": clean_tag,
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
            "team_tag": clean_tag.upper()
        }

        supabase.table("snapshots").insert(snapshot).execute()
        print(f"[TEAM] {official_team_name} [{clean_tag.upper()}]: {races} races | {len(members)} members")

        # Recursive Auto-Discovery: Index all active players on the team
        for member in members:
            m_username = member.get("username", "")
            m_display = member.get("displayName", m_username)
            if m_username:
                register_entity(m_username, "player", m_display)

    except Exception as e:
        print(f"Exception scraping team {clean_tag}: {e}")

def main():
    start_time = time.time()
    entities = fetch_tracked_entities()
    print(f"Starting Dah Tracker scrape run for {len(entities)} registered entities...")

    for entity in entities:
        identifier = entity.get("identifier")
        entity_type = entity.get("type")

        if not identifier:
            continue

        if entity_type == "player":
            scrape_player(identifier)
        elif entity_type == "team":
            scrape_team(identifier)

        time.sleep(0.2)  # Rate-limit safety barrier

    elapsed = round(time.time() - start_time, 2)
    print(f"Scrape pass completed successfully in {elapsed} seconds.")

if __name__ == "__main__":
    main()