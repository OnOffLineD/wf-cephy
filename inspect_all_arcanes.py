import json

with open("data/raw_wfcd/ko.json", "r", encoding="utf-8") as f:
    ko_data = json.load(f)

arcanes = {}
for k, v in ko_data.items():
    if k.startswith("/Lotus/Upgrades/CosmeticEnhancers/") and isinstance(v, dict):
        name_kr = v.get("name", "")
        desc_kr = v.get("description", "")
        if name_kr:
            arcanes[k] = (name_kr, desc_kr)

print(f"Total valid arcanes with names: {len(arcanes)}")
categories = set()
for k in arcanes.keys():
    parts = k.split('/')
    if len(parts) >= 5:
        categories.add(parts[4])
print("Arcane sub-categories:", categories)

for cat in sorted(categories):
    sample = [v[0] for k, v in arcanes.items() if f"/{cat}/" in k][:5]
    print(f"  {cat} ({len([k for k in arcanes.keys() if f'/{cat}/' in k])} items): {sample}")
