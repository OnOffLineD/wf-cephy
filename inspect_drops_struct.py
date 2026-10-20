import json

with open("data/raw_wfcd/drops_all.json", "r", encoding="utf-8") as f:
    drops = json.load(f)

if isinstance(drops, dict):
    print("Dict keys:", list(drops.keys())[:10])
    for k in list(drops.keys())[:3]:
        print(f"Sample under '{k}':", str(drops[k])[:200])
elif isinstance(drops, list):
    print("List len:", len(drops))
    print("Sample items:", drops[:3])
