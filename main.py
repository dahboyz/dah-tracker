import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client, Client

print("=== DAH TRACKER SCRAPER STARTING ===")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
})

def fetch_entities():
    try:
        res = supabase.table("entities").select("*").execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"Error fetching entities: {e}")
        return []

def ensure_player_entity(user_id, username):
    try:
        identifier = str(username or user_id).lower().strip()
        if not identifier:
            return
        entity_payload = {
            "identifier": identifier,
            "type": "player"
        }
        supabase.table("entities").upsert(entity_payload, on_conflict="identifier").execute()
    except Exception:
        pass

def extract_car_id(player_data):
    car_id = player_data.get("carID") or player_data.get("car_id") or player_data.get("carId")
    if not car_id:
        car_obj = player_data.get("car")
        if isinstance(car_obj, dict):
            car_id = car_obj.get("carID") or car_obj.get("id") or car_obj.get("car_id")
        elif isinstance(car_obj, (int, str)):
            car_id = car_obj

    try:
        return int(car_id)
    except (ValueError, TypeError):
        return 1

def process_and_save_player(player_data, team_tag=""):
    try:
        user_id = player_data.get("userID") or player_data.get("id")
        raw_username = player_data.get("username") or player_data.get("identifier") or user_id
        
        if not raw_username:
            return None

        username = str(raw_username).lower().strip()
        display_name = player_data.get("displayName") or player_data.get("name") or player_data.get("username") or username

        ensure_player_entity(user_id, username)

        races = int(player_data.get("racesPlayed") or player_data.get("played") or player_data.get("races") or 0)
        wpm = float(player_data.get("avgSpeed") or player_data.get("wpm") or player_data.get("speed") or 0)
        acc = float(player_data.get("avgAcc") or player_data.get("accuracy") or player_data.get("acc") or 0)
        
        pts_per_race = 100 + (wpm * 0.5) + (acc * 0.25)
        calc_points = int(races * pts_per_race)

        raw_points = player_data.get("points")
        if raw_points is not None and int(raw_points) >= calc_points * 0.5:
            points = int(raw_points)
        else:
            points = calc_points
            
        ppr = round(points / races, 2) if races > 0 else 0.00
        
        car_id = extract_car_id(player_data)
        car_url = f"https://nitrotype.info/assets/images/cars/{car_id}_large_1.webp"
        
        is_gold = bool(player_data.get("membership") == "gold" or player_data.get("gold") == 1 or player_data.get("membership") == 1)
        tag = str(player_data.get("tag") or team_tag).upper().strip()

        player_snapshot = {
            "identifier": username,
            "type": "player",
            "races": races,
            "accuracy": round(acc, 2),
            "wpm": round(wpm, 1),
            "points": points,
            "ppr": ppr,
            "online_status": bool(player_data.get("online", False)),
            "membership_status": "gold" if is_gold else "basic",
            "car_img_url": car_url,
            "title": display_name,
            "team_tag": tag
        }

        return player_snapshot

    except Exception as e:
        print(f"Error processing player {player_data.get('username')}: {e}")
        return None

def scrape_team(team_tag):
    clean_tag = str(team_tag).upper().strip()
    url = f"https://www.nitrotype.com/api/v2/teams/{clean_tag}"
    
    try:
        res = session.get(url, timeout=8)
        if res.status_code != 200:
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

        player_snapshots = []
        for m in members:
            snap = process_and_save_player(m, team_tag=clean_tag)
            if snap:
                player_snapshots.append(snap)

                team_races += snap["races"]
                team_points += snap["points"]
                team_wpm_sum += snap["wpm"]
                team_acc_sum += snap["accuracy"]

        if player_snapshots:
            supabase.table("snapshots").insert(player_snapshots).execute()

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
        print(f"=== Scraped Team [{clean_tag}] ({len(members)} members) ===")

    except Exception as e:
        print(f"Error scraping team [{clean_tag}]: {e}")

def scrape_player_direct(username):
    url = f"https://www.nitrotype.com/api/v2/u/{username}"
    try:
        res = session.get(url, timeout=8)
        if res.status_code == 200:
            json_data = res.json()
            results = json_data.get("results", {})
            if isinstance(results, dict):
                snap = process_and_save_player(results)
                if snap:
                    supabase.table("snapshots").insert(snap).execute()
    except Exception as e:
        print(f"Error scraping player {username}: {e}")

def main():
    start_time = time.time()
    entities = fetch_entities()
    if not entities:
        return

    teams = [e for e in entities if e.get("type") == "team"]
    players = [e for e in entities if e.get("type") == "player"]

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scrape_team, t.get("identifier")) for t in teams]
        futures += [executor.submit(scrape_player_direct, p.get("identifier")) for p in players]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass

    print(f"=== SCRAPER COMPLETED IN {round(time.time() - start_time, 2)} SECONDS ===")

if __name__ == "__main__":
    main()
