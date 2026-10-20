import json

with open("data/raw_wfcd/Mods.json", "r", encoding="utf-8") as f:
    mods = json.load(f)

types = {}
for m in mods:
    t = m.get('type', 'Unknown')
    types[t] = types.get(t, 0) + 1

for t, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {t}: {count}")
