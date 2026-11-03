import pytest
from scripts.damage_formulas import (
    enemy_armor_dr, total_crit_chance, total_crit_mult, average_crit_mult,
    weak_point_multiplier, arsenal_total, effective_fire_rate, shooting_proportion,
    bleed_tick
)
from scripts.wf_data_indexer import WFDataIndexer
from scripts.warframe_damage_engine import WarframeDamageEngine

@pytest.fixture(scope="module")
def idx():
    return WFDataIndexer()

def test_enemy_armor():
    assert enemy_armor_dr(1350) == 0.45
    assert enemy_armor_dr(2700) == 0.9
    assert enemy_armor_dr(200) == pytest.approx(0.9 * 200 / 2700)
    assert enemy_armor_dr(0) == 0

def test_crit_examples():
    assert total_crit_chance(0.12, 1.5 + 1.35, 0.0) == pytest.approx(0.462)
    assert total_crit_chance(0.12, 2.85, 0.45) == pytest.approx(0.912)
    assert total_crit_mult(1.6, 1.2, 1.2) == pytest.approx(4.72)
    assert total_crit_chance(0.20, 1.2, 0.0, 0.4, 4.0) == pytest.approx(0.68)

def test_weak_point_examples():
    assert weak_point_multiplier(3.0, 4.25, 0.0, True) == pytest.approx(9.375)
    assert weak_point_multiplier(3.0, 4.25, 0.7, True) == pytest.approx(15.9375)
    assert weak_point_multiplier(1.0, 4.25, 0.0, False) == pytest.approx(5.25)

def test_bleed_example():
    assert bleed_tick(100 * 2.65, 0.3, 0.9, 1.0) == pytest.approx(297.8202, abs=0.01)

def test_arsenal_total():
    assert arsenal_total(100.0, dict(impact=30, puncture=30, slash=40), 0.9, dict(slash=1.2), 1.65, 2.0) == pytest.approx(100 * (1 + 0.9 + 0.4 * 1.2) * 2.65 * 2.0)

def test_effective_rate():
    assert effective_fire_rate(3.0, 1.5) == pytest.approx(1 / (1.5 + 1 / 3))
    assert effective_fire_rate(5.0) == 5.0
    assert shooting_proportion(30, 10, 2) == pytest.approx(0.6)

def _mod(idx, name):
    return idx.mods_index[name.lower()]

def test_mod_buckets(idx):
    rifle_elementalist = _mod(idx,'Rifle Elementalist')
    assert rifle_elementalist['damage'] == 0
    assert rifle_elementalist['status_damage'] == 0.9

    seismic_wave = _mod(idx,'Seismic Wave')
    assert seismic_wave['damage'] == 0
    assert seismic_wave['slam_damage'] == 2.0

    condition_overload = _mod(idx,'Condition Overload')
    assert condition_overload['damage'] == 0
    assert condition_overload['status_type_damage'] == 0.8

    blood_rush = _mod(idx,'Blood Rush')
    assert blood_rush['crit_chance'] == 0
    assert blood_rush['combo_crit'] == 0.4

    galvanized_steel = _mod(idx,'Galvanized Steel')
    assert galvanized_steel['crit_chance'] == 1.1
    assert galvanized_steel['crit_damage'] == 0
    assert galvanized_steel['heavy_crit_chance'] == 1.1
    assert galvanized_steel['on_kill'][0]['stat'] == 'crit_damage'
    assert galvanized_steel['on_kill'][0]['value'] == 0.3
    assert galvanized_steel['on_kill'][0]['stacks'] == 4

    galvanized_chamber = _mod(idx,'Galvanized Chamber')
    assert galvanized_chamber['multishot'] == 0.8
    assert galvanized_chamber['on_kill'][0]['stat'] == 'multishot'
    assert galvanized_chamber['on_kill'][0]['value'] == 0.3
    assert galvanized_chamber['on_kill'][0]['stacks'] == 5

    galvanized_aptitude = _mod(idx,'Galvanized Aptitude')
    assert galvanized_aptitude['damage'] == 0
    assert galvanized_aptitude['on_kill'][0]['stat'] == 'status_type_direct'

    hunter_munitions = _mod(idx,'Hunter Munitions')
    assert hunter_munitions['slash'] == 0

    internal_bleeding = _mod(idx,'Internal Bleeding')
    assert internal_bleeding['fire_rate'] == 0

    serration = _mod(idx,'Serration')
    assert serration['damage'] == 1.65

    sawtooth_clip = _mod(idx,'Sawtooth Clip')
    assert sawtooth_clip['slash'] == 0.9

    primed_smite = _mod(idx, 'Primed Smite Grineer')
    assert primed_smite['faction']['grineer'] == pytest.approx(0.55)

def test_engine_physical_bucket():
    engine = WarframeDamageEngine()
    result = engine.compute_metrics(
        dict(
            name='W',
            category='Primary',
            total_damage=100.0,
            crit_chance=0.0,
            crit_mult=2.0,
            fire_rate=1.0,
            base_multishot=1.0,
            attacks=[dict(damage=dict(slash=50.0, impact=50.0))]
        ),
        mod_objs=[dict(name='Saw', slash=1.0)]
    )
    assert result['final_dmg'] == pytest.approx(150.0)

def test_full_stack_merciless_additive():
    engine = WarframeDamageEngine()
    result = engine.compute_full_stack(
        dict(
            name='W',
            category='Primary',
            total_damage=100.0,
            crit_chance=0.0,
            crit_mult=2.0,
            fire_rate=1.0,
            base_multishot=1.0,
            magazineSize=30,
            reloadTime=2.0
        ),
        left_stats=dict(total_damage=265.0),
        mod_objs=[dict(name='Serration', damage=1.65)],
        arcane=dict(name='Primary Merciless', damage_per_stack=0.3, max_stacks=12)
    )
    assert result['final_dmg'] == pytest.approx(265.0 * (1 + 1.65 + 3.6) / 2.65)

def test_full_stack_melee_blood_rush():
    engine = WarframeDamageEngine()
    result = engine.compute_full_stack(
        dict(
            name='M',
            category='Melee',
            total_damage=100.0,
            crit_chance=0.2,
            crit_mult=2.0,
            fire_rate=1.0
        ),
        left_stats=dict(total_damage=100.0, crit_chance=0.2, crit_mult=2.0),
        mod_objs=[dict(name='Blood Rush', combo_crit=0.4)]
    )
    assert result['final_cc'] == pytest.approx(0.2 + 0.2 * 0.4 * 11)