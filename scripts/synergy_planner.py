from dataclasses import dataclass, field
from typing import List, Dict, Any
from scripts.damage_simulator import DamageSimulator, WeaponStats, ModConfig, CombatState

@dataclass
class SynergyConfig:
    helminth_ability: str = "Pillage"  # 100% Armor Strip
    archon_shards: List[str] = field(default_factory=lambda: ["Emerald (Corrosive Cap +2)", "Emerald (Corrosive Cap +2)", "Violet (Crit Damage)"])
    flat_crit_bonus: float = 0.45  # Arcane Avenger
    roar_multiplier: float = 0.55  # Rhino Roar Faction Multiplier
    companion_primer_status_count: int = 4  # Viral, Cold, Heat, Radiation via Nautilus

class SynergyPlanner:
    def __init__(self):
        self.damage_simulator = DamageSimulator()
        self.synergy_config = SynergyConfig()

    def plan_levelcap_synergy(self, weapon: WeaponStats, target_level: int = 9999, is_steel_path: bool = True, target_ttk: float = 3.0) -> Dict[str, Any]:
        # Initial TTK calculation
        initial_ttk = self.damage_simulator.simulate_ttk(weapon, [])
        initial_dps = self.damage_simulator.calculate_damage_metrics(weapon, [])

        # Check if weapon alone can defeat target
        if initial_ttk <= target_ttk:
            return {
                "initial_ttk": initial_ttk,
                "initial_dps": initial_dps,
                "synergy_needed": False,
                "recommended_helminth": None,
                "recommended_shards": None,
                "recommended_companion": None,
                "recommended_arcanes": None
            }

        # Step 1: Armor Strip to 0%
        armor_strip_mod = ModConfig(name="Armor Strip", base_damage_pct=0.0, crit_chance_pct=0.0, crit_mult_pct=0.0, status_chance_pct=0.0, fire_rate_pct=0.0, elements={"Armor Strip": 1.0})
        ttk_with_armor_strip = self.damage_simulator.simulate_ttk(weapon, [armor_strip_mod])

        # Step 2: External Flat Crit +45%
        flat_crit_mod = ModConfig(name="Flat Crit", base_damage_pct=0.0, crit_chance_pct=0.0, crit_mult_pct=self.synergy_config.flat_crit_bonus, status_chance_pct=0.0, fire_rate_pct=0.0, elements={})
        ttk_with_flat_crit = self.damage_simulator.simulate_ttk(weapon, [armor_strip_mod, flat_crit_mod])

        # Step 3: Companion primer +4 statuses
        companion_primer_mod = ModConfig(name="Companion Primer", base_damage_pct=0.0, crit_chance_pct=0.0, crit_mult_pct=0.0, status_chance_pct=0.0, fire_rate_pct=0.0, elements={})
        ttk_with_companion_primer = self.damage_simulator.simulate_ttk(weapon, [armor_strip_mod, flat_crit_mod, companion_primer_mod])

        # Recalculate TTK and expected DPS
        final_ttk = ttk_with_companion_primer
        final_dps = self.damage_simulator.calculate_damage_metrics(weapon, [armor_strip_mod, flat_crit_mod, companion_primer_mod])

        # Return comprehensive masterplan dictionary
        return {
            "initial_ttk": initial_ttk,
            "initial_dps": initial_dps,
            "final_ttk": final_ttk,
            "final_dps": final_dps,
            "synergy_needed": True,
            "recommended_helminth": self.synergy_config.helminth_ability,
            "recommended_shards": self.synergy_config.archon_shards,
            "recommended_companion": "Nautilus",
            "recommended_arcanes": ["Arcane Avenger", "Rhino Roar"]
        }

if __name__ == "__main__":
    # Example usage
    weapon = WeaponStats(name="MK1-Braton", base_damage=100.0, crit_chance=0.1, crit_mult=1.5, status_chance=0.05, fire_rate=0.5)
    synergy_planner = SynergyPlanner()
    plan = synergy_planner.plan_levelcap_synergy(weapon)
    print(plan)