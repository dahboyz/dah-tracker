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

def format_car_url(player_data):
    # Direct CDN paths if returned by NT API
    for key in ["car", "car_img_url", "car_url", "carImgUrl", "carImage"]:
        val = player_data.get(key)
        if val and isinstance(val, str) and len(val) > 3:
            if val.startswith("http"):
                return val
            clean_path = val.lstrip('/')
            return f"https://www.nitrotype.com/{clean_path}"

    # Extract integer carID and hue
    car_id = player_data.get("carID") or player_data.get("car_id") or player_data.get("carId") or 1
    car_hue = player_data.get("carHue") or player_data.get("car_hue") or 1
    
    try:
        cid = int(car_id)
    except (ValueError, TypeError):
        cid = 1

    try:
        hue = int(car_hue)
    except (ValueError, TypeError):
        hue = 1

    return f"https://www.nitrotype.com/cars/{cid}_large_{hue}.png"

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
        
        car_url = format_car_url(player_data)
        
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

        player_snapshots = []
        for m in members:
            snap = process_and_save_player(m, team_tag=clean_tag)
            if snap:
                player_snapshots.append(snap)

                m_races = snap["races"]
                m_wpm = snap["wpm"]
                m_acc = snap["accuracy"]
                m_points = snap["points"]

                team_races += m_races
                team_points += m_points
                team_wpm_sum += m_wpm
                team_acc_sum += m_acc

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
        print(f"=== Successfully scraped Team [{clean_tag}] {official_name} ({len(members)} members) ===")

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
        print(f"Error scraping direct player {username}: {e}")

def main():
    start_time = time.time()
    entities = fetch_entities()
    if not entities:
        print("No entities found in Supabase 'entities' table.")
        return

    teams = [e for e in entities if e.get("type") == "team"]
    players = [e for e in entities if e.get("type") == "player"]

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scrape_team, t.get("identifier")) for t in teams]
        futures += [executor.submit(scrape_player_direct, p.get("identifier")) for p in players]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                print(f"Task generated an exception: {exc}")

    print(f"=== SCRAPER COMPLETED IN {round(time.time() - start_time, 2)} SECONDS ===")

if __name__ == "__main__":
    main()
