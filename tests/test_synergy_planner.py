import pytest
from scripts.damage_simulator import WeaponStats
from scripts.synergy_planner import SynergyPlanner

def test_mk1_braton_levelcap_synergy():
    planner = SynergyPlanner()
    mk1_braton = WeaponStats(
        name="MK1-Braton",
        base_damage=18.0,
        crit_chance=0.08,  # very low base crit
        crit_mult=1.5,
        status_chance=0.05,
        fire_rate=4.17,
        multishot=1.0,
        magazine_size=60,
        reload_time=2.0
    )

    plan = planner.plan_levelcap_synergy(mk1_braton, target_level=9999, is_steel_path=True, target_ttk=3.0)
    assert "synergy_recommendations" in plan or "steps" in plan or "recommended_helminth" in plan or "final_ttk" in plan or "after_ttk" in plan
    # Ensure plan provides concrete recommendations
    assert any(k in plan for k in ("final_ttk", "synergy_layers", "synergy_recommendations", "helminth", "external_buffs"))
