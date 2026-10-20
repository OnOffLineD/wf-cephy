from scripts.jamo_matcher import decompose_hangul
from scripts.wf_data_indexer import WFDataIndexer
from rapidfuzz import fuzz

idx = WFDataIndexer()

ocr_lines = [
    "스파이럴",
    "기럽트자지",
    "새크쳗피살레솋",
    "프끼임드리치",
    "불로우",
    "르건가터",
    "째크리피셜 스",
    "늘쏌들뮤"
]

def smart_match(ocr_lines, category="Melee"):
    candidates = []
    seen = set()
    for k, mod in idx.mods_index.items():
        name = mod.get('name')
        if not name or name in seen:
            continue
        m_type = str(mod.get('type', '')).lower()
        m_compat = str(mod.get('compatName', '')).lower()
        comb = f"{m_compat} {m_type}"
        if category and not any(c in comb for c in ['melee', 'stance', 'claw', 'sword', 'nikana', 'glaive', 'hammer', 'scythe', 'polearm', 'staff', 'dagger', 'dual', 'heavy']):
            continue
        seen.add(name)
        kr = mod.get('kr_name', '')
        if kr:
            candidates.append((decompose_hangul(kr.replace(' ', '')), kr, mod))
        candidates.append((decompose_hangul(name.lower().replace(' ', '')), name, mod))

    matches = {}
    for q in ocr_lines:
        q_jamo = decompose_hangul(q.replace(' ', ''))
        if len(q_jamo) < 5:
            continue
        for c_jamo, c_disp, mod in candidates:
            r = fuzz.ratio(q_jamo, c_jamo)
            pr = fuzz.partial_ratio(q_jamo, c_jamo)
            # Smart blended score
            score = max(r, pr * 0.9 if len(q_jamo) >= 6 else 0)
            if score >= 68.0:
                name = mod['name']
                if name not in matches or score > matches[name][0]:
                    matches[name] = (score, mod, q)

    return sorted(matches.values(), key=lambda x: x[0], reverse=True)

res = smart_match(ocr_lines)
print(f"Total matched ({len(res)}):")
for score, m, q in res[:10]:
    print(f"  [{score:.1f}%] {m.get('kr_name')} ({m.get('name')}) <- '{q}'")
