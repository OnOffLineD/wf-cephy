"""Weapon innate traits that change how mods work, which the official data only describes in prose.

Each weapon's numbers live in data/innate_traits.json with the wiki page they came from.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from scripts.path_config import get_path

PHYSICAL = ('impact', 'puncture', 'slash')
RIVEN = 'Riven Mod'
INNATE_MOD = 'Innate Trait'

# Kuva, Tenet and Coda weapons carry a Valence Bonus of one of these types, capped at 60%.
# The player can change it (Valence Fusion), so the arsenal panel or the player is the only source.
ADVERSARY_PREFIXES = ('kuva ', 'tenet ', 'coda ')
BONUS_ELEMENTS = {
    'impact': '충격', 'heat': '화염', 'cold': '냉기', 'electric': '전기',
    'toxin': '독성', 'magnetic': '자성', 'radiation': '방사능',
}
BONUS_MIN, BONUS_MAX = 0.25, 0.60
_ELEMENT_WORDS = (
    (r'충격|impact', 'impact'), (r'화염|불|열기|heat|fire', 'heat'), (r'냉기|얼음|cold|ice', 'cold'),
    (r'전기|전격|electric(?:ity)?', 'electric'), (r'독성|독|toxin', 'toxin'), (r'자성|자기|magnetic', 'magnetic'),
    (r'방사능|radiation', 'radiation'),
)
_FILLER = r'(?:보너스|속성|원소|베일런스|valence|bonus|은|는|이|가|에|로|으로|이야|입니다|이에요|예요|임|요|[,.!~\s])*'
BONUS_ANSWER = re.compile(
    rf'^\s*{_FILLER}(?P<el>{"|".join(p for p, _ in _ELEMENT_WORDS)}){_FILLER}(?:(?P<pct>\d+(?:\.\d+)?)\s*(?:%|퍼센트|퍼)?)?{_FILLER}$',
    re.I,
)

_traits: Optional[Dict[str, Dict[str, Any]]] = None


def load_traits() -> Dict[str, Dict[str, Any]]:
    global _traits
    if _traits is None:
        try:
            with open(get_path('data', 'innate_traits.json'), encoding='utf-8') as f:
                _traits = {k.lower(): v for k, v in json.load(f).items()}
        except (OSError, ValueError):
            _traits = {}
    return _traits


def trait_for(w_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return load_traits().get(str(w_meta.get('name', '')).lower())


def apply_innate_traits(w_meta: Dict[str, Any], mods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Returns the mods as the weapon actually applies them.

    Physical mod values are scaled by the weapon's multiplier, and the wheel buff the build selects is
    added as one extra entry so it joins the same additive buckets as mods. Safe to call twice.
    """
    trait = trait_for(w_meta)
    if not trait or any(m.get('_innate_applied') for m in mods):
        return mods

    mult = float(trait.get('physical_mod_multiplier') or 1.0)
    out = []
    totals = dict.fromkeys(PHYSICAL, 0.0)
    for m in mods:
        c = dict(m)
        c['_innate_applied'] = True
        if c.get('name') != RIVEN:
            for k in PHYSICAL:
                if c.get(k):
                    totals[k] += c[k]
                    c[k] = c[k] * mult
        out.append(c)

    buff = selected_wheel(trait, totals)
    if buff:
        out.append({'name': INNATE_MOD, 'kr_name': buff.get('label', ''), '_innate_applied': True,
                    **{k: v for k, v in buff.items() if k != 'label'}})
    return out


def selected_wheel(trait: Dict[str, Any], totals: Dict[str, float]) -> Optional[Dict[str, Any]]:
    wheel = trait.get('wheel') or {}
    best = max(PHYSICAL, key=lambda k: totals.get(k, 0.0))
    if totals.get(best, 0.0) <= 0:
        return None
    return wheel.get(best)


def is_adversary(w_meta: Dict[str, Any]) -> bool:
    return str(w_meta.get('name', '')).lower().startswith(ADVERSARY_PREFIXES)


def bonus_in(stats: Optional[Dict[str, float]]) -> Optional[Tuple[str, float]]:
    """The Valence Bonus already in the panel stats, as (type, fraction)."""
    for k, v in (stats or {}).items():
        if k.startswith('valence_'):
            return k[len('valence_'):], float(v)
    return None


def set_bonus(stats: Dict[str, float], element: str, fraction: float) -> None:
    """Replaces the Valence Bonus in place, so every holder of these stats sees the new one."""
    for k in [k for k in stats if k.startswith('valence_')]:
        del stats[k]
    stats['valence_' + element] = fraction


def parse_bonus_answer(text: str) -> Optional[Tuple[str, Optional[float]]]:
    """Reads a short answer like "자성 45" or "전기 60%".

    Only a message that is nothing but a type and a number counts, so "화염 약점 뭐야?" is left alone.
    The percentage is None when the player gave only the type, and is not range-checked here.
    """
    m = BONUS_ANSWER.match(text or '')
    if not m:
        return None
    word = m.group('el')
    element = next(el for pattern, el in _ELEMENT_WORDS if re.fullmatch(pattern, word, re.I))
    pct = m.group('pct')
    if pct is None:
        return element, None
    value = float(pct)
    return element, value / 100.0 if value > 1.0 else value


def describe(w_meta: Dict[str, Any], mods: List[Dict[str, Any]], stats: Optional[Dict[str, float]] = None) -> List[str]:
    """Report lines for the weapon's traits, or [] for a weapon without any."""
    lines = []
    trait = trait_for(w_meta)
    if trait:
        mult = float(trait.get('physical_mod_multiplier') or 1.0)
        if mult != 1.0:
            lines.append(f"물리(충격·관통·베기) 모드 효과 {mult:g}배 적용")
        if trait.get('wheel'):
            wheel = next((m for m in mods if m.get('name') == INNATE_MOD and m.get('kr_name')), None)
            lines.append(wheel['kr_name'] if wheel else "휠 버프 없음 (물리 모드 미장착)")
        lines.extend(trait.get('notes') or [])
    if is_adversary(w_meta):
        bonus = bonus_in(stats)
        if bonus:
            lines.append(f"보너스 속성: {BONUS_ELEMENTS.get(bonus[0], bonus[0])} {bonus[1] * 100:g}%")
        else:
            lines.append("보너스 속성: 확인 안 됨 (계산에 반영하지 않음)")
    return lines
