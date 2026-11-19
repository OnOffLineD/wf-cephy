# scripts/damage_formulas.py

import math
from typing import Any, Dict, Optional

DAMAGING_STATUS_TYPES = ('slash', 'heat', 'toxin', 'electric', 'gas', 'blast')

# (tick_coeff, tick_count, elemental_mod_key):
# - Slash: 0.35x modded base, 6 ticks over 6s (ignores elemental/+slash mods).
# - Heat: 0.50x modded base * (1 + heat_mod), 6 ticks over 6s.
# - Toxin: 0.50x modded base * (1 + toxin_mod), 6 ticks over 6s.
# - Electric: 0.50x modded base * (1 + electric_mod), 7 ticks (0s + 1s..6s).
# - Gas: 0.50x modded base, 7 ticks (0s + 1s..6s; ignores elemental mods, capped at 10 stacks).
# - Blast (U36): 0.30x modded base single-target detonation (1 tick; ignores elemental mods).
STATUS_DOT_SPECS = {
    'slash': (0.35, 6, None),
    'heat': (0.50, 6, 'heat'),
    'toxin': (0.50, 6, 'toxin'),
    'electric': (0.50, 7, 'electric'),
    'gas': (0.50, 7, None),
    'blast': (0.30, 1, None),
}
# Steady-state active stack caps (Gas caps at 10 stacks -> max 10 ticks/sec).
STATUS_STACK_CAPS = {
    'gas': 10,
}
_STATUS_ALIASES = {'bleed': 'slash', 'electricity': 'electric'}


def _normalize_status_type(status_type: str) -> str:
    key = str(status_type or '').strip().lower()
    return _STATUS_ALIASES.get(key, key)


def enemy_armor_dr(armor: float) -> float:
    """Calculate post-Update 36 (Jade Shadows) enemy armor damage reduction (cap 2,700 -> 90% DR)."""
    a = max(0.0, float(armor))
    if a <= 0.0:
        return 0.0
    return 0.9 * math.sqrt(min(a, 2700.0) / 2700.0)


def total_crit_chance(base: float, relative: float = 0.0, flat: float = 0.0, combo_bonus: float = 0.0, combo_mult: float = 1.0) -> float:
    """Calculate the total critical hit chance."""
    return base * (1.0 + relative + combo_bonus * (combo_mult - 1.0)) + flat


def total_crit_mult(base: float, relative: float = 0.0, flat: float = 0.0) -> float:
    """Calculate the total critical hit multiplier."""
    return base * (1.0 + relative) + flat


def average_crit_mult(crit_chance: float, crit_mult: float, vigilante_chance: float = 0.0) -> float:
    """Calculate the average critical hit multiplier, optionally including Vigilante tier-upgrade chance."""
    cc = max(0.0, float(crit_chance))
    cm = max(1.0, float(crit_mult))
    vig = min(0.30, max(0.0, float(vigilante_chance or 0.0)))
    effective_tier = cc + min(1.0, cc) * vig
    return 1.0 + effective_tier * (cm - 1.0)


def hm_crit_avg(crit_chance: float, crit_mult: float, vigilante_chance: float = 0.0) -> float:
    """Conditional expected crit multiplier given a critical hit occurred (e.g. Hunter Munitions)."""
    cc = max(0.0, float(crit_chance))
    cm = max(1.0, float(crit_mult))
    vig = min(0.30, max(0.0, float(vigilante_chance or 0.0)))
    if cc <= 0.0:
        return 1.0
    if cc < 1.0:
        return 1.0 + (1.0 + vig) * (cm - 1.0)
    return average_crit_mult(cc, cm, vigilante_chance=vig)


def headcrit_avg_mult(crit_chance: float, crit_mult: float, vigilante_chance: float = 0.0) -> float:
    """Average crit multiplier on a weak point: crits there deal an extra 2x, non-crits do not."""
    cc = max(0.0, float(crit_chance))
    return 2.0 * average_crit_mult(cc, crit_mult, vigilante_chance=vigilante_chance) - max(0.0, 1.0 - cc)


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


def effective_fire_rate(fire_rate: float, charge_time: float = 0.0, *, is_bow_charge: bool = False) -> float:
    """Calculate effective fire rate.

    For charge-per-shot bows (is_bow_charge=True), burst cadence is 1/charge_time so that
    shooting_proportion(..., reload_time) yields 1/(charge_time + reload_time) without double-counting 1/fire_rate.
    """
    fr = max(0.0, float(fire_rate or 0.0))
    ct = max(0.0, float(charge_time or 0.0))
    if ct > 0.0:
        if is_bow_charge or fr <= 0.0:
            return 1.0 / ct
        return 1.0 / (ct + 1.0 / fr)
    return fr


def shooting_proportion(shots_per_mag: float, effective_rate: float, reload_time: float) -> float:
    """Calculate the shooting proportion (handles magazine=0/infinite and zero reload safely)."""
    efr = float(effective_rate or 0.0)
    rel = float(reload_time or 0.0)
    if rel <= 0.0 or efr <= 0.0:
        return 1.0
    mag = float(shots_per_mag or 0.0)
    if mag <= 0.0:
        # Bows such as Nataruk report magazineSize=0 with a non-zero arrow draw/reload time.
        mag = 1.0
    return mag / (efr * rel + mag)


def status_tick_damage(
    status_type: str,
    modded_base: float,
    faction: float = 0.0,
    status_damage: float = 0.0,
    crit_avg: float = 1.0,
    element_bonus: float = 0.0,
) -> float:
    """Calculate single-tick (or Blast detonation) damage for a damaging status effect."""
    spec = STATUS_DOT_SPECS.get(_normalize_status_type(status_type))
    if not spec or modded_base <= 0:
        return 0.0
    coeff, _, elem_key = spec
    elem_mult = max(0.0, 1.0 + element_bonus) if elem_key else 1.0
    return modded_base * coeff * elem_mult * (1.0 + faction) ** 2 * (1.0 + status_damage) * crit_avg


def status_proc_total_damage(
    status_type: str,
    modded_base: float,
    faction: float = 0.0,
    status_damage: float = 0.0,
    crit_avg: float = 1.0,
    element_bonus: float = 0.0,
) -> float:
    """Calculate total lifetime damage of a single status proc across all its ticks."""
    spec = STATUS_DOT_SPECS.get(_normalize_status_type(status_type))
    if not spec or modded_base <= 0:
        return 0.0
    _, ticks, _ = spec
    return status_tick_damage(
        status_type,
        modded_base,
        faction=faction,
        status_damage=status_damage,
        crit_avg=crit_avg,
        element_bonus=element_bonus,
    ) * ticks


def bleed_tick(modded_base: float, faction: float = 0.0, status_damage: float = 0.0, crit_avg: float = 1.0) -> float:
    """Calculate the bleed tick damage."""
    return status_tick_damage('slash', modded_base, faction=faction, status_damage=status_damage, crit_avg=crit_avg)


def status_dot_dps(
    modded_base: float,
    shares: Optional[Dict[str, float]],
    status_chance: float,
    multishot: float,
    effective_rate: float,
    *,
    faction: float = 0.0,
    status_damage: float = 0.0,
    crit_avg: float = 1.0,
    element_bonuses: Optional[Dict[str, float]] = None,
    forced_procs_per_pellet: Optional[Dict[str, float]] = None,
    forced_crit_procs_per_pellet: Optional[Dict[str, float]] = None,
    forced_crit_avg: Optional[float] = None,
    is_beam: bool = False,
    beam_ms_scale: float = 1.0,
) -> Dict[str, Any]:
    """Calculate steady-state status DoT DPS and per-status breakdown at burst fire rate.

    - Caps Gas at 10 active stacks (max 10 ticks/sec).
    - On Beam weapons (`is_beam=True`), multishot scales tick base damage by `beam_ms_scale`
      as well as status proc rate (`multishot`), capturing beam multishot² DoT double-dipping
      while keeping crit-forced procs (e.g. Hunter Munitions) at 1 roll per beam.
    - `forced_crit_procs_per_pellet` (e.g. Hunter Munitions) uses `forced_crit_avg` (conditional
      crit multiplier given a crit occurred) instead of unconditional `crit_avg`.
    """
    if modded_base <= 0 or multishot <= 0 or effective_rate <= 0:
        return {'total_dps': 0.0, 'breakdown': {}, 'forced_crit_dps': 0.0}

    norm_shares: Dict[str, float] = {}
    for k, v in (shares or {}).items():
        nk = _normalize_status_type(k)
        norm_shares[nk] = norm_shares.get(nk, 0.0) + max(0.0, float(v or 0.0))

    norm_forced: Dict[str, float] = {}
    for k, v in (forced_procs_per_pellet or {}).items():
        nk = _normalize_status_type(k)
        norm_forced[nk] = norm_forced.get(nk, 0.0) + max(0.0, float(v or 0.0))

    norm_forced_crit: Dict[str, float] = {}
    for k, v in (forced_crit_procs_per_pellet or {}).items():
        nk = _normalize_status_type(k)
        norm_forced_crit[nk] = norm_forced_crit.get(nk, 0.0) + max(0.0, float(v or 0.0))

    bonuses = {_normalize_status_type(k): float(v or 0.0) for k, v in (element_bonuses or {}).items()}
    sc = max(0.0, float(status_chance or 0.0))

    beam_scale = max(1.0, float(beam_ms_scale or 1.0)) if is_beam else 1.0
    effective_base = modded_base * beam_scale
    hm_crit = crit_avg if forced_crit_avg is None else float(forced_crit_avg)
    # On beams, multishot merges into each beam tick rather than creating extra crit rolls for HM.
    forced_crit_ms = (multishot / beam_scale) if is_beam else multishot

    breakdown: Dict[str, float] = {}
    forced_crit_total_dps = 0.0
    for st in DAMAGING_STATUS_TYPES:
        nat_procs = sc * norm_shares.get(st, 0.0) + norm_forced.get(st, 0.0)
        crit_procs = norm_forced_crit.get(st, 0.0)
        if nat_procs <= 0 and crit_procs <= 0:
            continue
        eb = bonuses.get(st, 0.0)
        dps = 0.0
        if nat_procs > 0:
            proc_total = status_proc_total_damage(
                st,
                effective_base,
                faction=faction,
                status_damage=status_damage,
                crit_avg=crit_avg,
                element_bonus=eb,
            )
            dps += nat_procs * multishot * effective_rate * proc_total
        if crit_procs > 0:
            crit_proc_total = status_proc_total_damage(
                st,
                effective_base,
                faction=faction,
                status_damage=status_damage,
                crit_avg=hm_crit,
                element_bonus=eb,
            )
            fc_dps = crit_procs * forced_crit_ms * effective_rate * crit_proc_total
            dps += fc_dps
            forced_crit_total_dps += fc_dps

        stack_cap = STATUS_STACK_CAPS.get(st)
        if stack_cap and dps > 0:
            cap_tick = status_tick_damage(
                st,
                effective_base,
                faction=faction,
                status_damage=status_damage,
                crit_avg=crit_avg,
                element_bonus=eb,
            )
            dps = min(dps, float(stack_cap) * cap_tick)

        if dps > 0:
            breakdown[st] = dps

    return {
        'total_dps': sum(breakdown.values()),
        'breakdown': breakdown,
        'forced_crit_dps': forced_crit_total_dps,
    }

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

