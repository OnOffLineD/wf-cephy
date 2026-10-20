import pytest
from scripts.damage_simulator import DamageSimulator, WeaponStats, ModConfig, CombatState

def test_damage_simulator_metrics():
    sim = DamageSimulator()
    torid = WeaponStats(
        name="Torid",
        base_damage=100.0,
        crit_chance=0.30,
        crit_mult=2.5,
        status_chance=0.40,
        fire_rate=4.0,
        multishot=1.0,
        magazine_size=20,
        reload_time=1.7
    )
    mods = [
        ModConfig(name="Serration", base_damage_pct=1.65),
        ModConfig(name="Split Chamber", multishot_pct=0.90),
        ModConfig(name="Point Strike", crit_chance_pct=1.50),
        ModConfig(name="Vital Sense", crit_mult_pct=1.20)
    ]

    metrics_init = sim.calculate_damage_metrics(torid, mods, combat_state=CombatState.INITIAL)
    assert metrics_init["expected_hit"] > 0
    assert metrics_init["min_guaranteed_hit"] > 0
    assert metrics_init["burst_dps"] > 0
    assert metrics_init["sustained_dps"] > 0
    assert metrics_init["burst_dps"] >= metrics_init["sustained_dps"]

def test_simulate_ttk():
    sim = DamageSimulator()
    torid = WeaponStats(
        name="Torid",
        base_damage=200.0,
        crit_chance=0.50,
        crit_mult=3.0,
        status_chance=0.50,
        fire_rate=5.0
    )
    mods = [
        ModConfig(name="Damage", base_damage_pct=2.0),
        ModConfig(name="Multishot", multishot_pct=1.5)
    ]
    ttk = sim.simulate_ttk(torid, mods, enemy_health=50000.0, enemy_armor=1000.0)
    assert 0.0 < ttk <= 10.0

def test_compare_rivens():
    sim = DamageSimulator()
    torid = WeaponStats(
        name="Torid",
        base_damage=100.0,
        crit_chance=0.30,
        crit_mult=2.5,
        status_chance=0.40,
        fire_rate=4.0
    )
    base_7_mods = [
        ModConfig(name="Serration", base_damage_pct=1.65),
        ModConfig(name="Split Chamber", multishot_pct=0.90),
        ModConfig(name="Point Strike", crit_chance_pct=1.50),
        ModConfig(name="Vital Sense", crit_mult_pct=1.20),
        ModConfig(name="Hunter Munitions"),
        ModConfig(name="Malignant Force", status_chance_pct=0.60),
        ModConfig(name="Rime Rounds", status_chance_pct=0.60)
    ]

    riven_a = ModConfig(name="Riven A", crit_chance_pct=1.20, crit_mult_pct=1.00)
    riven_b = ModConfig(name="Riven B", multishot_pct=1.00, base_damage_pct=1.00)

    result = sim.compare_rivens(torid, base_7_mods, riven_a, riven_b)
    assert "winner" in result
    assert result["winner"] in ("Riven A", "Riven B", "Option A", "Option B")
