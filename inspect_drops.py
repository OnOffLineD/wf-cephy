import json

with open("data/raw_wfcd/drops_all.json", "r", encoding="utf-8") as f:
    drops = json.load(f)

print(f"Total drops: {len(drops)}")
items = set()
for d in drops:
    it = d.get('item', '')
    if any(k in it.lower() for k in ['arcane', 'primary', 'secondary', 'melee', 'shotgun', 'rifle', 'pistol']):
        items.add(it)

print(f"Candidate items in drops_all: {len(items)}")
sample = sorted(list(items))[:30]
for s in sample:
    print("  ", s)
