from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class WarframeStats:
    name: str
    base_health: float = 300.0
    base_shield: float = 300.0
    base_armor: float = 100.0
    base_energy: float = 150.0

@dataclass
class WarframeModConfig:
    name: str
    health_pct: float = 0.0
    armor_pct: float = 0.0
    shield_pct: float = 0.0
    strength_pct: float = 0.0
    duration_pct: float = 0.0
    efficiency_pct: float = 0.0
    has_adaptation: bool = False
    has_catalyzing_shields: bool = False
    has_brief_respite: bool = False

class SurvivalEvaluator:
    def calculate_ehp(self, wf: WarframeStats, mods: List[WarframeModConfig]) -> Dict[str, float]:
        total_health = wf.base_health * (1 + sum(mod.health_pct for mod in mods))
        total_armor = wf.base_armor * (1 + sum(mod.armor_pct for mod in mods))
        total_shield = wf.base_shield * (1 + sum(mod.shield_pct for mod in mods))
        
        armor_dr = total_armor / (total_armor + 300)
        ability_dr = 0.0
        adaptation_dr = 0.0
        
        for mod in mods:
            if mod.has_adaptation:
                adaptation_dr = 0.90
        
        # Assuming Nova Null Star and Mesa Shatter Shield are the abilities
        # Nova Null Star: up to 90% scaling with duration
        # Mesa Shatter Shield: up to 95% scaling with strength
        for mod in mods:
            if mod.duration_pct > 0:
                ability_dr += min(0.90, mod.duration_pct)
            if mod.strength_pct > 0:
                ability_dr += min(0.95, mod.strength_pct)
        
        total_ehp = total_health + total_armor + total_shield
        effective_health = total_health * (1 - ability_dr) * (1 - adaptation_dr)
        
        return {
            'effective_health': effective_health,
            'total_ehp': total_ehp,
            'armor_dr': armor_dr,
            'ability_dr': ability_dr,
            'adaptation_dr': adaptation_dr
        }
    
    def evaluate_survival_time(self, wf: WarframeStats, mods: List[WarframeModConfig], enemy_level: int = 200) -> Dict[str, Any]:
        base_damage = 100  # Assuming a base damage value for the enemy
        enemy_damage = base_damage * (1 + (enemy_level - 200) ** 1.55 * 0.015)
        
        stats = self.calculate_ehp(wf, mods)
        simple_health_build_time = stats['effective_health'] / enemy_damage
        ability_dr_build_time = stats['total_ehp'] / enemy_damage
        
        return {
            'enemy_damage': enemy_damage,
            'simple_health_build_time': simple_health_build_time,
            'ability_dr_build_time': ability_dr_build_time
        }
    
    def evaluate_shield_gating(self, wf: WarframeStats, mods: List[WarframeModConfig], energy_spent: float = 50.0) -> Dict[str, Any]:
        shield_regen = 10  # Assuming a base shield regen value
        shield_regen += shield_regen * sum(mod.efficiency_pct for mod in mods)
        
        gate_duration = 1.33 if any(mod.has_catalyzing_shields for mod in mods) else 2.0
        
        shield_reset_time = (wf.base_shield - energy_spent) / shield_regen
        
        return {
            'gate_duration': gate_duration,
            'shield_reset_time': shield_reset_time,
            'can_reset_shield': shield_reset_time <= gate_duration
        }