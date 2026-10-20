import json
import os

ko_path = "data/raw_wfcd/ko.json"
mods_path = "data/raw_wfcd/Mods.json"

with open(ko_path, "r", encoding="utf-8") as f:
    ko_data = json.load(f)

with open(mods_path, "r", encoding="utf-8") as f:
    mods_data = json.load(f)

print(f"Total keys in ko.json: {len(ko_data)}")
print(f"Total entries in Mods.json: {len(mods_data)}")

indexed_unique_names = set(m.get('uniqueName', '') for m in mods_data)
indexed_names = set(m.get('name', '').lower() for m in mods_data)

# Let's search ko.json for /Lotus/Upgrades/ (which are Warframe Mods, Arcanes, etc.)
upgrades_in_ko = {}
for k, v in ko_data.items():
    if k.startswith("/Lotus/Upgrades/"):
        name_kr = v.get("name") if isinstance(v, dict) else str(v)
        desc_kr = v.get("description", "") if isinstance(v, dict) else ""
        upgrades_in_ko[k] = (name_kr, desc_kr)

print(f"Total /Lotus/Upgrades/ in ko.json: {len(upgrades_in_ko)}")

# Check how many are NOT in Mods.json
missing_in_mods = {}
for k, (name_kr, desc_kr) in upgrades_in_ko.items():
    if k not in indexed_unique_names:
        missing_in_mods[k] = (name_kr, desc_kr)

print(f"Upgrades in ko.json NOT in Mods.json: {len(missing_in_mods)}")

# Sample missing upgrades
print("\n--- Sample missing upgrades ---")
samples = list(missing_in_mods.items())[:30]
for k, (n, d) in samples:
    print(f"  {k} -> KR: {n}")
