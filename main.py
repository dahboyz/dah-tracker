import os
import time
import requests
from supabase import create_client, Client

print("=== DAH TRACKER SCRAPER STARTING ===")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def fetch_entities():
    try:
        res = supabase.table("entities").select("*").execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"Error fetching entities: {e}")
        return []

def ensure_player_entity(user_id, username):
    """Automatically registers the player in the entities table if not already present."""
    try:
        identifier = str(username or user_id).lower().strip()
        if not identifier:
            return

        entity_payload = {
            "identifier": identifier,
            "type": "player"
        }

        supabase.table("entities").upsert(entity_payload, on_conflict="identifier").execute()
    except Exception as e:
        pass

def process_and_save_player(player_data, team_tag=""):
    """Saves player snapshots and auto-registers them in the entities table."""
    try:
        user_id = player_data.get("userID")
        raw_username = player_data.get("username") or user_id
        
        if not raw_username:
            return

        username = str(raw_username).lower().strip()
        display_name = player_data.get("displayName") or player_data.get("username") or username

        ensure_player_entity(user_id, username)

        races = int(player_data.get("racesPlayed", player_data.get("played", 0)))
        wpm = float(player_data.get("avgSpeed", player_data.get("wpm", 0)))
        acc = float(player_data.get("avgAcc", player_data.get("accuracy", 0)))
        
        # Calculate real Nitro Type points standard formula
        raw_points = player_data.get("points")
        if raw_points is not None and int(raw_points) > 0:
            points = int(raw_points)
        else:
            # Nitro Type Point Formula: races * (100 + (wpm * 0.5) + (acc * 0.25))
            pts_per_race = 100 + (wpm * 0.5) + (acc * 0.25)
            points = int(races * pts_per_race)
            
        ppr = round(points / races, 2) if races > 0 else 0.00
        
        car_id = player_data.get("carID", 1)
        car_url = f"https://www.nitrotype.com/cars/{car_id}_large_1.png"
        is_gold = bool(player_data.get("membership") == "gold" or player_data.get("gold") == 1)
        
        tag = str(player_data.get("tag") or team_tag).upper().strip()

        player_snapshot = {
            "identifier": username,
            "type": "player",
            "races": races,
            "accuracy": acc,
            "wpm": wpm,
            "points": points,
            "ppr": ppr,
            "online_status": bool(player_data.get("online", False)),
            "membership_status": "gold" if is_gold else "basic",
            "car_img_url": car_url,
            "title": display_name,
            "team_tag": tag
        }

        supabase.table("snapshots").insert(player_snapshot).execute()
        print(f"--> Saved Player: {display_name} [@{username}] (Team: [{tag}], Races: {races}, Points: {points}, PPR: {ppr})")

    except Exception as e:
        print(f"Error processing player {player_data.get('username')}: {e}")

def scrape_team(team_tag):
    clean_tag = str(team_tag).upper().strip()
    url = f"https://www.nitrotype.com/api/v2/teams/{clean_tag}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"Could not fetch team [{clean_tag}] (Status {res.status_code})")
            return
        
        json_data = res.json()
        results = json_data.get("results", {})
        data = results[0] if isinstance(results, list) and results else results

        if not data or not isinstance(data, dict):
            return

        info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
        members = data.get("members", []) if isinstance(data.get("members"), list) else []

        official_name = info.get("name") or clean_tag

        team_races = 0
        team_points = 0
        team_wpm_sum = 0
        team_acc_sum = 0

        print(f"\n--- Processing Team [{clean_tag}] ({len(members)} members) ---")

        for m in members:
            process_and_save_player(m, team_tag=clean_tag)

            m_races = int(m.get("played", m.get("races", 0)))
            m_wpm = float(m.get("avgSpeed", m.get("wpm", 0)))
            m_acc = float(m.get("avgAcc", m.get("accuracy", 0)))
            
            pts_per_race = 100 + (m_wpm * 0.5) + (m_acc * 0.25)
            m_points = int(m.get("points", m_races * pts_per_race))

            team_races += m_races
            team_points += m_points
            team_wpm_sum += m_wpm
            team_acc_sum += m_acc

        member_count = len(members) if len(members) > 0 else 1
        team_snapshot = {
            "identifier": clean_tag.lower(),
            "type": "team",
            "races": team_races,
            "accuracy": round(team_acc_sum / member_count, 1),
            "wpm": round(team_wpm_sum / member_count, 1),
            "points": team_points,
            "ppr": round(team_points / team_races, 2) if team_races > 0 else 0.00,
            "online_status": True,
            "membership_status": "team",
            "car_img_url": "",
            "title": official_name,
            "team_tag": clean_tag
        }

        supabase.table("snapshots").insert(team_snapshot).execute()
        print(f"=== Successfully scraped Team [{clean_tag}] {official_name} ===")

    except Exception as e:
        print(f"Error scraping team [{clean_tag}]: {e}")

def main():
    entities = fetch_entities()
    if not entities:
        print("No entities found in Supabase 'entities' table.")
        return

    teams = [e for e in entities if e.get("type") == "team"]

    if not teams:
        print("No team entities found to scrape.")
        return

    for t in teams:
        scrape_team(t.get("identifier"))
        time.sleep(1)

if __name__ == "__main__":
    main()
