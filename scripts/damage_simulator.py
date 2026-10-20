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
        # Base damage calculation
        base_damage = weapon.base_damage
        for mod in mods:
            base_damage *= (1 + mod.base_damage_pct)

        # Additive base damage from mods
        additive_base = sum(mod.base_damage_pct for mod in mods)

        # Sum of elemental modifiers
        sum_elements = sum(mod.elements.get(elem, 0) for elem in weapon.elements)

        # Faction damage modifier
        faction_damage = sum(mod.faction_damage_pct for mod in mods)

        # Crit multiplier
        crit_multiplier = weapon.crit_mult * (1 + sum(mod.crit_mult_pct for mod in mods))

        # Multishot
        multishot = weapon.multishot * (1 + sum(mod.multishot_pct for mod in mods))

        # Calculate expected hit
        expected_hit = base_damage * (1 + additive_base) * (1 + sum_elements) * (1 + faction_damage) * crit_multiplier * multishot

        # Min guaranteed hit (assuming no crit)
        min_guaranteed_hit = base_damage * (1 + additive_base) * (1 + sum_elements) * (1 + faction_damage) * multishot

        # Burst DPS
        burst_dps = expected_hit * weapon.fire_rate * weapon.magazine_size / (weapon.reload_time + weapon.magazine_size / weapon.fire_rate)

        # Sustained DPS
        sustained_dps = expected_hit * weapon.fire_rate

        # Apply typical full-stack bonuses in SUSTAINED state
        if combat_state == CombatState.SUSTAINED:
            sustained_dps *= 4.96  # Example multiplier for full-stack bonuses

        return {
            "expected_hit": expected_hit,
            "min_guaranteed_hit": min_guaranteed_hit,
            "burst_dps": burst_dps,
            "sustained_dps": sustained_dps
        }

    def simulate_ttk(self, weapon: WeaponStats, mods: List[ModConfig], enemy_health: float = 500000.0, enemy_armor: float = 2700.0, archetype: str = "STANDARD_MOB", max_seconds: float = 10.0) -> float:
        # Calculate damage metrics
        damage_metrics = self.calculate_damage_metrics(weapon, mods)

        # Armor Damage Reduction (DR)
        armor_dr = enemy_armor / (enemy_armor + 300)

        # Effective damage
        effective_damage = damage_metrics["expected_hit"] * (1 - armor_dr)

        # Viral status health multiplier (up to 4.25x)
        viral_multiplier = 1.0  # Placeholder for actual viral multiplier logic

        # Total damage per second
        dps = effective_damage * viral_multiplier

        # Time to Kill (TTK)
        ttk = enemy_health / dps

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