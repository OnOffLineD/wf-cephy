from scripts.jamo_matcher import match_mods_jamo, decompose_hangul
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

targets = [
    ("리핑 스파이럴", "스파이럴"),
    ("커럽트 차지", "기럽트자지"),
    ("새크리피셜 프레셔", "새크쳗피살레솋"),
    ("프라임드 리치", "프끼임드리치"),
    ("킬링 블로우", "불로우"),
    ("오르건 섀터", "르건가터"),
    ("새크리피셜 스틸", "째크리피셜 스"),
]

for kr_name, ocr in targets:
    mod = idx.mods_index.get(kr_name)
    c_jamo = decompose_hangul(kr_name.replace(' ', ''))
    q_jamo = decompose_hangul(ocr.replace(' ', ''))
    r = fuzz.ratio(q_jamo, c_jamo)
    pr = fuzz.partial_ratio(q_jamo, c_jamo)
    print(f"[{kr_name}] vs [{ocr}]: ratio={r:.1f}, partial={pr:.1f}")

matched = match_mods_jamo("\n".join(ocr_lines), idx.mods_index, category="Melee")
print("\nMatched by match_mods_jamo:")
for m in matched:
    print(" ", m.get('kr_name'), m.get('name'))
