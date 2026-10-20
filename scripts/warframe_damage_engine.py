import math
from typing import Dict, Any, Optional, List

class WarframeDamageEngine:
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

    def compute_metrics(self, w_meta: Dict[str, Any], left_stats: Optional[Dict[str, float]] = None, mod_objs: Optional[List[Dict[str, Any]]] = None, riven_stats: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        mod_dmg = 0.0
        mod_ms = 0.0
        mod_cc = 0.0
        mod_cd = 0.0
        mod_fr = 0.0
        mod_elem = 0.0

        if mod_objs:
            for mod in mod_objs:
                mod_dmg += mod.get('damage', 0.0)
                mod_ms += mod.get('multishot', 0.0)
                mod_cc += mod.get('crit_chance', 0.0)
                mod_cd += mod.get('crit_damage', 0.0)
                mod_fr += mod.get('fire_rate', 0.0)
                mod_elem += mod.get('elemental_damage', 0.0)

        if riven_stats:
            r_dmg = riven_stats.get('damage', 0.0) or riven_stats.get('base_damage', 0.0)
            r_ms = riven_stats.get('multishot', 0.0)
            r_cc = riven_stats.get('crit_chance', 0.0)
            r_cd = riven_stats.get('crit_damage', 0.0)
            r_fr = riven_stats.get('fire_rate', 0.0)
            r_elem = riven_stats.get('elemental_damage', 0.0)
            r_faction = riven_stats.get('faction_damage', 0.0)
            mod_dmg += r_dmg
            mod_ms += r_ms
            mod_cc += r_cc
            mod_cd += r_cd
            mod_fr += r_fr
            mod_elem += r_elem
        else:
            r_faction = 0.0

        is_melee = (w_meta.get('category') == 'Melee')
        base_dmg = float(w_meta.get('total_damage', 0.0) or left_stats.get('total_damage', 100.0) if left_stats else 100.0)

        if left_stats:
            left_stats = self.sanitize_left_stats(left_stats, base_dmg, is_melee)

        if left_stats and 'total_damage' in left_stats:
            final_dmg = float(left_stats['total_damage']) * (1.0 + (r_dmg if riven_stats else 0.0)) * (1.0 + (r_elem if riven_stats else 0.0))
        else:
            final_dmg = base_dmg * (1.0 + mod_dmg) * (1.0 + mod_elem)

        final_ms = 1.0 if is_melee else max(0.1, float(left_stats.get('multishot', 0.0) if left_stats else 0.0) or (float(w_meta.get('base_multishot', 1.0) or 1.0) * (1.0 + mod_ms)))

        base_cc = float(w_meta.get('crit_chance', 0.1))
        base_cc = base_cc / 100.0 if base_cc > 1.0 else base_cc
        final_cc = max(0.0, float(left_stats.get('crit_chance', 0.0) if left_stats else 0.0) or (base_cc * (1.0 + mod_cc)))

        base_cd = float(w_meta.get('crit_mult', 1.5))
        final_cd = max(1.0, float(left_stats.get('crit_mult', 0.0) if left_stats else 0.0) or (base_cd * (1.0 + mod_cd)))

        base_fr = float(w_meta.get('fire_rate', 1.0))
        final_fr = max(0.1, float(left_stats.get('fire_rate', 0.0) if left_stats else 0.0) or (base_fr * (1.0 + mod_fr)))

        exp_crit_mult = 1.0 + final_cc * (final_cd - 1.0) if final_cc > 0 else 1.0
        min_crit_mult = 1.0 + int(final_cc) * (final_cd - 1.0) if final_cc > 0 else 1.0
        max_crit_mult = 1.0 + int(math.ceil(final_cc)) * (final_cd - 1.0) if final_cc > 0 else 1.0

        expected_hit = final_dmg * exp_crit_mult * (1.0 + r_faction)
        min_hit = (final_dmg / final_ms if final_ms > 0 else final_dmg) * (1.0 if is_melee else max(1, int(final_ms))) * min_crit_mult
        max_crit_hit = (final_dmg / final_ms if final_ms > 0 else final_dmg) * (1.0 if is_melee else max(1, int(math.ceil(final_ms)))) * max_crit_mult

        burst_dps = expected_hit * final_fr
        sustained_dps = burst_dps if is_melee else (burst_dps * ((float(w_meta.get('magazineSize') or 30.0) / final_fr) / ((float(w_meta.get('magazineSize') or 30.0) / final_fr) + float(w_meta.get('reloadTime') or 2.0))))

        return {
            "final_dmg": final_dmg,
            "final_cc": final_cc,
            "final_cd": final_cd,
            "final_fr": final_fr,
            "final_ms": final_ms,
            "min_hit": min_hit,
            "max_crit_hit": max_crit_hit,
            "expected_hit": expected_hit,
            "burst_dps": burst_dps,
            "sustained_dps": sustained_dps,
            "per_pellet_dmg": final_dmg / final_ms
        }

