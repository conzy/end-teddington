import requests
import json
import time
import re
from datetime import datetime

# List of 51 PL clubs
pl_clubs_list = [
    "Arsenal", "Aston Villa", "Barnsley", "Birmingham City", "Blackburn Rovers",
    "Blackpool", "Bolton Wanderers", "Bournemouth", "Bradford City", "Brentford",
    "Brighton & Hove Albion", "Burnley", "Cardiff City", "Charlton Athletic", "Chelsea",
    "Coventry City", "Crystal Palace", "Derby County", "Everton", "Fulham",
    "Huddersfield Town", "Hull City", "Ipswear Town", "Leeds United", "Leicester City",
    "Liverpool", "Luton Town", "Manchester City", "Manchester United", "Middlesbrough",
    "Newcastle United", "Norwich City", "Nottingham Forest", "Oldham Athletic", "Portsmouth",
    "Queens Park Rangers", "Reading", "Sheffield United", "Sheffield Wednesday", "Southampton",
    "Stoke City", "Sunderland", "Swansea City", "Swindon Town", "Tottenham Hotspur",
    "Watford", "West Bromwich Albion", "West Ham United", "Wigan Athletic", "Wimbledon",
    "Wolverhampton Wanderers"
]

def clean_club_name(name):
    # Remove common suffixes
    name = re.sub(r'\b(F\.C\.|FC|A\.F\.C\.|AFC|F\. C\.)\b', '', name)
    name = re.sub(r'\bFootball Club\b', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    name = name.strip()
    return name

def fetch_wikidata_living_players():
    """
    Fetches all living football players with a Premier League Player ID (P12539).
    Includes a robust retry mechanism.
    """
    url = "https://query.wikidata.org/sparql"
    query = """
    SELECT ?player ?name ?plId ?birthDate ?nationalityLabel WHERE {
      ?player wdt:P12539 ?plId .
      ?player rdfs:label ?name .
      FILTER (LANG(?name) = "en")

      # Filter out players who have a date of death
      FILTER NOT EXISTS { ?player wdt:P570 ?death . }

      OPTIONAL { ?player wdt:P569 ?birthDate . }
      OPTIONAL {
        ?player wdt:P27 ?nationality .
        ?nationality rdfs:label ?nationalityLabel .
        FILTER (LANG(?nationalityLabel) = "en")
      }
    }
    """
    headers = {
        "User-Agent": "PremierLeagueTriviaBot/1.0 (contact@example.com)",
        "Accept": "application/json"
    }

    print("Fetching living players from Wikidata...")
    for attempt in range(5):
        try:
            response = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=30)
            if response.status_code == 200:
                results = response.json().get("results", {}).get("bindings", [])
                break
            else:
                print(f"Wikidata returned status {response.status_code}, retrying...")
                time.sleep(2)
        except Exception as e:
            print(f"Exception during Wikidata query: {e}, retrying...")
            time.sleep(2)
    else:
        raise Exception("Failed to fetch living players from Wikidata after 5 attempts.")

    living_players = {}
    for r in results:
        pl_id_str = r.get("plId", {}).get("value")
        if not pl_id_str:
            continue
        clean_id_str = pl_id_str.split("/")[0]
        try:
            pl_id = int(float(clean_id_str))
        except ValueError:
            continue

        name = r.get("name", {}).get("value")
        dob = r.get("birthDate", {}).get("value", "")
        nationality = r.get("nationalityLabel", {}).get("value", "")

        # Parse birth year
        birth_year = None
        if dob:
            match = re.match(r"^(\d{4})", dob)
            if match:
                birth_year = int(match.group(1))

        living_players[pl_id] = {
            "id": pl_id,
            "name": name,
            "birth_year": birth_year,
            "nationality": nationality,
            "teams": set()
        }

    print(f"Loaded {len(living_players)} living players from Wikidata.")
    return living_players

def fetch_wikidata_clubs_for_ids(player_ids, living_players):
    """
    Fetches club relationships from Wikidata only for specified player IDs using a VALUES block.
    Includes robust retry mechanism.
    """
    url = "https://query.wikidata.org/sparql"
    ids_str = " ".join(f'"{pid}"' for pid in player_ids)

    query = f"""
    SELECT ?plId ?clubLabel WHERE {{
      VALUES ?plId {{ {ids_str} }}
      ?player wdt:P12539 ?plId .
      ?player p:P54 ?statement .
      ?statement ps:P54 ?club .
      ?club rdfs:label ?clubLabel .
      FILTER (LANG(?clubLabel) = "en")
    }}
    """
    headers = {
        "User-Agent": "PremierLeagueTriviaBot/1.0 (contact@example.com)",
        "Accept": "application/json"
    }

    # Build standard mapping to simplify matching
    standard_mapping = {}
    for club in pl_clubs_list:
        clean_club = clean_club_name(club)
        standard_mapping[clean_club.lower()] = club

    for attempt in range(5):
        try:
            response = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=20)
            if response.status_code == 200:
                results = response.json().get("results", {}).get("bindings", [])
                break
            else:
                print(f"Wikidata club query returned status {response.status_code}, retrying...")
                time.sleep(2)
        except Exception as e:
            print(f"Exception during Wikidata club query: {e}, retrying...")
            time.sleep(2)
    else:
        print("Failed to fetch clubs for batch, skipping.")
        return 0

    matched_count = 0
    for r in results:
        pl_id_str = r.get("plId", {}).get("value")
        if not pl_id_str:
            continue
        clean_pl_id = pl_id_str.split("/")[0]
        try:
            pl_id = int(float(clean_pl_id))
        except ValueError:
            continue

        if pl_id not in living_players:
            continue

        club_label = r.get("clubLabel", {}).get("value")
        clean_lbl = clean_club_name(club_label).lower()

        matched_club = None
        for std_clean, std_name in standard_mapping.items():
            if std_clean in clean_lbl or clean_lbl in std_clean:
                matched_club = std_name
                break

        if matched_club:
            living_players[pl_id]["teams"].add(matched_club)
            matched_count += 1

    return matched_count

def fetch_all_time_appearances():
    """
    Fetches all-time Premier League player appearances from the official Pulse Live stats endpoint.
    """
    pl_url = "https://footballapi.pulselive.com/football/stats/ranked/players/appearances"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Origin": "https://www.premierleague.com"
    }

    all_players = []
    page = 0
    print("Fetching all-time appearances from Premier League API...")
    while True:
        params = {
            "page": page,
            "pageSize": 1000,
            "comps": 1
        }
        for attempt in range(5):
            try:
                resp = requests.get(pl_url, headers=headers, params=params, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("stats", {}).get("content", [])
                    break
                else:
                    print(f"Status Code: {resp.status_code} for page {page}, retrying...")
                    time.sleep(2)
            except Exception as e:
                print(f"Exception for page {page}: {e}, retrying...")
                time.sleep(2)
        else:
            print("Failed to fetch page after 5 attempts:", page)
            break

        if not content:
            break
        all_players.extend(content)
        print(f"Fetched page {page}, got {len(content)} players. Total so far: {len(all_players)}")
        if len(content) < 1000:
            break
        page += 1
        time.sleep(0.5)

    return all_players

def clean_nationality(nat):
    if nat == "United Kingdom":
        return "England"
    return nat

def main():
    living_players = fetch_wikidata_living_players()
    appearances_records = fetch_all_time_appearances()

    # Process and combine initial player profiles
    final_players_map = {}
    standard_mapping = {clean_club_name(club).lower(): club for club in pl_clubs_list}

    for p in appearances_records:
        owner = p.get("owner", {})
        pl_id_raw = owner.get("id")
        if pl_id_raw is None:
            continue
        pl_id = int(float(pl_id_raw))

        if pl_id in living_players:
            wiki_p = living_players[pl_id]

            # Extract name parts
            first_name = owner.get("name", {}).get("first", "")
            last_name = owner.get("name", {}).get("last", "")
            if not first_name and not last_name:
                display_name = owner.get("name", {}).get("display", "")
                parts = display_name.split()
                if parts:
                    first_name = parts[0]
                    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

            # Use display name as fallback if name parts are empty
            if not first_name:
                first_name = owner.get("name", {}).get("display", "Unknown")
                last_name = ""

            # Get teams from Pulse Live currentTeam & previousTeam
            api_teams = set()
            for team_key in ["currentTeam", "previousTeam"]:
                t_obj = owner.get(team_key, {})
                if t_obj:
                    t_name = t_obj.get("name")
                    if t_name:
                        clean_t = clean_club_name(t_name).lower()
                        for std_clean, std_name in standard_mapping.items():
                            if std_clean in clean_t or clean_t in std_clean:
                                api_teams.add(std_name)

            # Fallback birth year from API if Wikidata birth year is missing
            birth_year = wiki_p["birth_year"]
            if not birth_year:
                dob_lbl = owner.get("birth", {}).get("date", {}).get("label", "")
                if dob_lbl:
                    parts = dob_lbl.split()
                    if parts:
                        try:
                            birth_year = int(parts[-1])
                        except ValueError:
                            pass

            # Fallback nationality from API if Wikidata nationality is missing
            nationality = wiki_p["nationality"]
            if not nationality:
                nationality = owner.get("nationalTeam", {}).get("country", "")

            nationality = clean_nationality(nationality)

            final_players_map[pl_id] = {
                "id": pl_id,
                "first_name": first_name,
                "last_name": last_name,
                "birth_year": birth_year or "Unknown",
                "is_alive": True,
                "nationality": nationality or "Unknown",
                "appearances": int(float(p.get("value", 0))),
                "teams": api_teams
            }

    print(f"Total initial living players from appearances: {len(final_players_map)}")

    # Calculate combinations to find which players are actually in pairs summing to 450
    players_list = list(final_players_map.values())
    valid_pairs = []
    active_player_ids = set()

    for i in range(len(players_list)):
        for j in range(i + 1, len(players_list)):
            p1 = players_list[i]
            p2 = players_list[j]
            if p1["appearances"] + p2["appearances"] == 450:
                valid_pairs.append((p1["id"], p2["id"]))
                active_player_ids.add(p1["id"])
                active_player_ids.add(p2["id"])

    print(f"Total valid pairings found: {len(valid_pairs)}")
    print(f"Total unique players involved in pairings: {len(active_player_ids)}")

    # Fetch clubs ONLY for the active players from Wikidata
    active_player_ids_list = list(active_player_ids)
    batch_size = 100
    total_matched_clubs = 0
    print("Fetching club mappings from Wikidata for active players in batches of 100...")
    for i in range(0, len(active_player_ids_list), batch_size):
        batch = active_player_ids_list[i:i+batch_size]
        try:
            matched = fetch_wikidata_clubs_for_ids(batch, final_players_map)
            total_matched_clubs += matched
            print(f"  Processed batch {i // batch_size + 1}/{len(active_player_ids_list) // batch_size + 1}, matched {matched} relationships.")
            time.sleep(0.5)
        except Exception as e:
            print(f"  Failed to fetch clubs for batch starting at index {i}: {e}")

    # Compile the final player directory and structures
    player_directory = {}
    for pid, pdata in final_players_map.items():
        if pid in active_player_ids:
            # Union of Wikidata teams and API teams
            all_teams = pdata["teams"].union(living_players[pid]["teams"])
            player_directory[str(pid)] = {
                "id": pid,
                "first_name": pdata["first_name"],
                "last_name": pdata["last_name"],
                "birth_year": pdata["birth_year"],
                "is_alive": pdata["is_alive"],
                "nationality": pdata["nationality"],
                "appearances": pdata["appearances"],
                "teams": sorted(list(all_teams))
            }

    # Structure views
    all_combinations = [list(pair) for pair in valid_pairs]

    def pair_difference(pair):
        p1 = final_players_map[pair[0]]
        p2 = final_players_map[pair[1]]
        return abs(p1["appearances"] - p2["appearances"])

    ranked_by_balance = sorted(all_combinations, key=pair_difference)

    # Export results.json
    results = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_appearances": 450,
        "views": {
            "all_combinations": all_combinations,
            "ranked_by_balance": ranked_by_balance,
            "player_directory": player_directory
        }
    }

    output_filename = "results.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated {output_filename} with {len(all_combinations)} pairings and {len(player_directory)} players.")

if __name__ == "__main__":
    main()
