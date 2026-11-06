"""Weapon innate traits that change how mods work, which the official data only describes in prose.

Each weapon's numbers live in data/innate_traits.json with the wiki page they came from.
"""
import json
from typing import Any, Dict, List, Optional

from scripts.path_config import get_path

PHYSICAL = ('impact', 'puncture', 'slash')
RIVEN = 'Riven Mod'
INNATE_MOD = 'Innate Trait'

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


def describe(w_meta: Dict[str, Any], mods: List[Dict[str, Any]]) -> List[str]:
    """Report lines for the weapon's trait, or [] for a weapon without one."""
    trait = trait_for(w_meta)
    if not trait:
        return []
    lines = []
    mult = float(trait.get('physical_mod_multiplier') or 1.0)
    if mult != 1.0:
        lines.append(f"물리(충격·관통·베기) 모드 효과 {mult:g}배 적용")
    wheel = next((m for m in mods if m.get('name') == INNATE_MOD and m.get('kr_name')), None)
    lines.append(wheel['kr_name'] if wheel else "휠 버프 없음 (물리 모드 미장착)")
    return lines
