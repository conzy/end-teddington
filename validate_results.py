import json
import os
import sys

def main():
    print("Starting results.json structural validation...")

    # 1. Check file existence
    if not os.path.exists("results.json"):
        print("FAIL: results.json does not exist!")
        sys.exit(1)

    # 2. Check JSON validity
    try:
        with open("results.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"FAIL: results.json is not valid JSON! Error: {e}")
        sys.exit(1)

    print("PASS: results.json exists and is valid JSON.")

    # 3. Check key fields
    required_keys = ["generated_at", "target_appearances", "views"]
    for key in required_keys:
        if key not in data:
            print(f"FAIL: Missing key '{key}' in root!")
            sys.exit(1)
    print("PASS: Required root keys present.")

    # 4. Check target appearances
    if data["target_appearances"] != 450:
        print(f"FAIL: target_appearances is {data['target_appearances']}, expected 450!")
        sys.exit(1)
    print("PASS: target_appearances is exactly 450.")

    # 5. Check views keys
    required_view_keys = ["all_combinations", "ranked_by_balance", "player_directory"]
    views = data["views"]
    for key in required_view_keys:
        if key not in views:
            print(f"FAIL: Missing view key '{key}' in views!")
            sys.exit(1)
    print("PASS: Required view keys present.")

    # 6. Verify player directory structure
    pd = views["player_directory"]
    if not isinstance(pd, dict):
        print("FAIL: player_directory is not a dictionary!")
        sys.exit(1)

    for pid, p in pd.items():
        # verify key matches id
        if str(p.get("id")) != pid:
            print(f"FAIL: Player ID mismatch: key '{pid}' but id in object is {p.get('id')}!")
            sys.exit(1)

        required_player_fields = ["id", "first_name", "last_name", "birth_year", "is_alive", "nationality", "appearances", "teams"]
        for field in required_player_fields:
            if field not in p:
                print(f"FAIL: Player {pid} is missing required field '{field}'!")
                sys.exit(1)

        # appearances must be >= 1
        if p["appearances"] < 1:
            print(f"FAIL: Player {pid} has invalid appearances: {p['appearances']}!")
            sys.exit(1)

        # is_alive must be True
        if p["is_alive"] is not True:
            print(f"FAIL: Player {pid} has is_alive set to {p['is_alive']} instead of True!")
            sys.exit(1)

        # teams must be a list
        if not isinstance(p["teams"], list):
            print(f"FAIL: Player {pid} has teams set to {type(p['teams'])} instead of list!")
            sys.exit(1)

    print(f"PASS: Verified {len(pd)} players in player_directory structure.")

    # 7. Verify all combinations
    all_combs = views["all_combinations"]
    if not isinstance(all_combs, list):
        print("FAIL: all_combinations is not a list!")
        sys.exit(1)

    for i, pair in enumerate(all_combs):
        if len(pair) != 2:
            print(f"FAIL: Combination {i} is not a pair: {pair}!")
            sys.exit(1)

        id1, id2 = str(pair[0]), str(pair[1])
        if id1 not in pd or id2 not in pd:
            print(f"FAIL: Combination {i} contains unknown player ID: {pair}!")
            sys.exit(1)

        p1 = pd[id1]
        p2 = pd[id2]

        # Combined appearances must sum to 450
        sum_apps = p1["appearances"] + p2["appearances"]
        if sum_apps != 450:
            print(f"FAIL: Combination {i} ({p1['first_name']} {p1['last_name']} & {p2['first_name']} {p2['last_name']}) appearances sum to {sum_apps}, expected 450!")
            sys.exit(1)

    print(f"PASS: Verified {len(all_combs)} pairs in all_combinations. All pairs sum to 450.")

    # 8. Verify ranked_by_balance sorting
    ranked = views["ranked_by_balance"]
    if len(ranked) != len(all_combs):
        print(f"FAIL: ranked_by_balance length ({len(ranked)}) does not match all_combinations length ({len(all_combs)})!")
        sys.exit(1)

    last_diff = -1
    for i, pair in enumerate(ranked):
        p1 = pd[str(pair[0])]
        p2 = pd[str(pair[1])]
        diff = abs(p1["appearances"] - p2["appearances"])
        if diff < last_diff:
            print(f"FAIL: ranked_by_balance sorting violated at index {i}! Diff {diff} is less than previous diff {last_diff}!")
            sys.exit(1)
        last_diff = diff

    print("PASS: ranked_by_balance is correctly sorted in ascending order of appearance difference.")
    print("ALL VALIDATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
