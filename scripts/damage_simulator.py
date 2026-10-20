from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any

class CombatState(str, Enum):
    INITIAL = "INITIAL"
    SUSTAINED = "SUSTAINED"

@dataclass
class WeaponStats:
    name: str
    base_damage: float
    crit_chance: float
    crit_mult: float
    status_chance: float
    fire_rate: float
    multishot: float = 1.0
    magazine_size: int = 30
    reload_time: float = 2.0
    disposition: float = 1.0
    is_incarnon: bool = False
    elements: Dict[str, float] = field(default_factory=dict)

@dataclass
class ModConfig:
    name: str
    base_damage_pct: float = 0.0
    multishot_pct: float = 0.0
    crit_chance_pct: float = 0.0
    crit_mult_pct: float = 0.0
    status_chance_pct: float = 0.0
    fire_rate_pct: float = 0.0
    elements: Dict[str, float] = field(default_factory=dict)
    faction_damage_pct: float = 0.0
    gunco_per_proc: float = 0.0

class DamageSimulator:
    def calculate_damage_metrics(self, weapon: WeaponStats, mods: List[ModConfig], combat_state: CombatState = CombatState.SUSTAINED, active_status_types: int = 0) -> Dict[str, float]:
            # Mod base percentage calculation
            mod_base_pct = sum(m.base_damage_pct for m in mods)
            if active_status_types > 0:
                mod_base_pct += sum(m.gunco_per_proc for m in mods) * active_status_types
            base_dmg = weapon.base_damage * (1.0 + mod_base_pct)

            # Mod elemental percentage calculation
            mod_elem_pct = sum(sum(m.elements.values()) for m in mods)
            total_modded_base = base_dmg * (1.0 + mod_elem_pct)

            # Multishot calculation
            ms = max(0.1, weapon.multishot * (1.0 + sum(m.multishot_pct for m in mods)))

            # Faction damage calculation
            faction = 1.0 + sum(m.faction_damage_pct for m in mods)

            # Crit chance and crit multiplier calculation
            cc = max(0.0, weapon.crit_chance * (1.0 + sum(m.crit_chance_pct for m in mods)))
            cd = max(1.0, weapon.crit_mult * (1.0 + sum(m.crit_mult_pct for m in mods)))
            exp_crit_mult = 1.0 + cc * (cd - 1.0) if cc > 0 else 1.0
            min_crit_mult = 1.0 + int(cc) * (cd - 1.0) if cc > 0 else 1.0

            # Expected hit calculation
            expected_hit = total_modded_base * ms * faction * exp_crit_mult

            # Min guaranteed hit calculation
            min_guaranteed_hit = total_modded_base * max(1.0, float(int(ms))) * faction * min_crit_mult

            # Fire rate calculation
            fr = max(0.1, weapon.fire_rate * (1.0 + sum(m.fire_rate_pct for m in mods)))

            # Burst DPS calculation
            burst_dps = expected_hit * fr

            # Magazine size and reload time
            mag = float(weapon.magazine_size)
            reload = float(weapon.reload_time)

            # Sustained DPS calculation
            if mag > 0 and reload > 0 and fr > 0:
                sustained_dps = burst_dps * (mag / fr) / ((mag / fr) + reload)
            else:
                sustained_dps = burst_dps

            return {
                "expected_hit": expected_hit,
                "min_guaranteed_hit": min_guaranteed_hit,
                "burst_dps": burst_dps,
                "sustained_dps": sustained_dps,
                "crit_chance": cc,
                "crit_mult": cd,
                "multishot": ms,
                "fire_rate": fr
            }

    def simulate_ttk(self, weapon: WeaponStats, mods: List[ModConfig], enemy_health: float = 500000.0, enemy_armor: float = 2700.0, archetype: str = "STANDARD_MOB", max_seconds: float = 10.0) -> float:
            # Calculate damage metrics
            damage_metrics = self.calculate_damage_metrics(weapon, mods)

            # Check for Armor Strip mod
            for m in mods:
                if m.name == 'Armor Strip' or 'Armor Strip' in m.elements:
                    enemy_armor = 0.0
                    break

            # Effective armor calculation
            effective_armor = min(2700.0, max(0.0, float(enemy_armor)))
            armor_dr = effective_armor / (effective_armor + 300.0) if effective_armor > 0 else 0.0

            # Viral status health multiplier
            viral_multiplier = 4.25 if any('Viral' in m.name or 'Viral' in m.elements for m in mods) else 1.0

            # Effective damage per second
            effective_dps = max(1.0, damage_metrics.get('sustained_dps', 1.0) * (1.0 - armor_dr) * viral_multiplier)

            # Time to Kill (TTK)
            ttk = float(enemy_health) / effective_dps

            # Cap TTK at max_seconds
            return min(ttk, max_seconds)

    def compare_rivens(self, weapon: WeaponStats, base_7_mods: List[ModConfig], riven_a: ModConfig, riven_b: ModConfig) -> Dict[str, Any]:
        # Calculate metrics for base build
        base_metrics = self.calculate_damage_metrics(weapon, base_7_mods)

        # Calculate metrics for build + Riven A
        riven_a_metrics = self.calculate_damage_metrics(weapon, base_7_mods + [riven_a])

        # Calculate metrics for build + Riven B
        riven_b_metrics = self.calculate_damage_metrics(weapon, base_7_mods + [riven_b])

        # Compare sustained DPS
        base_dps = base_metrics["sustained_dps"]
        riven_a_dps = riven_a_metrics["sustained_dps"]
        riven_b_dps = riven_b_metrics["sustained_dps"]

        # Determine the winner
        if riven_a_dps > riven_b_dps and riven_a_dps > base_dps:
            winner = "Riven A"
            expected_dps_diff_percent = ((riven_a_dps - base_dps) / base_dps) * 100
        elif riven_b_dps > riven_a_dps and riven_b_dps > base_dps:
            winner = "Riven B"
            expected_dps_diff_percent = ((riven_b_dps - base_dps) / base_dps) * 100
        else:
            winner = "No Riven"
            expected_dps_diff_percent = 0.0

        return {
            "winner": winner,
            "expected_dps_diff_percent": expected_dps_diff_percent,
            "base_metrics": base_metrics,
            "riven_a_metrics": riven_a_metrics,
            "riven_b_metrics": riven_b_metrics
        }