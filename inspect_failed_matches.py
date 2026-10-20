import json
from scripts.wf_data_indexer import WFDataIndexer

idx = WFDataIndexer()

# 1. Dark Split-Sword investigation
print("--- 1. Dark Split-Sword ---")
for k, v in idx.weapons_index.items():
    if "다크" in k or "dark" in k or "스플릿" in k:
        print(f"  Key in weapons_index: '{k}' -> {v.get('name')}")

test_header = "업그레이드: 다크 스플릿-소드 랭크 30"
m = idx.fuzzy_match_weapon(test_header)
print(f"  fuzzy_match_weapon('{test_header}') -> {m.get('name') if m else None}")

# 2. Mods investigation in Reaper Prime and Nami Skyla Prime
print("\n--- 2. Mods investigation ---")
test_mods = ["새크리피셜 프레셔", "킬링 블로우", "비셔스 프로스트", "리핑 스파이럴", "볼래틸 퀵 리턴"]
for tm in test_mods:
    m = idx.match_mod(tm, category="Melee")
    print(f"  match_mod('{tm}') -> {m.get('name') if m else 'NONE'} (kr: {m.get('kr_name') if m else 'NONE'})")
