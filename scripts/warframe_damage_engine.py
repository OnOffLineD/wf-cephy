import math
import re
from typing import Dict, Any, Optional, List, Tuple

import scripts.innate_traits as _innate_mod
from scripts.innate_traits import apply_innate_traits, describe as describe_innate

_ALL_ELEMENTS = ('heat', 'cold', 'electric', 'toxin', 'blast', 'radiation', 'gas', 'magnetic', 'viral', 'corrosive')
_PHYS = ('impact', 'puncture', 'slash')
_EPS = 1e-6

# Rifle fire-rate mods that double their bonus on Bows (fallback when indexer field is absent).
_BOW_2X_FR_MODS = {'vile acceleration', 'shred', 'primed shred', 'speed trigger'}

_MELEE_CLASSES = {
    'melee', 'claws', 'daggers', 'dual daggers', 'dual swords', 'dual nikanas', 'fists', 'glaives', 'gunblade',
    'hammers', 'heavy blade', 'heavy scythe', 'machetes', 'nikanas', 'nunchaku', 'polearms', 'rapiers', 'scythes',
    'sparring', 'staves', 'sword and shield', 'swords', 'tonfas', 'two-handed nikana', 'warfans', 'whips',
    'blade and whip', 'assault saw', 'bayonet', 'thrown melee'
}
# Generic compatName -> (allowed weapon categories, allowed weapon types or None for any type).
_GENERIC_COMPAT = {
    **{c: ({'melee'}, None) for c in _MELEE_CLASSES},
    'primary': ({'primary'}, None),
    'unique': ({'primary'}, None),
    'rifle': ({'primary'}, {'rifle', 'sniper', 'bow', 'launcher', 'pistol', ''}),
    'rifle (no aoe)': ({'primary'}, {'rifle', 'sniper', 'bow', 'pistol', ''}),
    'assault rifle': ({'primary'}, {'rifle', ''}),
    'sniper': ({'primary'}, {'sniper', ''}),
    'bow': ({'primary'}, {'bow', ''}),
    'shotgun': ({'primary'}, {'shotgun', ''}),
    'secondary': ({'secondary'}, None),
    'pistol': ({'secondary'}, None),
    'pistol (no aoe)': ({'secondary'}, None),
    'thrown': ({'secondary'}, {'throwing', ''}),
    'tome': ({'secondary'}, None),
    'archgun': ({'arch-gun'}, None),
    'archmelee': ({'arch-melee'}, None),
}
_DUAL_RE = re.compile(r'\b(?:dual|twin)\b|\bak[^aeiou\W]', re.IGNORECASE)


def _tier_min(x: float) -> int:
    return max(0, int(math.floor(float(x) + _EPS)))


def _tier_max(x: float) -> int:
    return max(0, int(math.ceil(float(x) - _EPS)))


def _norm_dist(raw: Any) -> Dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in raw.items():
        val = float(v or 0.0)
        if val <= 0.0:
            continue
        nk = 'electric' if str(k).strip().lower() == 'electricity' else str(k).strip().lower()
        out[nk] = out.get(nk, 0.0) + val
    return out


def _is_aoe_attack(attack: Dict[str, Any]) -> bool:
    name_l = str(attack.get('name', '')).lower()
    shot_l = str(attack.get('shot_type', '')).lower()
    return (
        shot_l == 'aoe'
        or 'radial' in name_l
        or 'explosion' in name_l
        or 'blast' in name_l
        or 'cloud' in name_l
    )


def _iter_conditional(mod: Dict[str, Any], key: str) -> List[Tuple[str, float]]:
    """Yield (stat, total_bonus) from a mod's conditional field (list of dicts or flat dict)."""
    raw = mod.get(key)
    if not raw:
        return []
    out: List[Tuple[str, float]] = []
    if isinstance(raw, list):
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            stat = str(entry.get('stat') or '').strip().lower()
            if not stat:
                continue
            val = float(entry.get('value') or 0.0) * float(entry.get('stacks') or 1.0)
            out.append((stat, val))
    elif isinstance(raw, dict):
        for stat, val in raw.items():
            if isinstance(val, (int, float)):
                out.append((str(stat).strip().lower(), float(val)))
    return out


class WarframeDamageEngine:
    @staticmethod
    def _is_beam(w_meta: Dict[str, Any]) -> bool:
        if w_meta.get('is_beam'):
            return True
        if str(w_meta.get('trigger') or '').strip().lower() == 'held':
            return True
        attacks = w_meta.get('attacks') or []
        if attacks and isinstance(attacks[0], dict):
            st = str(attacks[0].get('shot_type') or '').strip().lower()
            if st in ('beam', 'continuous'):
                return True
        return False

    @staticmethod
    def _is_bow(w_meta: Dict[str, Any]) -> bool:
        return str(w_meta.get('type') or '').strip().lower() == 'bow'

    @staticmethod
    def _get_trait(w_meta: Dict[str, Any]) -> Dict[str, Any]:
        fn = getattr(_innate_mod, 'trait_for', None)
        if callable(fn):
            try:
                return fn(w_meta) or {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _get_incarnon_data(w_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        fn = getattr(_innate_mod, 'get_incarnon_data', None)
        if callable(fn):
            try:
                res = fn(str(w_meta.get('name') or ''))
                return res if isinstance(res, dict) else None
            except Exception:
                return None
        return None

    def is_mod_compatible(self, w_meta: Dict[str, Any], mod: Dict[str, Any]) -> bool:
        """Whether the mod can go on this weapon: category for generic mods, weapon family for exclusive ones."""
        compat = str(mod.get('compatName') or '').strip().lower()
        if not compat or compat == 'any' or mod.get('name') == 'Riven Mod':
            return True
        category = str(w_meta.get('category') or '').strip().lower()
        w_type = str(w_meta.get('type') or '').strip().lower()
        if compat in _GENERIC_COMPAT:
            if category not in {'primary', 'secondary', 'melee', 'arch-gun', 'arch-melee'}:
                return True
            categories, types = _GENERIC_COMPAT[compat]
            return category in categories and (types is None or w_type in types)
        name = str(w_meta.get('name') or '').strip()
        if not name:
            return True
        # 'Skana' mods don't fit 'Dual Skana', but 'Dual Cleavers' mods fit 'Prisma Dual Cleavers'.
        if bool(_DUAL_RE.search(name)) != bool(_DUAL_RE.search(compat)):
            return False
        return re.search(r'\b' + re.escape(compat) + r'\b', name, re.IGNORECASE) is not None

    def _prepare_mods(self, w_meta: Dict[str, Any], mods: List[Dict[str, Any]], keep_incompatible: bool = False) -> List[Dict[str, Any]]:
        """Mods as the weapon applies them: set bonuses first, then the weapon's innate trait.

        Mods exclusive to another weapon are dropped, or appended unapplied with _compatible False if kept.
        """
        flagged = [dict(m, _compatible=self.is_mod_compatible(w_meta, m)) for m in mods]
        prepared = apply_innate_traits(w_meta, self._apply_mod_sets([m for m in flagged if m['_compatible']]))
        if keep_incompatible:
            prepared = prepared + [m for m in flagged if not m['_compatible']]
        return prepared

    def _magazine_and_reload(self, w_meta: Dict[str, Any], mods: List[Dict[str, Any]], rv: Dict[str, float]) -> Tuple[float, float]:
        raw_mag = w_meta.get('magazineSize')
        raw_reload = w_meta.get('reloadTime')
        base_reload = 2.0 if raw_reload is None else max(0.0, float(raw_reload))
        if raw_mag is None:
            base_mag = 30.0
        elif float(raw_mag) <= 0.0:
            # Single-shot bows like Nataruk report magazineSize=0 with a non-zero arrow draw/reload time.
            base_mag = 1.0 if base_reload > 0.0 else 0.0
        else:
            base_mag = float(raw_mag)

        if base_mag <= 0.0:
            return 0.0, 0.0

        if self._is_bow(w_meta) and base_mag <= 1.0:
            mag = 1.0
        else:
            mag_mult = max(0.01, 1.0 + sum(float(m.get('magazine_capacity') or 0.0) for m in mods if m.get('name') != 'Riven Mod') + float(rv.get('magazine_capacity') or 0.0))
            mag = max(1.0, base_mag * mag_mult)

        if base_reload <= 0.0:
            return mag, 0.0
        rel_mult = max(0.01, 1.0 + sum(float(m.get('reload_speed') or 0.0) for m in mods if m.get('name') != 'Riven Mod') + float(rv.get('reload_speed') or 0.0))
        rate = rel_mult / base_reload
        return mag, 1.0 / max(rate, 0.01)

    @staticmethod
    def _valence(stats: Optional[Dict[str, float]]) -> float:
        return sum(max(0.0, float(v or 0.0)) for k, v in (stats or {}).items() if str(k).startswith('valence_'))

    @staticmethod
    def _valence_phys(stats: Optional[Dict[str, float]]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for k, v in (stats or {}).items():
            if str(k).startswith('valence_'):
                el = str(k)[len('valence_'):].lower()
                if el in _PHYS:
                    out[el] = out.get(el, 0.0) + max(0.0, float(v or 0.0))
        return out

    @staticmethod
    def _mod_elemental_total(mod: Dict[str, Any]) -> float:
        """Sum elemental damage bonus on a mod/riven without double-counting named element keys."""
        if mod.get('elemental_damage'):
            return float(mod['elemental_damage'])
        return sum(float(mod.get(el) or 0.0) for el in _ALL_ELEMENTS)

    @staticmethod
    def _vigilante_chance(w_meta: Dict[str, Any], mod_objs: List[Dict[str, Any]]) -> float:
        """Vigilante set bonus: +5% chance per equipped Vigilante mod (cap 30%) to enhance Primary crits by +1 tier."""
        if str(w_meta.get('category') or '').strip().lower() != 'primary':
            return 0.0
        count = sum(
            1 for m in mod_objs
            if m.get('name') != 'Riven Mod' and 'vigilante' in str(m.get('modSet') or '').lower()
        )
        return min(0.30, 0.05 * count)

    @staticmethod
    def _initial_combo_mult(mod_objs: List[Dict[str, Any]], rv: Dict[str, float], extra_initial_combo: float = 0.0) -> float:
        """Convert initial combo counter (e.g. Corrupt Charge +30 -> 2x, Galvanized Reflex +80 -> 5x) to combo multiplier."""
        total_ic = float(extra_initial_combo or 0.0) + float(rv.get('initial_combo') or 0.0) + sum(
            float(m.get('initial_combo') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod'
        )
        if total_ic <= 0.0:
            return 1.0
        return min(12.0, 1.0 + math.floor(total_ic / 20.0))

    @staticmethod
    def _mod_fire_rate_sum(w_meta: Dict[str, Any], mod_objs: List[Dict[str, Any]]) -> float:
        is_bow = WarframeDamageEngine._is_bow(w_meta)
        total = 0.0
        for mod in mod_objs:
            if mod.get('name') == 'Riven Mod':
                continue
            fr = float(mod.get('fire_rate') or 0.0)
            if fr == 0.0:
                continue
            if is_bow:
                mult = float(mod.get('bow_fire_rate_mult') or 0.0)
                if mult <= 0.0:
                    mult = 2.0 if str(mod.get('name') or '').strip().lower() in _BOW_2X_FR_MODS else 1.0
                fr *= mult
            total += fr
        return total

    @staticmethod
    def _resolve_base_status(w_meta: Dict[str, Any]) -> float:
        """Resolve weapon base status chance as a decimal fraction (preserving explicit 0.0)."""
        raw_status = next((v for v in (w_meta.get('procChance'), w_meta.get('status_chance')) if v is not None), None)
        if raw_status is None:
            attacks = w_meta.get('attacks') or []
            atk0_status = attacks[0].get('status_chance') if attacks and isinstance(attacks[0], dict) else None
            if atk0_status is not None:
                raw_status = atk0_status
        base_status = float(raw_status) if raw_status is not None else 0.1
        return base_status / 100.0 if base_status > 1.0 else base_status

    @staticmethod
    def _collect_faction_bonuses(
        mod_objs: List[Dict[str, Any]],
        rv: Dict[str, float],
        target_faction: Optional[str] = None,
    ) -> Tuple[float, float, Dict[str, float]]:
        """Collect active faction scalar (with target_faction), generic-only scalar, and per-faction bonuses."""
        generic = float(rv.get('faction_damage', 0.0) or 0.0) + sum(
            float(m.get('faction_damage', 0.0) or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod'
        )
        by_faction: Dict[str, float] = {}
        for m in mod_objs:
            for name, val in (m.get('faction') or {}).items():
                key = {'sentients': 'sentient', 'corrupted': 'orokin'}.get(str(name).lower(), str(name).lower())
                by_faction[key] = by_faction.get(key, 0.0) + float(val)
        active = generic
        if target_faction:
            tkey = {'sentients': 'sentient', 'corrupted': 'orokin'}.get(str(target_faction).lower(), str(target_faction).lower())
            active += by_faction.get(tkey, 0.0)
        return active, generic, by_faction

    def _primary_damage_split(self, w_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Identify whether total_damage is a single attack or a paired Direct + Radial attack."""
        normal = [
            a for a in (w_meta.get('attacks') or [])
            if isinstance(a, dict)
            and 'incarnon' not in str(a.get('name', '')).lower()
            and _norm_dist(a.get('damage'))
        ]
        total_dmg = float(w_meta.get('total_damage') or 0.0)
        if not normal:
            return {
                'paired': False,
                'direct_atk': None,
                'direct_dist': {},
                'direct_base': total_dmg or 100.0,
                'radial_atk': None,
                'radial_dist': {},
                'radial_base': 0.0,
            }

        a0 = normal[0]
        d0 = _norm_dist(a0.get('damage'))
        s0 = sum(d0.values())

        # Check paired Direct + AoE (e.g. Kuva Zarr 50+673=723, Kuva Bramma 187+839=1026, Acceltra Prime 44+53=97).
        if len(normal) >= 2 and total_dmg > 0.0 and abs(s0 - total_dmg) > 0.02 * total_dmg:
            for a1 in normal[1:]:
                if not _is_aoe_attack(a1):
                    continue
                d1 = _norm_dist(a1.get('damage'))
                s1 = sum(d1.values())
                if s1 > 0.0 and abs((s0 + s1) - total_dmg) <= 0.02 * max(total_dmg, 1.0):
                    return {
                        'paired': True,
                        'direct_atk': a0,
                        'direct_dist': d0,
                        'direct_base': s0,
                        'radial_atk': a1,
                        'radial_dist': d1,
                        'radial_base': s1,
                    }

        # Otherwise pick the attack whose damage sum matches total_damage (preferring a0 on ties).
        if total_dmg > 0.0 and abs(s0 - total_dmg) > 0.02 * total_dmg:
            best = min(normal, key=lambda a: abs(sum(_norm_dist(a.get('damage')).values()) - total_dmg))
            db = _norm_dist(best.get('damage'))
            sb = sum(db.values())
            if abs(sb - total_dmg) <= 0.02 * max(total_dmg, 1.0):
                return {
                    'paired': False,
                    'direct_atk': best,
                    'direct_dist': db,
                    'direct_base': sb,
                    'radial_atk': None,
                    'radial_dist': {},
                    'radial_base': 0.0,
                }

        return {
            'paired': False,
            'direct_atk': a0,
            'direct_dist': d0,
            'direct_base': s0,
            'radial_atk': None,
            'radial_dist': {},
            'radial_base': 0.0,
        }

    def _modded_base_per_pellet(
        self,
        w_meta: Dict[str, Any],
        left: Dict[str, float],
        mod_dmg: float,
        r_dmg: float,
        base_override: Optional[float] = None,
    ) -> float:
        """Modded base damage per projectile (WFCD total_damage is already per-pellet; never divide by base_ms)."""
        base_dmg = float(base_override if base_override is not None else (w_meta.get('total_damage') or 100.0))
        valence = self._valence(left)
        return base_dmg * (1.0 + valence) * max(0.0, 1.0 + mod_dmg + r_dmg)

    def _physical_bonus_for_dist(
        self,
        dist: Dict[str, float],
        values: Dict[str, float],
        valence_total: float = 0.0,
        valence_phys: Optional[Dict[str, float]] = None,
    ) -> float:
        """Physical mod damage fraction relative to eff_base = sum(dist) * (1 + valence_total)."""
        total = sum(dist.values())
        if total <= 0.0 or not values:
            return 0.0
        vp = valence_phys or {}
        added = sum((dist.get(k, 0.0) + vp.get(k, 0.0) * total) * float(v or 0.0) for k, v in values.items())
        return added / (total * max(0.01, 1.0 + valence_total))

    def _physical_bonus(
        self,
        w_meta: Dict[str, Any],
        values: Dict[str, float],
        left: Optional[Dict[str, float]] = None,
    ) -> float:
        """Physical mod bonus weighted across the weapon's true primary damage distribution (paired Direct+Radial safe)."""
        if not values or not any(values.values()):
            return 0.0
        split = self._primary_damage_split(w_meta)
        valence_total = self._valence(left)
        vp = self._valence_phys(left)
        if split['paired']:
            d0, d1 = split['direct_dist'], split['radial_dist']
            s0, s1 = split['direct_base'], split['radial_base']
            tot = s0 + s1
            if tot <= 0.0:
                return 0.0
            added = (
                sum((d0.get(k, 0.0) + vp.get(k, 0.0) * s0) * float(v or 0.0) for k, v in values.items())
                + sum((d1.get(k, 0.0) + vp.get(k, 0.0) * s1) * float(v or 0.0) for k, v in values.items())
            )
            return added / (tot * max(0.01, 1.0 + valence_total))
        return self._physical_bonus_for_dist(split['direct_dist'], values, valence_total, vp)

    def _compute_status_section(
        self,
        mod_objs: List[Dict[str, Any]],
        rv: Dict[str, float],
        elements: Optional[Dict[str, Any]],
        modded_base: float,
        final_ms: float,
        base_ms: float,
        final_cc: float,
        final_cd: float,
        final_status: float,
        final_fr: float,
        efr: float,
        crit_avg: float,
        faction_scalar: float,
        faction_by_name: Dict[str, float],
        shooting_prop: float,
        generic_faction: Optional[float] = None,
        *,
        vigilante_chance: float = 0.0,
        is_beam: bool = False,
        radial_status_input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute steady-state status DoT DPS, breakdown, Slash vs non-Slash split, per-faction DoTs, and forced bleeds."""
        from scripts.damage_formulas import FACTION_MODIFIERS, bleed_tick, hm_crit_avg, status_dot_dps

        status_damage_sum = sum(
            float(m.get('status_damage') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod'
        ) + float(rv.get('status_damage') or 0.0)
        has_hm = any('hunter munitions' in str(m.get('name', '')).lower() for m in mod_objs)
        has_ib = any(
            k in str(m.get('name', '')).lower() for m in mod_objs for k in ('internal bleeding', 'hemorrhage')
        )
        shares = (elements or {}).get('shares') or {}

        forced_crit: Dict[str, float] = {}
        forced_nat: Dict[str, float] = {}
        if has_hm and final_cc > 0.0:
            forced_crit['slash'] = 0.30 * min(1.0, final_cc)
        if has_ib and final_status > 0.0 and elements is not None and shares.get('impact', 0.0) > 0.0:
            ib_chance = 0.70 if final_fr < 2.5 else 0.35
            forced_nat['slash'] = final_status * shares['impact'] * ib_chance

        hm_crit = hm_crit_avg(final_cc, final_cd, vigilante_chance=vigilante_chance)
        beam_ms_scale = (final_ms / max(0.1, base_ms)) if is_beam else 1.0
        bleed_base = modded_base * (beam_ms_scale if is_beam else 1.0)
        if has_hm:
            hm_bleed_tick = bleed_tick(bleed_base, faction_scalar, status_damage_sum, hm_crit)
        elif has_ib:
            hm_bleed_tick = bleed_tick(bleed_base, faction_scalar, status_damage_sum, crit_avg)
        else:
            hm_bleed_tick = 0.0

        # Synthetic direct-hit fixtures without `attacks` (`elements is None`) keep status_dps disabled unless forced bleed exists.
        natural_active = final_status > 0.0 and elements is not None
        active_shares = shares if natural_active else {}
        active_sc = final_status if natural_active else 0.0

        elem_bonuses = {
            'heat': sum(float(m.get('heat') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod') + float(rv.get('heat') or 0.0),
            'toxin': sum(float(m.get('toxin') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod') + float(rv.get('toxin') or 0.0),
            'electric': (
                sum(float(m.get('electric') or 0.0) + float(m.get('electricity') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod')
                + float(rv.get('electric') or 0.0)
                + float(rv.get('electricity') or 0.0)
            ),
        }

        dot_res = status_dot_dps(
            modded_base,
            active_shares,
            active_sc,
            final_ms,
            efr,
            faction=faction_scalar,
            status_damage=status_damage_sum,
            crit_avg=crit_avg,
            element_bonuses=elem_bonuses,
            forced_procs_per_pellet=forced_nat,
            forced_crit_procs_per_pellet=forced_crit,
            forced_crit_avg=hm_crit,
            is_beam=is_beam,
            beam_ms_scale=beam_ms_scale,
        )
        status_breakdown = dict(dot_res['breakdown'])
        hm_slash_dps = float(dot_res.get('forced_crit_dps') or 0.0)

        # Paired Direct + Radial attacks also roll status procs on the radial explosion component.
        if radial_status_input:
            r_shares = radial_status_input.get('shares') or {}
            r_base = float(radial_status_input.get('modded_base') or 0.0)
            r_sc = float(radial_status_input.get('status_chance') or 0.0)
            r_crit = float(radial_status_input.get('crit_avg') or crit_avg)
            r_cc = float(radial_status_input.get('crit_chance') or final_cc)
            r_cd = float(radial_status_input.get('crit_mult') or final_cd)
            r_hm = {'slash': 0.30 * min(1.0, r_cc)} if (has_hm and r_cc > 0.0) else {}
            r_hm_crit = hm_crit_avg(r_cc, r_cd, vigilante_chance=vigilante_chance)
            if r_base > 0.0 and (r_sc > 0.0 or r_hm):
                r_dot = status_dot_dps(
                    r_base,
                    r_shares if r_sc > 0.0 else {},
                    r_sc,
                    final_ms,
                    efr,
                    faction=faction_scalar,
                    status_damage=status_damage_sum,
                    crit_avg=r_crit,
                    element_bonuses=elem_bonuses,
                    forced_crit_procs_per_pellet=r_hm,
                    forced_crit_avg=r_hm_crit,
                    is_beam=False,
                    beam_ms_scale=1.0,
                )
                for st, val in r_dot['breakdown'].items():
                    status_breakdown[st] = status_breakdown.get(st, 0.0) + val
                hm_slash_dps += float(r_dot.get('forced_crit_dps') or 0.0)

        status_dps = sum(status_breakdown.values())
        status_sustained_dps = status_dps * shooting_prop
        slash_status_dps = float(status_breakdown.get('slash', 0.0))
        non_slash_status_dps = max(0.0, status_dps - slash_status_dps)

        faction_status_dps: Dict[str, float] = {}
        if status_dps > 0.0:
            generic_only = faction_scalar if generic_faction is None else generic_faction
            active_scale = max(0.01, 1.0 + faction_scalar)
            for fac, table in FACTION_MODIFIERS.items():
                fb = generic_only + faction_by_name.get(fac, 0.0)
                bane_scale = (max(0.0, 1.0 + fb) / active_scale) ** 2
                faction_status_dps[fac] = sum(
                    dps * (1.0 if st == 'slash' else table.get(st, 1.0)) * bane_scale
                    for st, dps in status_breakdown.items()
                )

        return {
            'status_dps': status_dps,
            'status_sustained_dps': status_sustained_dps,
            'slash_status_dps': slash_status_dps,
            'slash_status_sustained_dps': slash_status_dps * shooting_prop,
            'non_slash_status_dps': non_slash_status_dps,
            'non_slash_status_sustained_dps': non_slash_status_dps * shooting_prop,
            'hm_slash_dps': hm_slash_dps,
            'status_breakdown': status_breakdown,
            'faction_status_dps': faction_status_dps,
            'hm_bleed_tick': hm_bleed_tick,
            'has_forced_bleed': has_hm or has_ib,
        }

    @staticmethod
    def _db_charge_time(w_meta: Dict[str, Any]) -> float:
        """Base charge time of the attack total_damage describes (0 for weapons that fire without charging)."""
        attacks = [a for a in (w_meta.get('attacks') or [])
                   if isinstance(a, dict) and 'incarnon' not in str(a.get('name', '')).lower()]
        if not attacks:
            return 0.0
        total = float(w_meta.get('total_damage') or 0.0)
        # On paired Direct+Radial weapons (e.g. Lenz 50+10=60, Kuva Bramma 187+839=1026), attacks[0] holds the charge_time.
        if len(attacks) >= 2:
            s0 = sum((attacks[0].get('damage') or {}).values())
            for a1 in attacks[1:]:
                if _is_aoe_attack(a1):
                    s1 = sum((a1.get('damage') or {}).values())
                    if s0 > 0 and s1 > 0 and abs((s0 + s1) - total) <= 0.02 * max(total, 1.0):
                        return float(attacks[0].get('charge_time') or a1.get('charge_time') or 0.0)
        main = min(attacks, key=lambda a: abs(sum((a.get('damage') or {}).values()) - total))
        return float(main.get('charge_time') or 0.0)

    @staticmethod
    def _headcrit_tier(level: int, cd: float) -> float:
        """Crit tier multiplier on a weak point: tier 1+ gets the extra 2x headcrit, tier 0 is a plain hit."""
        tier = 1.0 + level * (cd - 1.0)
        return tier * 2.0 if level >= 1 else tier

    def _headshot(
        self,
        final_dmg: float,
        per_pellet: float,
        ms_min: int,
        ms_max: int,
        final_cc: float,
        final_cd: float,
        base_cc: float,
        wp_damage: float,
        wp_crit_chance: float,
        headshot_bonus: float,
        faction: float,
        vigilante_chance: float = 0.0,
    ) -> Dict[str, float]:
        """Weak point hits: the 3x weak point base, then the 2x headcrit on crit tiers only."""
        from scripts.damage_formulas import headcrit_avg_mult, weak_point_multiplier

        wp_mult = weak_point_multiplier(3.0, wp_damage, headshot_bonus, is_headshot=True)
        cc_wp = max(0.0, final_cc + base_cc * wp_crit_chance)
        return {
            'wp_mult': wp_mult,
            'final_cc_wp': cc_wp,
            'max_crit_hit': per_pellet * ms_max * wp_mult * self._headcrit_tier(_tier_max(cc_wp), final_cd) * faction,
            'min_hit': per_pellet * ms_min * wp_mult * self._headcrit_tier(_tier_min(cc_wp), final_cd) * faction,
            'expected_hit': final_dmg * wp_mult * headcrit_avg_mult(cc_wp, final_cd, vigilante_chance=vigilante_chance) * faction,
        }

    def _compute_incarnon(
        self,
        w_meta: Dict[str, Any],
        left: Dict[str, float],
        mod_objs: List[Dict[str, Any]],
        rv: Dict[str, float],
        *,
        mod_dmg: float,
        r_dmg: float,
        mod_elem_only: float,
        r_elem_only: float,
        mod_phys_all: Dict[str, float],
        mod_ms: float,
        r_ms: float,
        mod_cc: float,
        r_cc: float,
        mod_cd: float,
        r_cd: float,
        mod_status: float,
        r_status: float,
        mod_flat_cc: float,
        mod_flat_cd: float,
        mod_flat_status: float,
        mod_fr: float,
        r_fr: float,
        lock_multishot: bool,
        lock_fire_rate: bool,
        faction: float,
        r_faction: float,
        vigilante_chance: float,
        base_cc: float,
        base_cd: float,
        base_fr: float,
        base_status: float,
        buff_dmg: float = 0.0,
        gunco_bonus: float = 0.0,
        is_mult_gunco: bool = False,
        buff_elem: float = 0.0,
        buff_ms: float = 0.0,
        buff_cc: float = 0.0,
        buff_cd: float = 0.0,
        buff_sc: float = 0.0,
        buff_fr: float = 0.0,
        buff_flat_cc: float = 0.0,
        buff_flat_cd: float = 0.0,
        buff_flat_sc: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate Incarnon attack (plus paired Incarnon AoE, Evolutions II-V, Attrition, and beam DoTs)."""
        from scripts.damage_formulas import average_crit_mult

        inc = w_meta.get('incarnon_attack')
        if not inc or not isinstance(inc, dict):
            return None

        inc_dist = _norm_dist(inc.get('damage'))
        inc_raw_base = sum(inc_dist.values())
        if inc_raw_base <= 0.0:
            return None

        inc_data = self._get_incarnon_data(w_meta) or {}
        evo = inc_data.get('default_evolutions') or {}
        evo_base_dmg = float(evo.get('flat_base_damage') or 0.0)
        evo_flat_cc = float(evo.get('flat_crit_chance') or 0.0)
        evo_flat_sc = float(evo.get('flat_status') or 0.0)
        evo_cd = float(evo.get('crit_mult') or 0.0)
        evo_ms = float(evo.get('multishot') or 0.0)
        attrition = evo.get('non_crit_attrition') if isinstance(evo.get('non_crit_attrition'), dict) else None
        inc_is_beam = bool(inc_data.get('is_beam')) or str(inc.get('shot_type') or '').lower() in ('beam', 'continuous')

        valence_total = self._valence(left)
        vp = self._valence_phys(left)
        inc_base = inc_raw_base + evo_base_dmg
        inc_eff_base = inc_base * (1.0 + valence_total)

        # Scale physical mods strictly by Incarnon's own damage distribution.
        inc_phys = self._physical_bonus_for_dist(inc_dist, mod_phys_all, valence_total, vp)
        inc_elem_mult = max(0.0, 1.0 + mod_elem_only + r_elem_only + inc_phys + buff_elem)

        raw_inc_cc = float(inc.get('crit_chance') or 0.0)
        inc_base_cc = (raw_inc_cc / 100.0 if raw_inc_cc > 1.0 else (raw_inc_cc or base_cc)) + evo_flat_cc
        inc_base_cd = float(inc.get('crit_mult') or base_cd) + evo_cd
        raw_inc_sc = inc.get('status_chance')
        if raw_inc_sc is not None:
            inc_base_sc = (float(raw_inc_sc) / 100.0 if float(raw_inc_sc) > 1.0 else float(raw_inc_sc)) + evo_flat_sc
        else:
            inc_base_sc = base_status + evo_flat_sc

        inc_final_cc = max(0.0, inc_base_cc * (1.0 + mod_cc + r_cc + buff_cc) + mod_flat_cc + buff_flat_cc)
        inc_final_cd = max(1.0, inc_base_cd * (1.0 + mod_cd + r_cd + buff_cd) + mod_flat_cd + buff_flat_cd)
        inc_final_sc = max(0.0, inc_base_sc * (1.0 + mod_status + r_status + buff_sc) + mod_flat_status + buff_flat_sc)

        inc_crit_avg = average_crit_mult(inc_final_cc, inc_final_cd, vigilante_chance=vigilante_chance)
        attr_extra = 0.0
        if attrition and inc_final_cc < 1.0:
            attr_extra = (1.0 - inc_final_cc) * float(attrition.get('chance') or 0.0) * float(attrition.get('bonus') or 0.0)
        inc_hit_crit = inc_crit_avg + attr_extra

        inc_base_ms = float(inc.get('multishot') or 1.0)
        if lock_multishot:
            inc_final_ms = max(0.1, inc_base_ms)
        else:
            inc_final_ms = max(0.1, inc_base_ms * max(0.1, 1.0 + mod_ms + r_ms + buff_ms + evo_ms))

        inc_base_fr = float(inc.get('speed') or base_fr)
        if lock_fire_rate:
            inc_final_fr = max(0.1, inc_base_fr)
        else:
            inc_final_fr = max(0.1, inc_base_fr * max(0.1, 1.0 + mod_fr + r_fr + buff_fr))

        if is_mult_gunco:
            direct_dmg_mult = max(0.0, 1.0 + mod_dmg + r_dmg + buff_dmg) * max(0.0, 1.0 + gunco_bonus)
        else:
            direct_dmg_mult = max(0.0, 1.0 + mod_dmg + r_dmg + buff_dmg + gunco_bonus)
        aoe_dmg_mult = max(0.0, 1.0 + mod_dmg + r_dmg + buff_dmg)

        direct_hit = inc_eff_base * direct_dmg_mult * inc_elem_mult * inc_final_ms * inc_hit_crit * faction

        # Paired Incarnon AoE (e.g. Laetum Auto Radial Attack, Burston Incarnon Radial Attack; no GunCO on AoE).
        aoe_hit = 0.0
        inc_aoe = w_meta.get('incarnon_aoe')
        aoe_status_input = None
        if isinstance(inc_aoe, dict):
            aoe_dist = _norm_dist(inc_aoe.get('damage'))
            aoe_raw = sum(aoe_dist.values())
            if aoe_raw > 0.0:
                aoe_eff_base = aoe_raw * (1.0 + valence_total)
                aoe_phys = self._physical_bonus_for_dist(aoe_dist, mod_phys_all, valence_total, vp)
                aoe_elem_mult = max(0.0, 1.0 + mod_elem_only + r_elem_only + aoe_phys + buff_elem)
                raw_aoe_cc = float(inc_aoe.get('crit_chance') or 0.0)
                aoe_base_cc = (raw_aoe_cc / 100.0 if raw_aoe_cc > 1.0 else (raw_aoe_cc or inc_base_cc - evo_flat_cc)) + evo_flat_cc
                aoe_base_cd = float(inc_aoe.get('crit_mult') or (inc_base_cd - evo_cd)) + evo_cd
                aoe_cc = max(0.0, aoe_base_cc * (1.0 + mod_cc + r_cc + buff_cc) + mod_flat_cc + buff_flat_cc)
                aoe_cd = max(1.0, aoe_base_cd * (1.0 + mod_cd + r_cd + buff_cd) + mod_flat_cd + buff_flat_cd)
                aoe_crit = average_crit_mult(aoe_cc, aoe_cd, vigilante_chance=vigilante_chance)
                aoe_attr = (1.0 - aoe_cc) * float(attrition.get('chance') or 0.0) * float(attrition.get('bonus') or 0.0) if (attrition and aoe_cc < 1.0) else 0.0
                aoe_hit = aoe_eff_base * aoe_dmg_mult * aoe_elem_mult * inc_final_ms * (aoe_crit + aoe_attr) * faction
                raw_aoe_sc = inc_aoe.get('status_chance')
                aoe_sc = max(0.0, ((float(raw_aoe_sc) / 100.0 if float(raw_aoe_sc) > 1.0 else float(raw_aoe_sc)) + evo_flat_sc) * (1.0 + mod_status + r_status + buff_sc) + mod_flat_status + buff_flat_sc) if raw_aoe_sc is not None else inc_final_sc
                aoe_el = self._elements_for_dist(aoe_dist, left, mod_objs, rv, inc_final_ms, is_melee=False)
                aoe_status_input = {
                    'shares': (aoe_el or {}).get('shares') or {},
                    'modded_base': aoe_eff_base * aoe_dmg_mult,
                    'status_chance': aoe_sc,
                    'crit_avg': aoe_crit,
                    'crit_chance': aoe_cc,
                    'crit_mult': aoe_cd,
                }

        total_hit = direct_hit + aoe_hit
        direct_burst = total_hit * inc_final_fr

        # Incarnon status DoTs (including beam multishot² for Torid/Boar/Furis Incarnon beams).
        inc_el = self._elements_for_dist(inc_dist, left, mod_objs, rv, inc_final_ms, is_melee=False)
        inc_status = self._compute_status_section(
            mod_objs,
            rv,
            inc_el,
            inc_eff_base * direct_dmg_mult,
            inc_final_ms,
            inc_base_ms,
            inc_final_cc,
            inc_final_cd,
            inc_final_sc,
            inc_final_fr,
            inc_final_fr,
            inc_crit_avg,
            r_faction,
            {},
            1.0,
            vigilante_chance=vigilante_chance,
            is_beam=inc_is_beam,
            radial_status_input=aoe_status_input,
        )

        return {
            'expected_hit': total_hit,
            'direct_expected_hit': direct_hit,
            'aoe_expected_hit': aoe_hit,
            'direct_burst_dps': direct_burst,
            'status_dps': inc_status['status_dps'],
            'burst_dps': direct_burst + inc_status['status_dps'],
            'final_cc': inc_final_cc,
            'final_cd': inc_final_cd,
            'final_status': inc_final_sc,
            'final_ms': inc_final_ms,
            'final_fr': inc_final_fr,
            'is_beam': inc_is_beam,
            'attrition_applied': attr_extra > 0.0,
            'attack_meta': inc,
        }

    def compute_metrics(
        self,
        w_meta: Dict[str, Any],
        left_stats: Optional[Dict[str, float]] = None,
        mod_objs: Optional[List[Dict[str, Any]]] = None,
        riven_stats: Optional[Dict[str, float]] = None,
        target_faction: Optional[str] = None,
        arcane: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Metrics from DB base stats, mods and riven. left_stats carries only the Valence Bonus (valence_*)
        and the melee rows heavy_damage, charge_time and slam_damage."""
        from scripts.damage_formulas import average_crit_mult, effective_fire_rate, shooting_proportion, status_tick_damage, status_proc_total_damage

        all_mods = self._prepare_mods(w_meta, mod_objs or [], keep_incompatible=True)
        incompatible_mods = [m.get('name') for m in all_mods if not m.get('_compatible', True)]
        mod_objs = [m for m in all_mods if m.get('_compatible', True)]

        mod_dmg = sum(float(mod.get('damage') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_ms = sum(float(mod.get('multishot') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_cc = sum(float(mod.get('crit_chance') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_cd = sum(float(mod.get('crit_damage') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_status = sum(float(mod.get('status') or mod.get('status_chance') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_flat_status = sum(float(mod.get('flat_status') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_flat_cc = sum(float(mod.get('flat_crit_chance') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_flat_cd = sum(float(mod.get('flat_crit_damage') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_fr = self._mod_fire_rate_sum(w_meta, mod_objs)
        mod_elem_only = sum(self._mod_elemental_total(mod) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_phys = {
            'slash': sum(float(mod.get('slash') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod'),
            'impact': sum(float(mod.get('impact') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod'),
            'puncture': sum(float(mod.get('puncture') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod'),
        }

        rv = riven_stats or {}
        r_dmg = float(rv.get('damage', 0.0) or rv.get('base_damage', 0.0) or 0.0)
        r_ms = float(rv.get('multishot', 0.0) or 0.0)

        # Acuity mods: "Multishot cannot be modified."
        lock_multishot = any(mod.get('lock_multishot') or 'acuity' in str(mod.get('name', '')).lower() for mod in mod_objs)
        if lock_multishot:
            mod_ms = 0.0
            r_ms = 0.0

        # Cannonade mods: "Fire Rate cannot be modified."
        lock_fire_rate = any(mod.get('lock_fire_rate') or 'cannonade' in str(mod.get('name', '')).lower() for mod in mod_objs)
        r_fr = float(rv.get('fire_rate', 0.0) or 0.0)
        if lock_fire_rate:
            mod_fr = 0.0
            r_fr = 0.0

        mod_wp_dmg = sum(float(mod.get('weak_point_damage') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_wp_cc = sum(float(mod.get('weak_point_crit_chance') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_hs_bonus = sum(float(mod.get('headshot_bonus') or 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        r_wp_dmg = float(rv.get('weak_point_damage') or 0.0)
        mod_wp_cc += float(rv.get('weak_point_crit_chance') or 0.0)
        hs_bonus_total = mod_hs_bonus + float(rv.get('headshot_bonus') or 0.0) + float((arcane or {}).get('headshot_bonus') or 0.0)

        r_cc = float(rv.get('crit_chance') or 0.0)
        r_cd = float(rv.get('crit_damage') or 0.0)
        r_status = float(rv.get('status') or rv.get('status_chance') or 0.0)
        r_elem_only = self._mod_elemental_total(rv)
        r_faction, generic_faction, faction_by_name = self._collect_faction_bonuses(
            mod_objs, rv, target_faction=target_faction
        )
        r_phys = {
            'slash': float(rv.get('slash') or 0.0),
            'impact': float(rv.get('impact') or 0.0),
            'puncture': float(rv.get('puncture') or 0.0),
        }
        all_phys = {k: mod_phys[k] + r_phys[k] for k in _PHYS}

        is_melee = str(w_meta.get('category') or '').strip().lower() == 'melee'
        is_beam = (not is_melee) and self._is_beam(w_meta)
        is_bow = (not is_melee) and self._is_bow(w_meta)
        left = dict(left_stats or {})
        base_dmg = float(w_meta.get('total_damage') or 100.0)
        base_ms = 1.0 if is_melee else max(1.0, float(w_meta.get('base_multishot') or 1.0))
        valence_total = self._valence(left)
        eff_base_dmg = base_dmg * (1.0 + valence_total)

        # Physical mods scale by the weapon's true share of that physical type (incl. Impact Valence), in the elemental bracket.
        phys_frac = self._physical_bonus(w_meta, all_phys, left)
        mod_elem_total = mod_elem_only + r_elem_only + phys_frac

        base_cc = float(w_meta.get('crit_chance', 0.1) or 0.0)
        if base_cc > 1.0:
            base_cc /= 100.0
        base_cd = float(w_meta.get('crit_mult', 1.5) or 1.5)
        base_fr = max(0.01, float(w_meta.get('fire_rate', 1.0) or 1.0))

        if is_melee:
            final_ms = 1.0
        elif lock_multishot:
            final_ms = base_ms
        else:
            final_ms = max(0.01, base_ms * max(0.01, 1.0 + mod_ms + r_ms))

        # WFCD total_damage is already per-pellet; multiply by final_ms (NOT final_ms / base_ms).
        ms_factor = 1.0 if is_melee else final_ms
        single_pellet_dmg = eff_base_dmg * max(0.0, 1.0 + mod_dmg + r_dmg) * max(0.0, 1.0 + mod_elem_total)
        final_dmg = single_pellet_dmg * ms_factor

        final_cc = max(0.0, base_cc * (1.0 + mod_cc + r_cc) + mod_flat_cc)
        final_cd = max(1.0, base_cd * (1.0 + mod_cd + r_cd) + mod_flat_cd)

        base_status = self._resolve_base_status(w_meta)
        final_status = max(0.0, base_status * (1.0 + mod_status + r_status) + mod_flat_status)

        final_fr = max(0.1, base_fr * max(0.1, 1.0 + mod_fr + r_fr))

        vigilante_chance = self._vigilante_chance(w_meta, mod_objs)
        exp_crit = average_crit_mult(final_cc, final_cd, vigilante_chance=vigilante_chance)
        min_crit = 1.0 + _tier_min(final_cc) * (final_cd - 1.0)
        max_crit = 1.0 + _tier_max(final_cc) * (final_cd - 1.0)
        faction = max(0.0, 1.0 + r_faction)

        per_pellet = single_pellet_dmg
        if not is_melee:
            if final_ms >= 1.0 - _EPS:
                ms_min = max(1, _tier_min(final_ms))
                ms_max = max(1, _tier_max(final_ms))
                ms_extra = round(max(0.0, final_ms - ms_min) * 100.0, 1)
            else:
                # Negative multishot riven (<1 pellet): 0-pellet misfire trough, 1-pellet peak.
                ms_min = 0
                ms_max = 1
                ms_extra = round(final_ms * 100.0, 1)
        else:
            ms_min = 1
            ms_max = 1
            ms_extra = 0.0

        min_hit = per_pellet * ms_min * min_crit * faction
        max_non_crit = per_pellet * ms_max * faction
        max_crit_hit = per_pellet * ms_max * max_crit * faction
        expected_hit = final_dmg * exp_crit * faction

        charge_time = float(left.get('charge_time') or 0.0)
        if not charge_time:
            db_charge = self._db_charge_time(w_meta)
            if db_charge > 0.0:
                charge_time = db_charge * max(0.01, base_fr) / final_fr
        efr = effective_fire_rate(final_fr, charge_time, is_bow_charge=(is_bow and charge_time > 0.0))
        direct_burst_dps = expected_hit * efr

        # Weak point / headshot: crit on a weak point gets the extra 2x headcrit multiplier.
        if is_melee:
            wp_mult = 1.0
            final_cc_wp = final_cc
            headshot_max_crit_hit = max_crit_hit
            headshot_min_hit = min_hit
            headshot_expected_hit = expected_hit
            headshot_burst_dps = direct_burst_dps
        else:
            hs = self._headshot(
                final_dmg, per_pellet, ms_min, ms_max, final_cc, final_cd, base_cc,
                mod_wp_dmg + r_wp_dmg, mod_wp_cc, hs_bonus_total, faction,
                vigilante_chance=vigilante_chance,
            )
            wp_mult = hs['wp_mult']
            final_cc_wp = hs['final_cc_wp']
            headshot_max_crit_hit = hs['max_crit_hit']
            headshot_min_hit = hs['min_hit']
            headshot_expected_hit = hs['expected_hit']
            headshot_burst_dps = headshot_expected_hit * efr

        if is_melee:
            shooting_prop = 1.0
        else:
            mag, reload_t = self._magazine_and_reload(w_meta, mod_objs, rv)
            shooting_prop = shooting_proportion(mag, efr, reload_t)
        direct_sustained_dps = direct_burst_dps * shooting_prop
        headshot_ratio = (headshot_expected_hit / expected_hit) if expected_hit > 0.0 else 1.0

        result: Dict[str, Any] = {
            "final_dmg": final_dmg,
            "final_cc": final_cc,
            "final_cd": final_cd,
            "final_fr": final_fr,
            "final_ms": final_ms,
            "min_hit": min_hit,
            "max_non_crit": max_non_crit,
            "max_crit_hit": max_crit_hit,
            "expected_hit": expected_hit,
            "direct_burst_dps": direct_burst_dps,
            "direct_sustained_dps": direct_sustained_dps,
            "status_dps": 0.0,
            "status_sustained_dps": 0.0,
            "slash_status_dps": 0.0,
            "slash_status_sustained_dps": 0.0,
            "non_slash_status_dps": 0.0,
            "non_slash_status_sustained_dps": 0.0,
            "hm_slash_dps": 0.0,
            "status_breakdown": {},
            "faction_status_dps": {},
            "shooting_proportion": shooting_prop,
            "burst_dps": direct_burst_dps,
            "sustained_dps": direct_sustained_dps,
            "per_pellet_dmg": per_pellet,
            "ms_min_pellets": ms_min,
            "ms_max_pellets": ms_max,
            "ms_extra_pct": ms_extra,
            "effective_fire_rate": efr,
            "wp_mult": wp_mult,
            "final_cc_wp": final_cc_wp,
            "headshot_max_crit_hit": headshot_max_crit_hit,
            "headshot_min_hit": headshot_min_hit,
            "headshot_expected_hit": headshot_expected_hit,
            "headshot_burst_dps": headshot_burst_dps,
            "headshot_ratio": headshot_ratio,
            "lock_multishot": lock_multishot,
            "lock_fire_rate": lock_fire_rate,
            "is_beam": is_beam,
            "vigilante_chance": vigilante_chance,
            "final_status": final_status,
            "faction_by_name": faction_by_name,
            "generic_faction": generic_faction,
            "active_faction_bonus": r_faction,
            "effective_mod_dmg": mod_dmg + r_dmg,
            "effective_mod_elem": mod_elem_total,
            "incompatible_mods": incompatible_mods,
            "innate": describe_innate(w_meta, mod_objs, left),
        }

        result['elements'] = self.compute_elements(w_meta, left, mod_objs, rv, final_ms)

        # Radial AoE / Slam
        if left.get('slam_damage'):
            result['radial'] = {'base_damage': float(left['slam_damage'])}
        elif w_meta.get('radial_attack'):
            rad_atk = w_meta['radial_attack']
            rad_dist = _norm_dist(rad_atk.get('damage'))
            rad_raw = sum(rad_dist.values())
            if is_melee and base_dmg > 0.0:
                slam_bonus = sum(float(m.get('slam_damage') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod')
                rad_dmg_mult = max(0.0, 1.0 + mod_dmg + r_dmg + slam_bonus) / max(0.01, 1.0 + mod_dmg + r_dmg)
                result['radial'] = {'base_damage': rad_raw * (final_dmg / base_dmg) * rad_dmg_mult}
            elif rad_raw > 0.0:
                rad_eff_base = rad_raw * (1.0 + valence_total)
                rad_phys = self._physical_bonus_for_dist(rad_dist, all_phys, valence_total, self._valence_phys(left))
                rad_elem_mult = max(0.0, 1.0 + mod_elem_only + r_elem_only + rad_phys)
                raw_rad_cc = float(rad_atk.get('crit_chance') or 0.0)
                rad_base_cc = (raw_rad_cc / 100.0 if raw_rad_cc > 1.0 else (raw_rad_cc or base_cc))
                rad_base_cd = float(rad_atk.get('crit_mult') or base_cd)
                rad_cc = max(0.0, rad_base_cc * (1.0 + mod_cc + r_cc) + mod_flat_cc)
                rad_cd = max(1.0, rad_base_cd * (1.0 + mod_cd + r_cd) + mod_flat_cd)
                rad_crit = average_crit_mult(rad_cc, rad_cd, vigilante_chance=vigilante_chance)
                rad_modded = rad_eff_base * max(0.0, 1.0 + mod_dmg + r_dmg) * rad_elem_mult * ms_factor
                rad_expected = rad_modded * rad_crit * faction
                rad_fr = max(0.1, float(rad_atk.get('speed') or base_fr) * max(0.1, 1.0 + mod_fr + r_fr))
                result['radial'] = {
                    'base_damage': rad_expected,
                    'modded_damage': rad_modded,
                    'expected_hit': rad_expected,
                    'burst_dps': rad_expected * rad_fr,
                }

        # Heavy Attack (including Killing Blow heavy_damage_bonus, Corrupt Charge initial_combo, and forced heavy procs)
        trait = self._get_trait(w_meta)
        heavy_dmg_bonus = sum(float(m.get('heavy_damage_bonus') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod') + float(rv.get('heavy_damage_bonus') or 0.0)
        init_combo_mult = self._initial_combo_mult(mod_objs, rv)
        if left.get('heavy_damage'):
            result['heavy'] = {'heavy_hit': float(left['heavy_damage'])}
        elif is_melee and w_meta.get('heavy_damage') and base_dmg > 0.0:
            base_dmg_denom = max(0.01, 1.0 + mod_dmg + r_dmg)
            heavy_dmg_ratio = max(0.0, 1.0 + mod_dmg + r_dmg + heavy_dmg_bonus) / base_dmg_denom
            raw_heavy_hit = float(w_meta['heavy_damage']) * (final_dmg / base_dmg) * heavy_dmg_ratio * init_combo_mult
            heavy_cc = max(0.0, final_cc + base_cc * sum(float(m.get('heavy_crit_chance') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod'))
            heavy_crit = average_crit_mult(heavy_cc, final_cd)
            heavy_info: Dict[str, Any] = {
                'heavy_hit': raw_heavy_hit,
                'expected_hit': raw_heavy_hit * heavy_crit * faction,
                'heavy_cc': heavy_cc,
                'initial_combo_mult': init_combo_mult,
            }
            forced_proc = trait.get('forced_heavy_proc')
            if forced_proc:
                sd_sum = sum(float(m.get('status_damage') or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod') + float(rv.get('status_damage') or 0.0)
                heavy_modded_base = float(w_meta['heavy_damage']) * (1.0 + valence_total) * max(0.0, 1.0 + mod_dmg + r_dmg + heavy_dmg_bonus) * init_combo_mult
                eb = sum(float(m.get(forced_proc) or 0.0) for m in mod_objs if m.get('name') != 'Riven Mod') + float(rv.get(forced_proc) or 0.0)
                heavy_info['forced_proc'] = {
                    'type': forced_proc,
                    'tick': status_tick_damage(forced_proc, heavy_modded_base, faction=r_faction, status_damage=sd_sum, crit_avg=heavy_crit, element_bonus=eb),
                    'total': status_proc_total_damage(forced_proc, heavy_modded_base, faction=r_faction, status_damage=sd_sum, crit_avg=heavy_crit, element_bonus=eb),
                }
            result['heavy'] = heavy_info

        for atk in w_meta.get('attacks', []):
            if atk.get('name') == 'Energy Disk':
                damage = sum((atk.get('damage') or {}).values())
                if base_dmg > 0.0:
                    damage *= final_dmg / base_dmg
                result['energy_disk'] = {'damage': damage}
                break

        inc_res = self._compute_incarnon(
            w_meta, left, mod_objs, rv,
            mod_dmg=mod_dmg, r_dmg=r_dmg,
            mod_elem_only=mod_elem_only, r_elem_only=r_elem_only,
            mod_phys_all=all_phys,
            mod_ms=mod_ms, r_ms=r_ms,
            mod_cc=mod_cc, r_cc=r_cc,
            mod_cd=mod_cd, r_cd=r_cd,
            mod_status=mod_status, r_status=r_status,
            mod_flat_cc=mod_flat_cc, mod_flat_cd=mod_flat_cd, mod_flat_status=mod_flat_status,
            mod_fr=mod_fr, r_fr=r_fr,
            lock_multishot=lock_multishot, lock_fire_rate=lock_fire_rate,
            faction=faction, r_faction=r_faction, vigilante_chance=vigilante_chance,
            base_cc=base_cc, base_cd=base_cd, base_fr=base_fr, base_status=base_status,
        )
        if inc_res is not None:
            result['incarnon'] = inc_res

        # Status DoTs (scoping Direct vs Radial on paired AoE weapons so Internal Bleeding & Blast shares are exact)
        split = self._primary_damage_split(w_meta)
        radial_status_input = None
        if split['paired']:
            direct_modded_base = self._modded_base_per_pellet(w_meta, left, mod_dmg, r_dmg, base_override=split['direct_base'])
            rad_atk = split['radial_atk']
            rad_el = self._elements_for_dist(split['radial_dist'], left, mod_objs, rv, final_ms, is_melee)
            raw_r_sc = rad_atk.get('status_chance') if isinstance(rad_atk, dict) else None
            if raw_r_sc is not None:
                r_base_sc = float(raw_r_sc) / 100.0 if float(raw_r_sc) > 1.0 else float(raw_r_sc)
                r_sc = max(0.0, r_base_sc * (1.0 + mod_status + r_status) + mod_flat_status)
            else:
                r_sc = final_status
            raw_r_cc = float(rad_atk.get('crit_chance') or 0.0) if isinstance(rad_atk, dict) else 0.0
            r_base_cc = (raw_r_cc / 100.0 if raw_r_cc > 1.0 else (raw_r_cc or base_cc))
            r_base_cd = float(rad_atk.get('crit_mult') or base_cd) if isinstance(rad_atk, dict) else base_cd
            r_cc_f = max(0.0, r_base_cc * (1.0 + mod_cc + r_cc) + mod_flat_cc)
            r_cd_f = max(1.0, r_base_cd * (1.0 + mod_cd + r_cd) + mod_flat_cd)
            radial_status_input = {
                'shares': (rad_el or {}).get('shares') or {},
                'modded_base': self._modded_base_per_pellet(w_meta, left, mod_dmg, r_dmg, base_override=split['radial_base']),
                'status_chance': r_sc,
                'crit_avg': average_crit_mult(r_cc_f, r_cd_f, vigilante_chance=vigilante_chance),
                'crit_chance': r_cc_f,
                'crit_mult': r_cd_f,
            }
        else:
            direct_modded_base = self._modded_base_per_pellet(w_meta, left, mod_dmg, r_dmg)

        status_res = self._compute_status_section(
            mod_objs,
            rv,
            result['elements'],
            direct_modded_base,
            final_ms,
            base_ms,
            final_cc,
            final_cd,
            final_status,
            final_fr,
            efr,
            exp_crit,
            r_faction,
            faction_by_name,
            shooting_prop,
            generic_faction=generic_faction,
            vigilante_chance=vigilante_chance,
            is_beam=is_beam,
            radial_status_input=radial_status_input,
        )
        result['status_dps'] = status_res['status_dps']
        result['status_sustained_dps'] = status_res['status_sustained_dps']
        result['slash_status_dps'] = status_res['slash_status_dps']
        result['slash_status_sustained_dps'] = status_res['slash_status_sustained_dps']
        result['non_slash_status_dps'] = status_res['non_slash_status_dps']
        result['non_slash_status_sustained_dps'] = status_res['non_slash_status_sustained_dps']
        result['hm_slash_dps'] = status_res['hm_slash_dps']
        result['status_breakdown'] = status_res['status_breakdown']
        result['faction_status_dps'] = status_res['faction_status_dps']
        result['burst_dps'] = direct_burst_dps + status_res['status_dps']
        result['sustained_dps'] = direct_sustained_dps + status_res['status_sustained_dps']

        if status_res['has_forced_bleed']:
            result['hunter_munitions'] = {
                'equipped': True,
                'bleed_tick': status_res['hm_bleed_tick'],
            }

        return result

    def compute_full_stack(
        self,
        w_meta: Dict[str, Any],
        left_stats: Optional[Dict[str, float]] = None,
        mod_objs: Optional[List[Dict[str, Any]]] = None,
        arcane: Optional[Dict[str, Any]] = None,
        combo_mult: float = 12.0,
        status_types: int = 3,
        riven_stats: Optional[Dict[str, float]] = None,
        target_faction: Optional[str] = None,
    ) -> Dict[str, Any]:
        from scripts.damage_formulas import average_crit_mult, effective_fire_rate, shooting_proportion, status_tick_damage, status_proc_total_damage

        prepared = self._prepare_mods(w_meta, mod_objs or [])
        # The riven slot marker stays in for compute_metrics: its slot decides where riven elements combine.
        mods = [m for m in prepared if m.get('name') != 'Riven Mod']
        rv = riven_stats or {}
        arc = arcane or {}
        base = self.compute_metrics(
            w_meta, left_stats=left_stats, mod_objs=prepared, riven_stats=rv,
            target_faction=target_faction, arcane=arc or None,
        )
        is_melee = str(w_meta.get('category') or '').strip().lower() == 'melee'
        is_beam = bool(base.get('is_beam'))
        is_bow = (not is_melee) and self._is_bow(w_meta)
        left = dict(left_stats or {})
        stacks = float(arc.get('max_stacks') or 0.0)
        trait = self._get_trait(w_meta)

        base_dmg = float(w_meta.get('total_damage') or 100.0)
        base_cc = float(w_meta.get('crit_chance', 0.1) or 0.0)
        if base_cc > 1.0:
            base_cc /= 100.0
        base_cd = float(w_meta.get('crit_mult', 1.5) or 1.5)
        base_ms = 1.0 if is_melee else max(1.0, float(w_meta.get('base_multishot') or 1.0))
        base_fr = max(0.01, float(w_meta.get('fire_rate', 1.0) or 1.0))
        base_status = self._resolve_base_status(w_meta)
        valence_total = self._valence(left)

        r_dmg = float(rv.get('damage', 0.0) or rv.get('base_damage', 0.0) or 0.0)
        mod_dmg_only = sum(float(mod.get('damage') or 0.0) for mod in mods)
        mod_dmg = mod_dmg_only + r_dmg
        mod_elem_only = sum(self._mod_elemental_total(mod) for mod in mods)
        r_elem_only = self._mod_elemental_total(rv)
        all_phys = {k: sum(float(mod.get(k) or 0.0) for mod in mods) + float(rv.get(k) or 0.0) for k in _PHYS}
        phys_frac = self._physical_bonus(w_meta, all_phys, left)
        mod_elem = mod_elem_only + r_elem_only + phys_frac

        mod_ms = 0.0 if base.get('lock_multishot') else sum(float(m.get('multishot') or 0.0) for m in mods)
        r_ms = 0.0 if base.get('lock_multishot') else float(rv.get('multishot') or 0.0)
        mod_cc = sum(float(m.get('crit_chance') or 0.0) for m in mods)
        r_cc = float(rv.get('crit_chance') or 0.0)
        mod_cd = sum(float(m.get('crit_damage') or 0.0) for m in mods)
        r_cd = float(rv.get('crit_damage') or 0.0)
        mod_status = sum(float(m.get('status') or m.get('status_chance') or 0.0) for m in mods)
        r_status = float(rv.get('status') or rv.get('status_chance') or 0.0)
        mod_flat_cc = sum(float(m.get('flat_crit_chance') or 0.0) for m in mods)
        mod_flat_cd = sum(float(m.get('flat_crit_damage') or 0.0) for m in mods)
        mod_flat_status = sum(float(m.get('flat_status') or 0.0) for m in mods)
        mod_fr = 0.0 if base.get('lock_fire_rate') else self._mod_fire_rate_sum(w_meta, mods)
        r_fr = 0.0 if base.get('lock_fire_rate') else float(rv.get('fire_rate') or 0.0)

        r_faction, generic_faction, faction_by_name = self._collect_faction_bonuses(
            mods, rv, target_faction=target_faction
        )

        # Effective status types for GunCO / Condition Overload (incl. hidden statuses like Kuva Nukor Microwave & Secondary Encumber).
        hidden_st = int(trait.get('hidden_status_types') or 0) + int(arc.get('extra_status_types') or 0)
        eff_status_types = max(0, int(status_types)) + hidden_st

        buff_dmg_non_gunco = float(arc.get('damage_per_stack') or 0.0) * stacks
        arc_mult_dmg = 1.0 + float(arc.get('multiplicative_damage') or 0.0) * (1.0 if stacks > 0 else 0.0)
        buff_elem = float(arc.get('elemental_per_stack') or 0.0) * stacks
        buff_ms = float(arc.get('multishot_per_stack') or 0.0) * stacks
        buff_cc = float(arc.get('crit_chance_per_stack') or 0.0) * stacks
        buff_cd = float(arc.get('crit_damage_per_stack') or 0.0) * stacks
        buff_sc = float(arc.get('status_per_stack') or 0.0) * stacks
        buff_fr = float(arc.get('fire_rate_per_stack') or arc.get('attack_speed_per_stack') or 0.0) * stacks
        buff_flat_cc = float(arc.get('flat_crit_chance_per_stack') or arc.get('flat_crit_per_stack') or 0.0) * stacks
        buff_flat_cd = float(arc.get('flat_crit_damage_per_stack') or 0.0) * stacks
        buff_flat_sc = float(arc.get('flat_status_per_stack') or 0.0) * stacks
        extra_initial_combo = float(arc.get('initial_combo_per_stack') or 0.0) * stacks
        gunco_bonus = float(trait.get('innate_gunco_per_status') or 0.0) * eff_status_types if not is_melee else 0.0
        has_weakpoint_mod = False

        for m in mods:
            for stat, total in _iter_conditional(m, 'on_kill'):
                if stat == 'damage':
                    buff_dmg_non_gunco += total
                elif stat == 'status_type_direct':
                    gunco_bonus += total * eff_status_types
                elif stat == 'multishot':
                    buff_ms += total
                elif stat == 'crit_chance':
                    buff_cc += total
                elif stat == 'crit_damage':
                    buff_cd += total
                elif stat in ('status', 'status_chance'):
                    buff_sc += total
                elif stat in ('attack_speed', 'fire_rate'):
                    buff_fr += total
                elif stat == 'initial_combo':
                    extra_initial_combo += total
            for stat, total in _iter_conditional(m, 'on_weakpoint'):
                has_weakpoint_mod = True
                if stat == 'crit_chance':
                    buff_cc += total
                elif stat == 'crit_damage':
                    buff_cd += total

        if is_melee:
            buff_cc += sum(float(m.get('combo_crit') or 0.0) for m in mods) * max(0.0, combo_mult - 1.0)
            buff_sc += sum(float(m.get('combo_status') or 0.0) for m in mods) * max(0.0, combo_mult - 1.0)
            buff_dmg_non_gunco += sum(float(m.get('status_type_damage') or 0.0) for m in mods) * eff_status_types

        if base.get('lock_fire_rate'):
            buff_fr = 0.0

        final_ms = base['final_ms']
        ms_ratio = 1.0
        if not is_melee and buff_ms and not base.get('lock_multishot'):
            new_ms = max(0.01, final_ms + base_ms * buff_ms)
            ms_ratio = new_ms / max(0.01, final_ms)
            final_ms = new_ms

        dmg_denom = max(0.01, 1.0 + mod_dmg)
        elem_denom = max(0.01, 1.0 + mod_elem)
        elem_ratio = max(0.01, 1.0 + mod_elem + buff_elem) / elem_denom

        is_mult_gunco = bool(trait.get('is_multiplicative_gunco')) and not is_melee
        split = self._primary_damage_split(w_meta)

        if is_mult_gunco:
            direct_dmg_ratio = (max(0.01, 1.0 + mod_dmg + buff_dmg_non_gunco) * max(0.0, 1.0 + gunco_bonus)) / dmg_denom
        else:
            direct_dmg_ratio = max(0.01, 1.0 + mod_dmg + buff_dmg_non_gunco + gunco_bonus) / dmg_denom
        aoe_dmg_ratio = max(0.01, 1.0 + mod_dmg + buff_dmg_non_gunco) / dmg_denom

        # Scope GunCO strictly to Direct portion on paired Direct + Radial weapons.
        if split['paired'] and (split['direct_base'] + split['radial_base']) > 0.0:
            d_w = split['direct_base'] / (split['direct_base'] + split['radial_base'])
            r_w = 1.0 - d_w
            eff_dmg_ratio = d_w * direct_dmg_ratio + r_w * aoe_dmg_ratio
        else:
            eff_dmg_ratio = direct_dmg_ratio

        final_dmg = base['final_dmg'] * eff_dmg_ratio * arc_mult_dmg * elem_ratio * ms_ratio
        final_cc = max(0.0, base['final_cc'] + base_cc * buff_cc + buff_flat_cc)
        final_status = max(0.0, base['final_status'] + base_status * buff_sc + buff_flat_sc)
        # Melee Doughty: +1.0x flat crit damage per 10% puncture status chance.
        doughty_flat_cd = 0.0
        if arc.get('puncture_status_to_cd') and base.get('elements'):
            punc_share = float((base['elements'].get('shares') or {}).get('puncture') or 0.0)
            doughty_flat_cd = float(arc['puncture_status_to_cd']) * (final_status * punc_share * 10.0)
        final_cd = max(1.0, base['final_cd'] + base_cd * buff_cd + buff_flat_cd + doughty_flat_cd)
        final_fr = max(0.1, base_fr * max(0.1, 1.0 + mod_fr + r_fr + buff_fr)) if buff_fr else base['final_fr']

        vigilante_chance = float(base.get('vigilante_chance') or 0.0)
        crit_avg = average_crit_mult(final_cc, final_cd, vigilante_chance=vigilante_chance)
        # Melee Duplicate: yellow crits (Tier 1) strike a second time.
        if is_melee and arc.get('yellow_crit_extra_hit') and 0.0 < final_cc < 2.0:
            p_yellow = final_cc if final_cc <= 1.0 else max(0.0, 2.0 - final_cc)
            crit_avg += p_yellow * float(arc['yellow_crit_extra_hit']) * final_cd
        faction = max(0.0, 1.0 + r_faction)
        expected_hit = final_dmg * crit_avg * faction

        if buff_fr:
            charge_time = float(left.get('charge_time') or 0.0)
            if not charge_time:
                db_charge = self._db_charge_time(w_meta)
                if db_charge > 0.0:
                    charge_time = db_charge * max(0.01, base_fr) / final_fr
            efr = effective_fire_rate(final_fr, charge_time, is_bow_charge=(is_bow and charge_time > 0.0))
        else:
            efr = base['effective_fire_rate']
        direct_burst_dps = expected_hit * efr

        if is_melee:
            shooting_prop = 1.0
        elif arc.get('reload_speed') or buff_fr:
            mag, reload_t = self._magazine_and_reload(w_meta, mods, rv)
            if arc.get('reload_speed') and reload_t > 0.0:
                raw_reload = w_meta.get('reloadTime')
                base_reload = 2.0 if raw_reload is None else max(0.01, float(raw_reload))
                new_rate = 1.0 / reload_t + float(arc['reload_speed']) / base_reload
                reload_t = 1.0 / max(new_rate, 0.01)
            shooting_prop = shooting_proportion(mag, efr, reload_t)
        else:
            shooting_prop = float(base.get('shooting_proportion') or 1.0)
        direct_sustained_dps = direct_burst_dps * shooting_prop

        full_elements = base.get('elements')
        arc_elem_name = str(arc.get('element') or 'corrosive').strip().lower()
        if full_elements and buff_elem > 0.0:
            # Arcane elemental bonus (e.g. Melee Exposure Corrosive) dilutes status weights without scaling DoT base.
            scale = elem_denom / max(0.01, elem_denom + buff_elem)
            new_shares = {k: v * scale for k, v in (full_elements.get('shares') or {}).items()}
            new_shares[arc_elem_name] = new_shares.get(arc_elem_name, 0.0) + buff_elem / max(0.01, elem_denom + buff_elem)
            full_elements = dict(full_elements, shares=new_shares)

        radial_status_input = None
        if split['paired']:
            base_direct_mb = self._modded_base_per_pellet(w_meta, left, mod_dmg, 0.0, base_override=split['direct_base'])
            full_direct_mb = base_direct_mb * direct_dmg_ratio * arc_mult_dmg
            base_rad_mb = self._modded_base_per_pellet(w_meta, left, mod_dmg, 0.0, base_override=split['radial_base'])
            full_rad_mb = base_rad_mb * aoe_dmg_ratio * arc_mult_dmg
            rad_atk = split['radial_atk']
            rad_el = self._elements_for_dist(split['radial_dist'], left, mods, rv, final_ms, is_melee)
            r_shares = (rad_el or {}).get('shares') or {}
            if buff_elem > 0.0 and r_shares:
                scale = elem_denom / max(0.01, elem_denom + buff_elem)
                r_shares = {k: v * scale for k, v in r_shares.items()}
                r_shares[arc_elem_name] = r_shares.get(arc_elem_name, 0.0) + buff_elem / max(0.01, elem_denom + buff_elem)
            raw_r_sc = rad_atk.get('status_chance') if isinstance(rad_atk, dict) else None
            r_base_sc = (float(raw_r_sc) / 100.0 if float(raw_r_sc) > 1.0 else float(raw_r_sc)) if raw_r_sc is not None else base_status
            r_sc = max(0.0, r_base_sc * (1.0 + mod_status + r_status + buff_sc) + mod_flat_status + buff_flat_sc)
            raw_r_cc = float(rad_atk.get('crit_chance') or 0.0) if isinstance(rad_atk, dict) else 0.0
            r_base_cc = (raw_r_cc / 100.0 if raw_r_cc > 1.0 else (raw_r_cc or base_cc))
            r_base_cd = float(rad_atk.get('crit_mult') or base_cd) if isinstance(rad_atk, dict) else base_cd
            r_cc_f = max(0.0, r_base_cc * (1.0 + mod_cc + r_cc + buff_cc) + mod_flat_cc + buff_flat_cc)
            r_cd_f = max(1.0, r_base_cd * (1.0 + mod_cd + r_cd + buff_cd) + mod_flat_cd + buff_flat_cd)
            radial_status_input = {
                'shares': r_shares,
                'modded_base': full_rad_mb,
                'status_chance': r_sc,
                'crit_avg': average_crit_mult(r_cc_f, r_cd_f, vigilante_chance=vigilante_chance),
                'crit_chance': r_cc_f,
                'crit_mult': r_cd_f,
            }
        else:
            base_modded_base = self._modded_base_per_pellet(w_meta, left, mod_dmg, 0.0)
            full_direct_mb = base_modded_base * direct_dmg_ratio * arc_mult_dmg

        status_res = self._compute_status_section(
            mods,
            rv,
            full_elements,
            full_direct_mb,
            final_ms,
            base_ms,
            final_cc,
            final_cd,
            final_status,
            final_fr,
            efr,
            crit_avg,
            r_faction,
            faction_by_name,
            shooting_prop,
            generic_faction=generic_faction,
            vigilante_chance=vigilante_chance,
            is_beam=is_beam,
            radial_status_input=radial_status_input,
        )
        burst_dps = direct_burst_dps + status_res['status_dps']
        sustained_dps = direct_sustained_dps + status_res['status_sustained_dps']

        assumptions = []
        if arc:
            assumptions.append(f"{arc.get('name', '아케인')} {int(stacks)}스택")
        if any(m.get('on_kill') for m in mods):
            assumptions.append('갈바나이즈드/온킬 최대 스택')
        if has_weakpoint_mod:
            assumptions.append('약점 조건부 치명타 활성')
        if is_melee:
            assumptions.append(f'연속기 {combo_mult:g}배')
        if (
            any(m.get('status_type_damage', 0.0) for m in mods)
            or any(s == 'status_type_direct' for m in mods for s, _ in _iter_conditional(m, 'on_kill'))
            or trait.get('innate_gunco_per_status')
        ):
            assumptions.append(f'상태이상 {eff_status_types}종')

        result: Dict[str, Any] = dict(
            burst_dps=burst_dps,
            sustained_dps=sustained_dps,
            direct_burst_dps=direct_burst_dps,
            direct_sustained_dps=direct_sustained_dps,
            status_dps=status_res['status_dps'],
            status_sustained_dps=status_res['status_sustained_dps'],
            slash_status_dps=status_res['slash_status_dps'],
            slash_status_sustained_dps=status_res['slash_status_sustained_dps'],
            non_slash_status_dps=status_res['non_slash_status_dps'],
            non_slash_status_sustained_dps=status_res['non_slash_status_sustained_dps'],
            hm_slash_dps=status_res['hm_slash_dps'],
            status_breakdown=status_res['status_breakdown'],
            faction_status_dps=status_res['faction_status_dps'],
            expected_hit=expected_hit,
            final_dmg=final_dmg,
            final_cc=final_cc,
            final_cd=final_cd,
            final_ms=final_ms,
            final_fr=final_fr,
            effective_fire_rate=efr,
            shooting_proportion=shooting_prop,
            final_status=final_status,
            assumptions=assumptions,
        )

        # Heavy attack (fix Melee Animosity * base_cc, include Killing Blow heavy_damage_bonus + initial combo + forced heavy proc)
        if is_melee and base.get('heavy'):
            heavy_cc_mod = sum(float(m.get('heavy_crit_chance') or 0.0) for m in mods)
            # Melee Animosity (+42%/stack up to +420%) is additive with crit mods (scales off base_cc), NOT flat!
            animosity_cc = base_cc * float(arc.get('heavy_crit_per_stack') or 0.0) * stacks
            heavy_cc = max(0.0, final_cc + base_cc * heavy_cc_mod + animosity_cc)

            heavy_dmg_bonus = sum(float(m.get('heavy_damage_bonus') or 0.0) for m in mods) + float(rv.get('heavy_damage_bonus') or 0.0)
            full_init_combo_mult = self._initial_combo_mult(mods, rv, extra_initial_combo=extra_initial_combo)
            eff_heavy_combo = max(float(combo_mult), full_init_combo_mult)

            # Recompute heavy base cleanly so Killing Blow stays additive with Pressure Point + Condition Overload.
            if left.get('heavy_damage'):
                heavy_ratio = (final_dmg / base['final_dmg']) if base['final_dmg'] else 1.0
                heavy_raw = float(left['heavy_damage']) * heavy_ratio * eff_heavy_combo
                heavy_modded_base = float(left['heavy_damage']) * direct_dmg_ratio * eff_heavy_combo
            elif w_meta.get('heavy_damage') and base_dmg > 0.0:
                heavy_base_val = float(w_meta['heavy_damage']) * (1.0 + valence_total)
                heavy_total_dmg_mult = max(0.0, 1.0 + mod_dmg + buff_dmg_non_gunco + heavy_dmg_bonus)
                heavy_total_elem_mult = max(0.0, 1.0 + mod_elem + buff_elem)
                heavy_raw = heavy_base_val * heavy_total_dmg_mult * heavy_total_elem_mult * eff_heavy_combo
                heavy_modded_base = heavy_base_val * heavy_total_dmg_mult * eff_heavy_combo
            else:
                heavy_ratio = (final_dmg / base['final_dmg']) if base['final_dmg'] else 1.0
                heavy_raw = base['heavy']['heavy_hit'] * heavy_ratio * eff_heavy_combo
                heavy_modded_base = full_direct_mb * eff_heavy_combo

            heavy_crit_avg = average_crit_mult(heavy_cc, final_cd)
            result['heavy_hit'] = heavy_raw * heavy_crit_avg * faction
            result['heavy_cc'] = heavy_cc
            forced_proc = trait.get('forced_heavy_proc')
            if forced_proc:
                sd_sum = sum(float(m.get('status_damage') or 0.0) for m in mods) + float(rv.get('status_damage') or 0.0)
                eb = sum(float(m.get(forced_proc) or 0.0) for m in mods) + float(rv.get(forced_proc) or 0.0)
                result['heavy_forced_proc'] = {
                    'type': forced_proc,
                    'tick': status_tick_damage(forced_proc, heavy_modded_base, faction=r_faction, status_damage=sd_sum, crit_avg=heavy_crit_avg, element_bonus=eb),
                    'total': status_proc_total_damage(forced_proc, heavy_modded_base, faction=r_faction, status_damage=sd_sum, crit_avg=heavy_crit_avg, element_bonus=eb),
                }

        if not is_melee:
            hs_bonus = (
                sum(float(m.get('headshot_bonus') or 0.0) for m in mods)
                + float(rv.get('headshot_bonus') or 0.0)
                + float(arc.get('headshot_bonus') or 0.0)
            )
            hs = self._headshot(
                final_dmg, final_dmg / max(0.01, final_ms), 1, 1, final_cc, final_cd, base_cc,
                sum(float(m.get('weak_point_damage') or 0.0) for m in mods) + float(rv.get('weak_point_damage') or 0.0),
                sum(float(m.get('weak_point_crit_chance') or 0.0) for m in mods) + float(rv.get('weak_point_crit_chance') or 0.0),
                hs_bonus,
                faction,
                vigilante_chance=vigilante_chance,
            )
            result['headshot_expected_hit'] = hs['expected_hit']
            result['headshot_burst_dps'] = hs['expected_hit'] * efr
            result['headshot_ratio'] = (hs['expected_hit'] / expected_hit) if expected_hit > 0.0 else 1.0

        # Full-stack Incarnon form (with Merciless/Galvanized/GunCO/Attrition)
        inc_full = self._compute_incarnon(
            w_meta, left, mods, rv,
            mod_dmg=mod_dmg_only, r_dmg=r_dmg,
            mod_elem_only=mod_elem_only, r_elem_only=r_elem_only,
            mod_phys_all=all_phys,
            mod_ms=mod_ms, r_ms=r_ms,
            mod_cc=mod_cc, r_cc=r_cc,
            mod_cd=mod_cd, r_cd=r_cd,
            mod_status=mod_status, r_status=r_status,
            mod_flat_cc=mod_flat_cc, mod_flat_cd=mod_flat_cd, mod_flat_status=mod_flat_status,
            mod_fr=mod_fr, r_fr=r_fr,
            lock_multishot=bool(base.get('lock_multishot')),
            lock_fire_rate=bool(base.get('lock_fire_rate')),
            faction=faction, r_faction=r_faction, vigilante_chance=vigilante_chance,
            base_cc=base_cc, base_cd=base_cd, base_fr=base_fr, base_status=base_status,
            buff_dmg=buff_dmg_non_gunco,
            gunco_bonus=gunco_bonus,
            is_mult_gunco=is_mult_gunco,
            buff_elem=buff_elem,
            buff_ms=0.0 if base.get('lock_multishot') else buff_ms,
            buff_cc=buff_cc,
            buff_cd=buff_cd,
            buff_sc=buff_sc,
            buff_fr=buff_fr,
            buff_flat_cc=buff_flat_cc,
            buff_flat_cd=buff_flat_cd,
            buff_flat_sc=buff_flat_sc,
        )
        if inc_full is not None:
            result['incarnon'] = inc_full

        return result

    def _apply_mod_sets(self, mods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if any(m.get('_set_applied') for m in mods):
            return mods

        counts: Dict[str, int] = {}
        for m in mods:
            s = m.get('modSet')
            if s:
                counts[s] = counts.get(s, 0) + 1

        out = []
        for m in mods:
            c = dict(m)
            c['_set_applied'] = True
            s = m.get('modSet')
            n = counts.get(s, 0) if s else 0
            values = m.get('modSetValues')

            if values and n >= 2 and n - 2 < len(values):
                factor = 1.0 + float(values[n - 2])
                if c.get('faction'):
                    # Wiki: Sacrificial set scales the bonus (+33% -> +41.25%), not (1 + bonus).
                    c['faction'] = {k: float(v) * factor for k, v in c['faction'].items()}
                for key in ('damage', 'multishot', 'crit_chance', 'crit_damage', 'fire_rate', 'status', 'elemental_damage', 'status_damage', 'heavy_crit_chance', 'slash', 'impact', 'puncture'):
                    if c.get(key):
                        c[key] = c[key] * factor

            if s and 'Gladiator' in str(s):
                c['combo_crit'] = c.get('combo_crit', 0.0) + 0.10

            out.append(c)

        return out

    def _elements_for_dist(
        self,
        dist: Dict[str, float],
        left: Dict[str, float],
        mod_objs: List[Dict[str, Any]],
        riven_stats: Dict[str, float],
        final_ms: float,
        is_melee: bool,
        *,
        first_attack_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        from scripts.damage_formulas import FACTION_MODIFIERS, combine_elements, faction_multipliers

        if not dist or sum(dist.values()) <= 0.0:
            return None

        base = dict(dist)
        base_total = sum(base.values())
        valence_total = self._valence(left)
        eff_base_total = base_total * (1.0 + valence_total)
        ms_factor = 1.0 if is_melee else final_ms

        rv = riven_stats or {}
        mods = self._prepare_mods({}, mod_objs or []) if not any(m.get('_set_applied') for m in (mod_objs or [])) else list(mod_objs or [])
        ordered = sorted(mods, key=lambda m: m.get('slot_index', 1000))
        order_known = all('slot_index' in m for m in mods if any(m.get(e) for e in _ALL_ELEMENTS))

        riven_elements = [k for k in rv if k in _ALL_ELEMENTS][::-1]
        sequence = []
        placed = False

        for m in ordered:
            if m.get('name') == 'Riven Mod':
                for k in riven_elements:
                    sequence.append((k, float(rv[k]) * eff_base_total))
                placed = True
                continue
            for el in _ALL_ELEMENTS:
                if m.get(el):
                    sequence.append((el, float(m[el]) * eff_base_total))

        if not placed:
            for k in riven_elements:
                sequence.append((k, float(rv[k]) * eff_base_total))

        innate = {k: v for k, v in base.items() if k in _ALL_ELEMENTS}
        # Valence Bonus joins innate base elements (or physical types for Impact Valence).
        valence_phys: Dict[str, float] = {}
        for k, v in (left or {}).items():
            if str(k).startswith('valence_'):
                el = str(k)[len('valence_'):].lower()
                target = valence_phys if el in _PHYS else innate
                target[el] = target.get(el, 0.0) + max(0.0, float(v or 0.0)) * base_total
        combined = combine_elements(sequence, innate)

        mod_dmg = sum(float(m.get('damage') or 0.0) for m in mods if m.get('name') != 'Riven Mod') + float(rv.get('damage', 0.0) or rv.get('base_damage', 0.0) or 0.0)
        factor = max(0.0, 1.0 + mod_dmg) * ms_factor

        types: Dict[str, float] = {}
        for t in _PHYS:
            if base.get(t) or valence_phys.get(t):
                bonus = sum(float(m.get(t) or 0.0) for m in mods if m.get('name') != 'Riven Mod') + float(rv.get(t) or 0.0)
                # Impact Valence is part of base Impact, so Impact mods scale both base and Valence Impact.
                types[t] = (base.get(t, 0.0) + valence_phys.get(t, 0.0)) * max(0.0, 1.0 + bonus) * factor

        for t, v in combined['types'].items():
            types[t] = v * factor

        for k, v in base.items():
            if k not in _ALL_ELEMENTS and k not in _PHYS:
                types[k] = v * factor

        total = sum(types.values()) or 1.0
        shares = {t: d / total for t, d in types.items()}

        faction_bonus: Dict[str, float] = {}
        for m in mods:
            for name, val in (m.get('faction') or {}).items():
                key = {'sentients': 'sentient', 'corrupted': 'orokin'}.get(str(name).lower(), str(name).lower())
                faction_bonus[key] = faction_bonus.get(key, 0.0) + float(val)
        generic_fac = float(rv.get('faction_damage') or 0.0) + sum(
            float(m.get('faction_damage') or 0.0) for m in mods if m.get('name') != 'Riven Mod'
        )
        if generic_fac:
            for fac in FACTION_MODIFIERS:
                faction_bonus[fac] = faction_bonus.get(fac, 0.0) + generic_fac

        return dict(
            types=types,
            shares=shares,
            pairs=combined['pairs'],
            order=combined['order'],
            first_attack_only=first_attack_only,
            order_known=order_known,
            faction_multipliers=faction_multipliers(types, faction_bonus),
        )

    def compute_elements(self, w_meta: Dict[str, Any], left: Dict[str, float], mod_objs: List[Dict[str, Any]], riven_stats: Dict[str, float], final_ms: float) -> Optional[Dict[str, Any]]:
        attacks = w_meta.get('attacks') or []
        dist = _norm_dist(attacks[0].get('damage')) if attacks and isinstance(attacks[0], dict) else {}
        if not dist:
            return None

        base_total = sum(dist.values())
        first_attack_only = abs(float(w_meta.get('total_damage') or base_total) - base_total) > 0.01 * base_total
        is_melee = str(w_meta.get('category') or '').strip().lower() == 'melee'
        mods = self._prepare_mods(w_meta, mod_objs or [])
        return self._elements_for_dist(
            dist, left, mods, riven_stats or {}, final_ms, is_melee,
            first_attack_only=first_attack_only,
        )
