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

def scrape_player(username):
    clean_user = str(username).lower().strip()
    url = f"https://www.nitrotype.com/api/v2/racer/{clean_user}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"Could not fetch player {clean_user} (Status {res.status_code})")
            return
        
        json_data = res.json()
        results = json_data.get("results", {})
        if not results:
            return

        races = int(results.get("racesPlayed", 0))
        wpm = float(results.get("avgSpeed", 0))
        acc = float(results.get("avgAcc", 0))
        points = int(results.get("points", 0))
        ppr = round(points / races, 2) if races > 0 else 0.00
        
        car_id = results.get("carID", 1)
        car_url = f"https://www.nitrotype.com/cars/{car_id}_large_1.png"
        is_gold = bool(results.get("membership") == "gold" or results.get("gold") == 1)
        
        team_tag = str(results.get("tag", "")).upper().strip()
        display_name = results.get("displayName") or results.get("username") or clean_user

        player_snapshot = {
            "identifier": clean_user,
            "type": "player",
            "races": races,
            "accuracy": acc,
            "wpm": wpm,
            "points": points,
            "ppr": ppr,
            "online_status": bool(results.get("online", False)),
            "membership_status": "gold" if is_gold else "basic",
            "car_img_url": car_url,
            "title": display_name,
            "team_tag": team_tag
        }

        supabase.table("snapshots").insert(player_snapshot).execute()
        print(f"Successfully scraped player: {clean_user} (Team: {team_tag}, Races: {races}, Points: {points}, PPR: {ppr})")

    except Exception as e:
        print(f"Error scraping player {clean_user}: {e}")

def scrape_team(team_tag):
    clean_tag = str(team_tag).upper().strip()
    url = f"https://www.nitrotype.com/api/v2/teams/{clean_tag}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"Could not fetch team {clean_tag}")
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

        for m in members:
            m_username = str(m.get("username") or "").lower().strip()
            if m_username:
                # Also scrape full profile for team members to keep them updated
                scrape_player(m_username)

            m_races = int(m.get("played", m.get("races", 0)))
            m_wpm = float(m.get("avgSpeed", m.get("wpm", 0)))
            m_acc = float(m.get("avgAcc", m.get("accuracy", 0)))
            m_points = int(m.get("points", 0))

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
        print(f"Successfully scraped team: [{clean_tag}] {official_name}")

    except Exception as e:
        print(f"Error scraping team {clean_tag}: {e}")

def main():
    entities = fetch_entities()
    if not entities:
        print("No entities found in Supabase 'entities' table.")
        return

    for e in entities:
        entity_type = e.get("type")
        identifier = e.get("identifier")
        
        if entity_type == "player":
            scrape_player(identifier)
        elif entity_type == "team":
            scrape_team(identifier)
            
        time.sleep(1) # Polite delay between requests

if __name__ == "__main__":
    main()
