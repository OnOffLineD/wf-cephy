import pytest
from scripts.survival_evaluator import SurvivalEvaluator, WarframeStats, WarframeModConfig

def test_nova_null_star_ehp():
    evaluator = SurvivalEvaluator()
    nova = WarframeStats(
        name="Nova",
        base_health=300.0,
        base_shield=300.0,
        base_armor=105.0,
        base_energy=225.0
    )
    # High duration build for Null Star 90% DR
    duration_mods = [
        WarframeModConfig(name="Narrow Minded", duration_pct=0.99),
        WarframeModConfig(name="Primed Continuity", duration_pct=0.55),
        WarframeModConfig(name="Adaptation", has_adaptation=True)
    ]
    res = evaluator.calculate_ehp(nova, duration_mods)
    assert res["total_ehp"] > 300.0
    assert "armor_dr" in res
    assert "ability_dr" in res
    assert res["ability_dr"] >= 0.70  # Nova high duration gives strong DR

def test_survival_time_scaling():
    evaluator = SurvivalEvaluator()
    nova = WarframeStats(name="Nova", base_health=300.0, base_armor=100.0)
    vitality_only = [WarframeModConfig(name="Vitality", health_pct=1.0)]
    dr_build = [
        WarframeModConfig(name="Primed Continuity", duration_pct=0.55),
        WarframeModConfig(name="Narrow Minded", duration_pct=0.99),
        WarframeModConfig(name="Adaptation", has_adaptation=True)
    ]
    report = evaluator.evaluate_survival_time(nova, dr_build, enemy_level=200)
    assert "ability_dr_build_time" in report or "simple_health_build_time" in report
    assert report["ability_dr_build_time"] > 0

def test_shield_gating_loop():
    evaluator = SurvivalEvaluator()
    nova = WarframeStats(name="Nova", base_shield=150.0)
    gating_mods = [
        WarframeModConfig(name="Catalyzing Shields", has_catalyzing_shields=True),
        WarframeModConfig(name="Brief Respite", has_brief_respite=True)
    ]
    gate_res = evaluator.evaluate_shield_gating(nova, gating_mods, energy_spent=50.0)
    assert "gate_duration" in gate_res or "is_infinite_sustainable" in gate_res or "shield_restored" in gate_res
