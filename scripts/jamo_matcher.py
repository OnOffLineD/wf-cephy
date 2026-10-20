import re
from typing import Dict, Any, Optional, List
from rapidfuzz import fuzz

CHOSUNG = ['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
JUNGSUNG = ['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
JONGSUNG = ['','ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

def decompose_hangul(text: str) -> str:
    result = []
    for c in text:
        if '가' <= c <= '힣':
            code = ord(c) - 0xAC00
            cho = code // 588
            jung = (code % 588) // 28
            jong = code % 28
            result.append(CHOSUNG[cho])
            result.append(JUNGSUNG[jung])
            if JONGSUNG[jong]:
                result.append(JONGSUNG[jong])
        else:
            result.append(c.lower())
    return ''.join(result)

CATEGORY_MAPPING = {
    'primary': ['rifle', 'shotgun', 'primary', 'bow', 'sniper'],
    'secondary': ['pistol', 'secondary'],
    'melee': ['melee', 'stance', 'whips', 'blade-whips', 'swords', 'nikana', 'fist', 'claws', 'hammer', 'heavy blade', 'polearm', 'glaive', 'scythe', 'staff', 'tonfa', 'warfan', 'nunchaku', 'gunblade', 'sparring', 'scythes', 'dagger', 'dual daggers', 'dual swords'],
    'warframe': ['warframe', 'aura', 'exilus']
}

def match_mods_jamo(ocr_text: str, mods_index: Dict[str, Any], category: Optional[str] = None, w_meta: Optional[Dict[str, Any]] = None, threshold: float = 75.0) -> List[Dict[str, Any]]:
    allowed = CATEGORY_MAPPING.get(category.lower(), []) if category else []
    w_type = (w_meta.get('type') or '').lower() if w_meta else ''
    
    candidates = []
    seen_unique = set()
    for k, mod in mods_index.items():
        name = mod.get('name')
        if not name or name in seen_unique:
            continue
        
        m_type = str(mod.get('type', '')).lower()
        m_compat = str(mod.get('compatName', '')).lower()
        
        # Stance mod weapon type compatibility check
        if 'stance' in m_type:
            if w_type and m_compat and (m_compat not in w_type and w_type not in m_compat):
                continue

        if allowed:
            is_compat = any(cat in m_type or cat in m_compat for cat in allowed)
            if not is_compat:
                if 'aura' in m_type or 'warframe' in m_type or 'companion' in m_type or 'archwing' in m_type or 'necramech' in m_type:
                    continue
                if 'arcane' in m_type or 'arcane' in m_compat:
                    is_compat = True
            if not is_compat:
                continue

        seen_unique.add(name)
        kr = mod.get('kr_name', '')
        if kr:
            candidates.append((decompose_hangul(kr.replace(' ', '')), kr, mod, True))
        candidates.append((decompose_hangul(name.lower().replace(' ', '')), name, mod, False))

    # Form queries from ocr_text: full lines, trimmed lines, combined lines, 2-token and 3-token phrases
    lines = [l.strip() for l in ocr_text.splitlines() if len(l.strip()) >= 2]
    combined_lines = [lines[i] + ' ' + lines[i+1] for i in range(len(lines) - 1)] if len(lines) >= 2 else []
    base_queries = lines + combined_lines
    
    queries = list(base_queries)
    for l in base_queries:
        if any(noise in l for noise in ['구성A', '구성B', '구성C', '고유 특성', '모두 표시', '수용량', '업그레이드', '기능']):
            continue
        tokens = [t for t in re.split(r'[,|:;`~•\s\(\)\[\]\/\\]+', l) if len(t) >= 2]
        for i in range(len(tokens) - 1):
            queries.append(tokens[i] + ' ' + tokens[i+1])
        if len(tokens) >= 3:
            for i in range(len(tokens) - 2):
                queries.append(tokens[i] + ' ' + tokens[i+1] + ' ' + tokens[i+2])
        for t in tokens:
            if len(t) >= 4:
                queries.append(t)
    queries = list(dict.fromkeys(queries))

    # Match tokens against candidates
    best_matches = {}
    for q in queries:
        q_clean = q.replace(' ', '')
        q_jamo = decompose_hangul(q_clean)
        if len(q_jamo) < 5:
            continue
            
        for cand_jamo, cand_display, mod, is_kr in candidates:
            max_len = max(len(cand_jamo), len(q_jamo))
            if abs(len(cand_jamo) - len(q_jamo)) > max_len * 0.52:
                continue
                
            ratio = fuzz.ratio(q_jamo, cand_jamo)
            partial_ratio = fuzz.partial_ratio(q_jamo, cand_jamo)
            score = max(ratio, partial_ratio * 0.92 if len(q_jamo) >= 6 else 0)
            
            if score >= 69.0:
                if any(p in cand_display.lower() for p in ['프라임드', 'primed', '갈바나이즈드', 'galvanized', '아말감', 'amalgam', '새크리피셜', 'sacrificial']):
                    score += 2.0
                name = mod['name']
                if name not in best_matches or score > best_matches[name][0]:
                    best_matches[name] = (score, mod, q)

    # Sort by score descending
    sorted_candidates = [m[1] for m in sorted(best_matches.values(), key=lambda x: x[0], reverse=True)]
    
    # Filter duplicate base variants when primed/sacrificial variant is present
    has_primed_reach = any('Primed Reach' in m['name'] for m in sorted_candidates)
    has_sac_pressure = any('Sacrificial Pressure' in m['name'] or 'Primed Pressure' in m['name'] for m in sorted_candidates)
    has_sac_steel = any('Sacrificial Steel' in m['name'] for m in sorted_candidates)
    
    final_mods = []
    for m in sorted_candidates:
        m_name = m['name']
        if has_primed_reach and m_name == 'Reach':
            continue
        if has_sac_pressure and m_name == 'Pressure Point':
            continue
        if has_sac_steel and m_name == 'True Steel':
            continue
        final_mods.append(m)

    return final_mods[:9]

