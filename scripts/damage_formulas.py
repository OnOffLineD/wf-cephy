# scripts/damage_formulas.py

from typing import Dict, Optional

def enemy_armor_dr(armor: float) -> float:
    """Calculate the enemy armor damage reduction."""
    a = max(0.0, armor)
    if a <= 2700.0:
        return 0.9 * a / 2700.0
    return a / (a + 300.0)

def total_crit_chance(base: float, relative: float = 0.0, flat: float = 0.0, combo_bonus: float = 0.0, combo_mult: float = 1.0) -> float:
    """Calculate the total critical hit chance."""
    return base * (1.0 + relative + combo_bonus * (combo_mult - 1.0)) + flat

def total_crit_mult(base: float, relative: float = 0.0, flat: float = 0.0) -> float:
    """Calculate the total critical hit multiplier."""
    return base * (1.0 + relative) + flat

def average_crit_mult(crit_chance: float, crit_mult: float) -> float:
    """Calculate the average critical hit multiplier."""
    return 1.0 + crit_chance * (crit_mult - 1.0)

def weak_point_multiplier(base: float = 3.0, wp_bonus: float = 0.0, headshot_bonus: float = 0.0, is_headshot: bool = True) -> float:
    """Calculate the weak point multiplier."""
    if is_headshot:
        return (base + 1.5 * wp_bonus) * (1.0 + headshot_bonus)
    else:
        return base + wp_bonus

def arsenal_total(base_damage: float, distribution: Dict[str, float], elemental: float = 0.0, physical: Optional[Dict[str, float]] = None, damage: float = 0.0, multishot: float = 1.0) -> float:
    """Calculate the total damage from arsenal."""
    total_dist = sum(distribution.values()) or 1.0
    phys = sum((distribution.get(k, 0.0) / total_dist) * v for k, v in (physical or dict()).items())
    return base_damage * (1.0 + elemental + phys) * (1.0 + damage) * multishot

def effective_fire_rate(fire_rate: float, charge_time: float = 0.0) -> float:
    """Calculate the effective fire rate."""
    if charge_time > 0:
        return 1.0 / (charge_time + 1.0 / fire_rate)
    return fire_rate

def shooting_proportion(shots_per_mag: float, effective_rate: float, reload_time: float) -> float:
    """Calculate the shooting proportion."""
    return shots_per_mag / (effective_rate * reload_time + shots_per_mag)

def bleed_tick(modded_base: float, faction: float = 0.0, status_damage: float = 0.0, crit_avg: float = 1.0) -> float:
    """Calculate the bleed tick damage."""
    return modded_base * 0.35 * (1.0 + faction) ** 2 * (1.0 + status_damage) * crit_avg

def combine_elements(mod_elements, innate=None):
    PRIMARY_ELEMENTS = ('heat', 'cold', 'electric', 'toxin')
    ELEMENT_COMBINATIONS = {
        frozenset(('cold', 'heat')): 'blast',
        frozenset(('electric', 'heat')): 'radiation',
        frozenset(('heat', 'toxin')): 'gas',
        frozenset(('cold', 'electric')): 'magnetic',
        frozenset(('cold', 'toxin')): 'viral',
        frozenset(('electric', 'toxin')): 'corrosive'
    }

    order = []
    primary = {}
    secondary = {}

    for el, val in mod_elements:
        if el in PRIMARY_ELEMENTS:
            if el not in order:
                order.append(el)
            primary[el] = primary.get(el, 0.0) + val
        else:
            secondary[el] = secondary.get(el, 0.0) + val

    if innate:
        for el, val in innate.items():
            if el not in PRIMARY_ELEMENTS:
                secondary[el] = secondary.get(el, 0.0) + val

        for el in PRIMARY_ELEMENTS:
            if el in innate:
                if el not in order:
                    order.append(el)
                primary[el] = primary.get(el, 0.0) + innate[el]

    types = dict(secondary)
    pairs = []
    i = 0

    while i + 1 < len(order):
        a, b = order[i], order[i + 1]
        name = ELEMENT_COMBINATIONS[frozenset((a, b))]
        types[name] = types.get(name, 0.0) + primary[a] + primary[b]
        pairs.append((a, b, name))
        i += 2

    if i < len(order):
        leftover = order[i]
        types[leftover] = types.get(leftover, 0.0) + primary[leftover]

    return dict(types=types, pairs=pairs, order=order)

FACTION_MODIFIERS = {
    'grineer': {'impact': 1.5, 'corrosive': 1.5},
    'corpus': {'puncture': 1.5, 'magnetic': 1.5},
    'infested': {'slash': 1.5, 'heat': 1.5},
    'orokin': {'puncture': 1.5, 'viral': 1.5, 'radiation': 0.5},
    'sentient': {'cold': 1.5, 'radiation': 1.5, 'corrosive': 0.5},
    'narmer': {'slash': 1.5, 'toxin': 1.5, 'magnetic': 0.5},
    'murmur': {'electric': 1.5, 'radiation': 1.5, 'viral': 0.5}
}

def faction_multipliers(types: Dict[str, float], faction_bonus: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    total = sum(types.values())
    if total <= 0:
        return {}

    result = {}
    for faction, table in FACTION_MODIFIERS.items():
        faction_total = sum(d * table.get(t, 1.0) for t, d in types.items())
        faction_multiplier = faction_total / total * (1.0 + (faction_bonus or dict()).get(faction, 0.0))
        result[faction] = faction_multiplier

    return result

