import os
import time
import requests
from supabase import create_client, Client

print("=== NITRO TYPE SCRAPER STARTING ===")

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

def scrape_team(team_tag):
    clean_tag = str(team_tag).upper().strip()
    url = f"https://www.nitrotype.com/api/v2/teams/{clean_tag}"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
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

        for m in members:
            m_username = str(m.get("username") or "").lower().strip()
            if not m_username:
                continue

            m_display = m.get("displayName") or m.get("username") or m_username
            m_races = int(m.get("played", m.get("races", 0)))
            m_wpm = float(m.get("avgSpeed", m.get("wpm", 0)))
            m_acc = float(m.get("avgAcc", m.get("accuracy", 0)))
            m_points = int(m.get("points", m_races * 100))
            m_ppr = round(m_points / m_races, 2) if m_races > 0 else 0.00

            m_car_id = m.get("carID", 1)
            m_car_url = f"https://www.nitrotype.com/cars/{m_car_id}_large_1.png"
            is_gold = bool(m.get("membership") == "gold" or m.get("isGold") or m.get("gold") == 1)

            team_races += m_races
            team_points += m_points
            team_wpm_sum += m_wpm
            team_acc_sum += m_acc

            player_snapshot = {
                "identifier": m_username,
                "type": "player",
                "races": m_races,
                "accuracy": m_acc,
                "wpm": m_wpm,
                "points": m_points,
                "ppr": m_ppr,
                "online_status": bool(m.get("online", False)),
                "membership_status": "gold" if is_gold else "basic",
                "car_img_url": m_car_url,
                "title": m_display,
                "team_tag": clean_tag
            }

            supabase.table("snapshots").insert(player_snapshot).execute()

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

    except Exception as e:
        print(f"Scrape error for {clean_tag}: {e}")

def main():
    entities = fetch_entities()
    for e in entities:
        if e.get("type") == "team":
            scrape_team(e.get("identifier"))

if __name__ == "__main__":
    main()
