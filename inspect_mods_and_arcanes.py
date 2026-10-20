import json

with open("data/raw_wfcd/ko.json", "r", encoding="utf-8") as f:
    ko_data = json.load(f)

with open("data/raw_wfcd/Mods.json", "r", encoding="utf-8") as f:
    mods_data = json.load(f)

indexed_unique = set(m.get('uniqueName', '') for m in mods_data)

mods_in_ko = {}
arcanes_in_ko = {}
for k, v in ko_data.items():
    if not isinstance(v, dict):
        continue
    name_kr = v.get("name", "")
    desc_kr = v.get("description", "")
    if k.startswith("/Lotus/Upgrades/Mods/"):
        mods_in_ko[k] = (name_kr, desc_kr)
    elif k.startswith("/Lotus/Upgrades/CosmeticEnhancers/"):
        arcanes_in_ko[k] = (name_kr, desc_kr)

print(f"Total /Lotus/Upgrades/Mods/ in ko.json: {len(mods_in_ko)}")
print(f"Total /Lotus/Upgrades/CosmeticEnhancers/ in ko.json: {len(arcanes_in_ko)}")

missing_mods = {k: v for k, v in mods_in_ko.items() if k not in indexed_unique}
print(f"Mods in ko.json but NOT in Mods.json: {len(missing_mods)}")

print("\n--- Sample missing mods from ko.json ---")
for k, (n, d) in list(missing_mods.items())[:20]:
    print(f"  {k} -> {n}")

print("\n--- Sample Arcanes from ko.json ---")
for k, (n, d) in list(arcanes_in_ko.items())[:20]:
    print(f"  {k} -> {n}")
