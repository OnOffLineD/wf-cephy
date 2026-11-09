import math
from typing import Dict, Any, Optional, List

from scripts.innate_traits import apply_innate_traits, describe as describe_innate

class WarframeDamageEngine:
    def _prepare_mods(self, w_meta: Dict[str, Any], mods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Mods as the weapon applies them: set bonuses first, then the weapon's innate trait."""
        return apply_innate_traits(w_meta, self._apply_mod_sets(mods))

    def sanitize_left_stats(self, left_stats: Dict[str, float], base_damage: float, is_melee: bool = False) -> Dict[str, float]:
        sanitized_stats = left_stats.copy()
    
        if is_melee:
            sanitized_stats.pop('multishot', None)
    
        total_damage = sanitized_stats.get('total_damage', 0.0)
        if total_damage < base_damage * 0.3:
            s_val = str(total_damage)
            parts = s_val.split('.')
            if len(parts) > 1 and len(parts[1]) >= 3 and (total_damage * 1000.0) >= base_damage * 0.4:
                sanitized_stats['total_damage'] = total_damage * 1000.0
            else:
                sanitized_stats.pop('total_damage', None)
    
        return sanitized_stats

    def _magazine_and_reload(self, w_meta: Dict[str, Any], left: Dict[str, float], mods: List[Dict[str, Any]], rv: Dict[str, float], add_r: bool) -> Any:
        base_mag = float(w_meta.get('magazineSize') or 30.0)
        base_reload = float(w_meta.get('reloadTime') or 2.0)
        r_mag = rv.get('magazine_capacity', 0.0)
        r_reload = rv.get('reload_speed', 0.0)
        if left.get('magazine'):
            mag = float(left['magazine']) + (base_mag * r_mag if add_r else 0.0)
        else:
            mag = base_mag * (1.0 + sum(m.get('magazine_capacity', 0.0) for m in mods) + r_mag)
        # Reload speed adds up as a rate, so a panel time is converted to a rate first.
        if left.get('reload_time'):
            rate = 1.0 / float(left['reload_time']) + (r_reload / base_reload if add_r else 0.0)
        else:
            rate = (1.0 + sum(m.get('reload_speed', 0.0) for m in mods) + r_reload) / base_reload
        return max(1.0, mag), 1.0 / max(rate, 0.01)

    @staticmethod
    def _valence(stats: Optional[Dict[str, float]]) -> float:
        return sum(v for k, v in (stats or {}).items() if k.startswith('valence_'))

    def _physical_bonus(self, w_meta: Dict[str, Any], values: Dict[str, float]) -> float:
        attacks = w_meta.get('attacks') or []
        dist = attacks[0].get('damage') if attacks and isinstance(attacks[0].get('damage'), dict) else {}
        total = sum(dist.values()) or 1.0
        return sum(dist.get(k, 0.0) / total * v for k, v in values.items())

    def compute_metrics(self, w_meta: Dict[str, Any], left_stats: Optional[Dict[str, float]] = None, mod_objs: Optional[List[Dict[str, Any]]] = None, riven_stats: Optional[Dict[str, float]] = None, riven_in_panel: bool = False) -> Dict[str, Any]:
        from scripts.damage_formulas import effective_fire_rate, shooting_proportion, bleed_tick, weak_point_multiplier

        mod_objs = self._prepare_mods(w_meta, mod_objs or [])
        mod_dmg = sum(mod.get('damage', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_ms =sum(mod.get('multishot', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_cc = sum(mod.get('crit_chance', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_cd = sum(mod.get('crit_damage', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_fr = sum(mod.get('fire_rate', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_elem = sum(mod.get('elemental_damage', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_phys = {
            'slash': sum(mod.get('slash', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod'),
            'impact': sum(mod.get('impact', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod'),
            'puncture': sum(mod.get('puncture', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        }

        rv = riven_stats or {}
        r_dmg = rv.get('damage', 0.0) or rv.get('base_damage', 0.0)
        r_ms = rv.get('multishot', 0.0)
        # Acuity mods: "Multishot cannot be modified."
        lock_multishot = any(mod.get('lock_multishot') or 'acuity' in str(mod.get('name', '')).lower() for mod in mod_objs)
        if lock_multishot:
            mod_ms = 0.0
            r_ms = 0.0
        mod_wp_dmg = sum(mod.get('weak_point_damage', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_wp_cc = sum(mod.get('weak_point_crit_chance', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        r_wp_dmg = rv.get('weak_point_damage', 0.0)
        mod_wp_cc += rv.get('weak_point_crit_chance', 0.0)
        r_cc = rv.get('crit_chance', 0.0)
        r_cd = rv.get('crit_damage', 0.0)
        r_fr = rv.get('fire_rate', 0.0)
        r_elem = rv.get('elemental_damage', 0.0)
        r_faction = rv.get('faction_damage', 0.0)
        r_phys = {
            'slash': rv.get('slash', 0.0),
            'impact': rv.get('impact', 0.0),
            'puncture': rv.get('puncture', 0.0)
        }

        is_melee = w_meta.get('category') == 'Melee'
        left = dict(left_stats or {})
        base_dmg = float(w_meta.get('total_damage') or left.get('total_damage') or 100.0)
        base_ms = float(w_meta.get('base_multishot') or 1.0)
        if left:
            left = self.sanitize_left_stats(left, base_dmg, is_melee)
        add_r = not riven_in_panel

        # Wiki arsenal total: physical mods scale by the weapon's share of that type, in the elemental bracket.
        mod_elem += self._physical_bonus(w_meta, mod_phys)
        r_elem += self._physical_bonus(w_meta, r_phys)
        mod_elem += self._valence(left)

        base_cc = float(w_meta.get('crit_chance', 0.1))
        if base_cc > 1.0:
            base_cc /= 100.0
        base_cd = float(w_meta.get('crit_mult', 1.5))
        base_fr = float(w_meta.get('fire_rate', 1.0))

        if is_melee:
            final_ms = 1.0
        elif lock_multishot:
            final_ms = base_ms
        elif left.get('multishot'):
            final_ms = float(left['multishot']) + (base_ms * r_ms if add_r else 0.0)
        else:
            final_ms = base_ms * (1.0 + mod_ms + r_ms)
        final_ms = max(0.1, final_ms)

        used_panel_total = bool(left.get('total_damage'))
        if used_panel_total:
            final_dmg = float(left['total_damage'])
            if add_r and rv:
                final_dmg *= (1.0 + mod_dmg + r_dmg) / (1.0 + mod_dmg) * (1.0 + mod_elem + r_elem) / (1.0 + mod_elem)
                if not is_melee and r_ms:
                    final_dmg *= final_ms / max(0.1, final_ms - base_ms * r_ms)
        else:
            ms_factor = 1.0 if is_melee else final_ms / base_ms
            final_dmg = base_dmg * (1.0 + mod_dmg + r_dmg) * (1.0 + mod_elem + r_elem) * ms_factor

        if left.get('crit_chance'):
            final_cc = float(left['crit_chance']) + (base_cc * r_cc if add_r else 0.0)
        else:
            final_cc = base_cc * (1.0 + mod_cc + r_cc)
        final_cc = max(0.0, final_cc)

        if left.get('crit_mult'):
            final_cd = float(left['crit_mult']) + (base_cd * r_cd if add_r else 0.0)
        else:
            final_cd = base_cd * (1.0 + mod_cd + r_cd)
        final_cd = max(1.0, final_cd)

        if left.get('fire_rate'):
            final_fr = float(left['fire_rate']) + (base_fr * r_fr if add_r else 0.0)
        else:
            final_fr = base_fr * (1.0 + mod_fr + r_fr)
        final_fr = max(0.1, final_fr)

        exp_crit = 1.0 + final_cc * (final_cd - 1.0)
        min_crit = 1.0 + int(final_cc) * (final_cd - 1.0)
        max_crit = 1.0 + int(math.ceil(final_cc)) * (final_cd - 1.0)
        faction = 1.0 + r_faction

        per_pellet = final_dmg / final_ms
        if not is_melee and final_ms > 1.0:
            ms_min = max(1, int(math.floor(final_ms)))
            ms_max = max(1, int(math.ceil(final_ms)))
            ms_extra = round((final_ms - math.floor(final_ms)) * 100.0, 1)
        else:
            ms_min = 1
            ms_max = 1
            ms_extra = 0.0
            per_pellet = final_dmg

        min_hit = per_pellet * ms_min * min_crit * faction
        max_non_crit = per_pellet * ms_max * faction
        max_crit_hit = per_pellet * ms_max * max_crit * faction
        expected_hit = final_dmg * exp_crit * faction
        efr = effective_fire_rate(final_fr, float(left.get('charge_time') or 0.0))
        burst_dps = expected_hit * efr

        # Weak point / headshot: crit on a weak point gets the extra 2x headcrit multiplier.
        if is_melee:
            wp_mult = 1.0
            final_cc_wp = final_cc
            headshot_max_crit_hit = max_crit_hit
            headshot_min_hit = min_hit
            headshot_expected_hit = expected_hit
            headshot_burst_dps = burst_dps
        else:
            wp_mult = weak_point_multiplier(3.0, mod_wp_dmg + r_wp_dmg, rv.get('headshot_bonus', 0.0), is_headshot=True)
            final_cc_wp = max(0.0, final_cc + base_cc * mod_wp_cc)
            max_crit_wp = 1.0 + int(math.ceil(final_cc_wp)) * (final_cd - 1.0)
            min_crit_wp = 1.0 + int(final_cc_wp) * (final_cd - 1.0)
            exp_crit_wp = 1.0 + final_cc_wp * (final_cd - 1.0)
            headshot_max_crit_hit = per_pellet * ms_max * wp_mult * max_crit_wp * 2.0 * faction
            headshot_min_hit = per_pellet * ms_min * wp_mult * min_crit_wp * 2.0 * faction
            headshot_expected_hit = final_dmg * wp_mult * exp_crit_wp * 2.0 * faction
            headshot_burst_dps = headshot_expected_hit * efr

        if is_melee:
            sustained_dps = burst_dps
        else:
            mag, reload_t = self._magazine_and_reload(w_meta, left, mod_objs, rv, add_r)
            sustained_dps = burst_dps * shooting_proportion(mag, efr, reload_t)

        result = {
            "final_dmg": final_dmg,
            "final_cc": final_cc,
            "final_cd": final_cd,
            "final_fr": final_fr,
            "final_ms": final_ms,
            "min_hit": min_hit,
            "max_non_crit": max_non_crit,
            "max_crit_hit": max_crit_hit,
            "expected_hit": expected_hit,
            "burst_dps": burst_dps,
            "sustained_dps": sustained_dps,
            "per_pellet_dmg": per_pellet,
            "ms_min_pellets": ms_min,
            "ms_max_pellets": ms_max,
            "ms_extra_pct": ms_extra,
            "used_panel_total": used_panel_total,
            "effective_fire_rate": efr,
            "wp_mult": wp_mult,
            "final_cc_wp": final_cc_wp,
            "headshot_max_crit_hit": headshot_max_crit_hit,
            "headshot_min_hit": headshot_min_hit,
            "headshot_expected_hit": headshot_expected_hit,
            "headshot_burst_dps": headshot_burst_dps,
            "lock_multishot": lock_multishot,
            "innate": describe_innate(w_meta, mod_objs, left)
        }

        # Panel type rows don't include a riven that is added on top of them.
        element_left = left if riven_in_panel or not rv else {k: v for k, v in left.items() if not k.startswith('el_')}
        result['elements'] = self.compute_elements(w_meta, element_left, mod_objs, rv, final_ms, final_dmg)

        if left.get('slam_damage'):
            result['radial'] = {'base_damage': left['slam_damage']}
        elif w_meta.get('radial_attack'):
            rad = sum(w_meta['radial_attack'].get('damage', {}).values())
            if is_melee and base_dmg > 0:
                rad *= final_dmg / base_dmg
            result['radial'] = {'base_damage': rad}

        if left.get('heavy_damage'):
            result['heavy'] = {'heavy_hit': left['heavy_damage']}

        for atk in w_meta.get('attacks', []):
            if atk.get('name') == 'Energy Disk':
                damage = sum(atk.get('damage', {}).values())
                if base_dmg > 0:
                    damage *= final_dmg / base_dmg
                result['energy_disk'] = {'damage': damage}
                break

        if w_meta.get('incarnon_attack'):
            inc = w_meta['incarnon_attack']
            inc_base = sum(inc.get('damage', {}).values())
            inc_cc = float(inc.get('crit_chance') or 0)
            inc_cc = inc_cc / 100.0 if inc_cc > 1.0 else (inc_cc or base_cc)
            inc_cd = float(inc.get('crit_mult') or base_cd)
            inc_fr = float(inc.get('speed') or base_fr)
            inc_hit = inc_base * (1.0 + mod_dmg + r_dmg) * (1.0 + mod_elem + r_elem) * (1.0 + mod_ms + r_ms) * (1.0 + inc_cc * (1.0 + mod_cc + r_cc) * (inc_cd * (1.0 + mod_cd + r_cd) - 1.0)) * faction
            result['incarnon'] = {
                'expected_hit': inc_hit,
                'burst_dps': inc_hit * inc_fr * (1.0 + mod_fr + r_fr),
                'attack_meta': inc
            }

        if any('Hunter Munitions' in mod.get('name', '') or 'Internal Bleeding' in mod.get('name', '') for mod in mod_objs):
            status_damage_sum = sum(mod.get('status_damage', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
            result['hunter_munitions'] = {
                'equipped': True,
                'bleed_tick': bleed_tick(base_dmg / base_ms * (1.0 + mod_dmg + r_dmg), r_faction, status_damage_sum, exp_crit)
            }

        return result

    def strip_riven_from_panel(self, left_stats: Dict[str, float], w_meta: Dict[str, Any], mod_objs: Optional[List[Dict[str, Any]]], riven_stats: Dict[str, float]) -> Dict[str, float]:
        is_melee = w_meta.get('category') == 'Melee'
        base_dmg = float(w_meta.get('total_damage') or left_stats.get('total_damage') or 100.0)
        out = self.sanitize_left_stats(dict(left_stats), base_dmg, is_melee)
        if not out or not riven_stats:
            return out
    
        mod_objs = self._prepare_mods(w_meta, mod_objs or [])
        mod_dmg = sum(mod.get('damage', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_elem =sum(mod.get('elemental_damage', 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod')
        mod_elem += self._physical_bonus(w_meta, {k: sum(mod.get(k, 0.0) for mod in mod_objs if mod.get('name') != 'Riven Mod') for k in ('slash', 'impact', 'puncture')})
        mod_elem += self._valence(left_stats)

        r_dmg = riven_stats.get('damage', 0.0) or riven_stats.get('base_damage', 0.0)
        r_ms = riven_stats.get('multishot', 0.0)
        r_cc = riven_stats.get('crit_chance', 0.0)
        r_cd = riven_stats.get('crit_damage', 0.0)
        r_fr = riven_stats.get('fire_rate', 0.0)
        r_elem = riven_stats.get('elemental_damage', 0.0) + self._physical_bonus(w_meta, {k: riven_stats.get(k, 0.0) for k in ('slash', 'impact', 'puncture')})

        base_ms = float(w_meta.get('base_multishot') or 1.0)
        base_cc = float(w_meta.get('crit_chance', 0.1))
        if base_cc > 1.0:
            base_cc /= 100.0
        base_cd = float(w_meta.get('crit_mult', 1.5))
        base_fr = float(w_meta.get('fire_rate', 1.0))
    
        ms_ratio = 1.0
        if not is_melee and out.get('multishot') and r_ms:
            without = max(1.0, out['multishot'] - base_ms * r_ms)
            ms_ratio = out['multishot'] / without
            out['multishot'] = without
    
        if out.get('total_damage'):
            divisor = (1.0 + mod_dmg + r_dmg) / (1.0 + mod_dmg) * (1.0 + mod_elem + r_elem) / (1.0 + mod_elem) * ms_ratio
            if divisor > 0:
                out['total_damage'] = out['total_damage'] / divisor
    
        if out.get('crit_chance'):
            out['crit_chance'] = max(0.0, out['crit_chance'] - base_cc * r_cc)
    
        if out.get('crit_mult'):
            out['crit_mult'] = max(1.0, out['crit_mult'] - base_cd * r_cd)
    
        if out.get('fire_rate'):
            out['fire_rate'] = max(0.05, out['fire_rate'] - base_fr * r_fr)

        if out.get('magazine'):
            out['magazine'] = max(1.0, out['magazine'] - float(w_meta.get('magazineSize') or 30.0) * riven_stats.get('magazine_capacity', 0.0))

        if out.get('reload_time'):
            rate = 1.0 / out['reload_time'] - riven_stats.get('reload_speed', 0.0) / float(w_meta.get('reloadTime') or 2.0)
            out['reload_time'] = 1.0 / max(rate, 0.01)

        # Type rows show the build with the removed stats, so they no longer describe what remains.
        out = {k: v for k, v in out.items() if not k.startswith('el_')}
    
        return out

    def compute_full_stack(self, w_meta: Dict[str, Any], left_stats: Optional[Dict[str, float]] = None, mod_objs: Optional[List[Dict[str, Any]]] = None, arcane: Optional[Dict[str, Any]] = None, combo_mult: float = 12.0, status_types: int = 3, riven_stats: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        from scripts.damage_formulas import average_crit_mult, effective_fire_rate, weak_point_multiplier
    
        mods = [m for m in self._prepare_mods(w_meta, mod_objs or []) if m.get('name') != 'Riven Mod']
        rv = riven_stats or {}
        base = self.compute_metrics(w_meta, left_stats=left_stats, mod_objs=mods, riven_stats=rv)
        is_melee = w_meta.get('category') == 'Melee'
        arc = arcane or dict()
        stacks = float(arc.get('max_stacks') or 0)
    
        base_cc = float(w_meta.get('crit_chance', 0.1))
        if base_cc > 1.0:
            base_cc /= 100.0
        base_cd = float(w_meta.get('crit_mult', 1.5))
        base_ms = float(w_meta.get('base_multishot') or 1.0)
    
        # The riven shares these buckets, so buffs are measured against the total with it included.
        mod_dmg = sum(mod.get('damage', 0.0) for mod in mods) + (rv.get('damage', 0.0) or rv.get('base_damage', 0.0))
        mod_elem = sum(mod.get('elemental_damage', 0.0) for mod in mods) + rv.get('elemental_damage', 0.0)
        mod_elem += self._physical_bonus(w_meta, {k: sum(mod.get(k, 0.0) for mod in mods) + rv.get(k, 0.0) for k in ('slash', 'impact', 'puncture')})
        # The Valence Bonus shares the elemental bucket, so a buff there is measured against it too.
        mod_elem += self._valence(left_stats)

        buff_dmg =float(arc.get('damage_per_stack') or 0) * stacks
        buff_elem = float(arc.get('elemental_per_stack') or 0) * stacks
        buff_ms = buff_cc = buff_cd = 0.0
    
        for m in mods:
            for e in m.get('on_kill', []):
                total = e['value'] * e['stacks']
                stat = e['stat']
                if stat == 'damage':
                    buff_dmg += total
                elif stat == 'status_type_direct':
                    buff_dmg += total * status_types
                elif stat == 'multishot':
                    buff_ms += total
                elif stat == 'crit_chance':
                    buff_cc += total
                elif stat == 'crit_damage':
                    buff_cd += total
    
        if is_melee:
            buff_cc += sum(m.get('combo_crit', 0.0) for m in mods) * (combo_mult - 1.0)
            buff_dmg += sum(m.get('status_type_damage', 0.0) for m in mods) * status_types
    
        final_ms = base['final_ms']
        ms_ratio = 1.0
        if not is_melee and buff_ms:
            new_ms = final_ms + base_ms * buff_ms
            ms_ratio = new_ms / final_ms
            final_ms = new_ms
    
        final_dmg = base['final_dmg'] * (1.0 + mod_dmg + buff_dmg) / (1.0 + mod_dmg) * (1.0 + mod_elem + buff_elem) / (1.0 + mod_elem) * ms_ratio
        final_cc = base['final_cc'] + base_cc * buff_cc
        final_cd = base['final_cd'] + base_cd * buff_cd
        crit_avg = average_crit_mult(final_cc, final_cd)
        expected_hit = final_dmg * crit_avg
        burst_dps = expected_hit * base['effective_fire_rate']
    
        assumptions = []
        if arc:
            assumptions.append(f"{arc.get('name', '아케인')} {int(stacks)}스택")
        if any(m.get('on_kill', []) for m in mods):
            assumptions.append('갈바나이즈드 최대 스택')
        if is_melee:
            assumptions.append(f'연속기 {combo_mult:g}배')
        if any(m.get('status_type_damage', 0.0) for m in mods) or any(e['stat'] == 'status_type_direct' for m in mods for e in m.get('on_kill', [])):
            assumptions.append(f'상태이상 {status_types}종')
    
        result = dict(
            burst_dps=burst_dps,
            expected_hit=expected_hit,
            final_dmg=final_dmg,
            final_cc=final_cc,
            final_cd=final_cd,
            final_ms=final_ms,
            assumptions=assumptions
        )
    
        if is_melee and base.get('heavy'):
            heavy_cc = final_cc + base_cc * sum(m.get('heavy_crit_chance', 0.0) for m in mods) + float(arc.get('heavy_crit_per_stack') or 0) * stacks
            heavy_ratio = final_dmg / base['final_dmg'] if base['final_dmg'] else 1.0
            result['heavy_hit'] = base['heavy']['heavy_hit'] * heavy_ratio * combo_mult * average_crit_mult(heavy_cc, final_cd)
    
        if not is_melee:
            wp = weak_point_multiplier(3.0, sum(m.get('weak_point_damage', 0.0) for m in mods), float(arc.get('headshot_bonus') or 0.0), True)
            result['headshot_burst_dps'] = final_dmg * wp * average_crit_mult(final_cc, final_cd * 2.0) * base['effective_fire_rate']
    
        return result

    def _apply_mod_sets(self, mods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if any(m.get('_set_applied') for m in mods):
            return mods
    
        counts = {}
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
                    c['faction'] = {k: (1.0 + v) * factor - 1.0 for k, v in c['faction'].items()}
                for key in ('damage', 'multishot', 'crit_chance', 'crit_damage', 'fire_rate', 'status', 'elemental_damage', 'status_damage', 'heavy_crit_chance', 'slash', 'impact', 'puncture'):
                    if c.get(key):
                        c[key] = c[key] * factor
    
            if s and 'Gladiator' in str(s):
                c['combo_crit'] = c.get('combo_crit', 0.0) + 0.10
    
            out.append(c)
    
        return out

    def compute_elements(self, w_meta: Dict[str, Any], left: Dict[str, float], mod_objs: List[Dict[str, Any]], riven_stats: Dict[str, float], final_ms: float, final_dmg: float) -> Optional[Dict[str, Any]]:
            from scripts.damage_formulas import combine_elements, faction_multipliers
    
            ALL = ('heat', 'cold', 'electric', 'toxin', 'blast', 'radiation', 'gas', 'magnetic', 'viral', 'corrosive')
            PHYS = ('impact', 'puncture', 'slash')
    
            attacks = w_meta.get('attacks') or []
            dist = attacks[0].get('damage') if attacks and isinstance(attacks[0].get('damage'), dict) else None
    
            if not dist or sum(dist.values()) <= 0:
                return None
    
            # Only the first attack is broken down: total_damage may also include explosions or other modes.
            dist = {('electric' if k == 'electricity' else k): v for k, v in dist.items()}
            base_total = sum(dist.values())
            base = {k: v for k, v in dist.items() if v}
            first_attack_only = abs(float(w_meta.get('total_damage') or base_total) - base_total) > 0.01 * base_total

            is_melee = w_meta.get('category') == 'Melee'
            base_ms = float(w_meta.get('base_multishot') or 1.0)
            ms_factor = 1.0 if is_melee else final_ms / base_ms
    
            rv = riven_stats or {}
            mods = self._prepare_mods(w_meta, mod_objs or [])
            ordered =sorted(mods, key=lambda m: m.get('slot_index', 1000))
            order_known = all('slot_index' in m for m in mods if any(m.get(e) for e in ALL))
    
            riven_elements = [k for k in rv if k in ALL][::-1]
            sequence = []
            placed = False
    
            for m in ordered:
                if m.get('name') == 'Riven Mod':
                    for k in riven_elements:
                        sequence.append((k, rv[k] * base_total))
                    placed = True
                    continue
                for el in ALL:
                    if m.get(el):
                        sequence.append((el, m[el] * base_total))
    
            if not placed:
                for k in riven_elements:
                    sequence.append((k, rv[k] * base_total))
    
            innate = {k: v for k, v in base.items() if k in ALL}
            # An impact Valence Bonus adds impact, so it joins the physical rows instead of the elements.
            valence_phys = {}
            for k, v in left.items():
                if k.startswith('valence_'):
                    el = k[len('valence_'):]
                    target = valence_phys if el in PHYS else innate
                    target[el] = target.get(el, 0.0) + v * base_total
            combined = combine_elements(sequence, innate)
    
            mod_dmg = sum(m.get('damage', 0.0) for m in mods if m.get('name') != 'Riven Mod') + (rv.get('damage', 0.0) or rv.get('base_damage', 0.0))
            factor = (1.0 + mod_dmg) * ms_factor
    
            types = {}
            for t in PHYS:
                if base.get(t) or valence_phys.get(t):
                    bonus = sum(m.get(t, 0.0) for m in mods) + rv.get(t, 0.0)
                    types[t] = (base.get(t, 0.0) * (1.0 + bonus) + valence_phys.get(t, 0.0)) * factor
    
            for t, v in combined['types'].items():
                types[t] = v * factor
    
            for k, v in base.items():
                if k not in ALL and k not in PHYS:
                    types[k] = v * factor
    
            source = 'computed'
            # Panel type rows are per projectile; only the total row includes multishot.
            panel = {k[3:]: v * final_ms for k, v in left.items() if k.startswith('el_')}
            total_panel = left.get('total_damage')
            if panel and total_panel and abs(sum(panel.values()) - total_panel) <= 0.03 * total_panel:
                types = panel
                source = 'panel'
            else:
                resolved = False
                if panel and total_panel:
                    missing = [t for t in types if t not in panel]
                    if not missing and types:
                        smallest = min(panel, key=panel.get)
                        missing = [smallest] if smallest in types else []
                    if len(missing) == 1:
                        others = sum(v for t, v in panel.items() if t != missing[0])
                        residual = total_panel - others
                        if residual > 0 and all(t in types for t in panel):
                            types = {t: v for t, v in panel.items() if t != missing[0]}
                            types[missing[0]] = residual
                            source = 'panel'
                            resolved = True
                if not resolved:
                    current = sum(types.values())
                    if current > 0 and final_dmg > 0 and total_panel:
                        ratio = final_dmg / current
                        types = {t: d * ratio for t, d in types.items()}
                    elif panel and not total_panel:
                        # Total row scrolled out of view: anchor the estimate to the rows that are visible.
                        ratios = sorted(panel[t] / types[t] for t in panel if types.get(t))
                        if ratios:
                            ratio = ratios[len(ratios) // 2]
                            types = {t: panel.get(t, d * ratio) for t, d in types.items()}
                            source = 'panel_partial'

            total = sum(types.values()) or 1.0
            shares = {t: d / total for t, d in types.items()}
    
            faction_bonus = {}
            for m in mods:
                for name, val in (m.get('faction') or {}).items():
                    key = {'sentients': 'sentient', 'corrupted': 'orokin'}.get(name, name)
                    faction_bonus[key] = faction_bonus.get(key, 0.0) + val
    
            return dict(
                types=types,
                shares=shares,
                pairs=combined['pairs'],
                order=combined['order'],
                source=source,
                first_attack_only=first_attack_only,
                order_known=order_known,
                faction_multipliers=faction_multipliers(types, faction_bonus)
            )

