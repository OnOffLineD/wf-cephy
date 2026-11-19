import math
import pytest
from scripts.damage_formulas import (
    enemy_armor_dr, total_crit_chance, total_crit_mult, average_crit_mult, hm_crit_avg,
    weak_point_multiplier, arsenal_total, effective_fire_rate, shooting_proportion,
    bleed_tick, status_tick_damage, status_proc_total_damage, status_dot_dps,
    headcrit_avg_mult,
)
from scripts.wf_data_indexer import WFDataIndexer
from scripts.warframe_damage_engine import WarframeDamageEngine

@pytest.fixture(scope="module")
def idx():
    return WFDataIndexer()

def test_enemy_armor():
    # Post-Update 36 (Jade Shadows): enemy armor DR = 0.9 * sqrt(min(armor, 2700) / 2700).
    assert enemy_armor_dr(0) == 0.0
    assert enemy_armor_dr(-50) == 0.0
    assert enemy_armor_dr(200) == pytest.approx(0.9 * math.sqrt(200.0 / 2700.0))
    assert enemy_armor_dr(540) == pytest.approx(0.9 * math.sqrt(540.0 / 2700.0))
    assert enemy_armor_dr(1350) == pytest.approx(0.9 * math.sqrt(0.5))
    assert enemy_armor_dr(2700) == pytest.approx(0.9)
    assert enemy_armor_dr(5000) == pytest.approx(0.9)

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

def test_status_tick_and_proc_total_damage_all_six_types():
    base = 100.0
    faction = 0.5
    sd = 0.8
    crit = 2.0
    common = (1 + faction) ** 2 * (1 + sd) * crit

    # Slash: 0.35x, 6 ticks, ignores +slash / elemental mods
    slash_tick = status_tick_damage('slash', base, faction=faction, status_damage=sd, crit_avg=crit, element_bonus=0.9)
    assert slash_tick == pytest.approx(0.35 * base * common)
    assert slash_tick == pytest.approx(bleed_tick(base, faction=faction, status_damage=sd, crit_avg=crit))
    assert status_proc_total_damage('slash', base, faction=faction, status_damage=sd, crit_avg=crit, element_bonus=0.9) == pytest.approx(6 * slash_tick)

    # Heat / Toxin / Electric: 0.50x * (1 + element_bonus), 6/6/7 ticks
    heat_tick = status_tick_damage('heat', base, faction=faction, status_damage=sd, crit_avg=crit, element_bonus=0.9)
    assert heat_tick == pytest.approx(0.50 * base * 1.9 * common)
    assert status_proc_total_damage('heat', base, faction=faction, status_damage=sd, crit_avg=crit, element_bonus=0.9) == pytest.approx(6 * heat_tick)

    tox_tick = status_tick_damage('toxin', base, element_bonus=0.6)
    assert tox_tick == pytest.approx(0.50 * base * 1.6)
    assert status_proc_total_damage('toxin', base, element_bonus=0.6) == pytest.approx(6 * tox_tick)

    elec_tick = status_tick_damage('electric', base, element_bonus=0.6)
    assert elec_tick == pytest.approx(0.50 * base * 1.6)
    assert status_proc_total_damage('electric', base, element_bonus=0.6) == pytest.approx(7 * elec_tick)

    # Gas (7 ticks) and Blast (1 tick) ignore elemental mods
    assert status_tick_damage('gas', base, element_bonus=1.5) == pytest.approx(0.50 * base)
    assert status_proc_total_damage('gas', base, element_bonus=1.5) == pytest.approx(7 * 0.50 * base)
    assert status_tick_damage('blast', base, element_bonus=1.5) == pytest.approx(0.30 * base)
    assert status_proc_total_damage('blast', base, element_bonus=1.5) == pytest.approx(0.30 * base)

    # Non-damaging status contributes 0 DoT
    assert status_tick_damage('viral', base) == 0.0
    assert status_proc_total_damage('corrosive', base) == 0.0

def test_status_dot_dps_over_100_sc_and_forced_procs():
    res = status_dot_dps(
        100.0,
        shares={'slash': 0.4, 'heat': 0.4, 'viral': 0.2},
        status_chance=1.5,
        multishot=2.0,
        effective_rate=5.0,
        faction=0.55,
        status_damage=0.80,
        crit_avg=2.0,
        element_bonuses={'heat': 0.9},
        forced_procs_per_pellet={'slash': 0.30},
    )
    # 2.0 multishot * 5.0 FR = 10 pellets/sec
    expected_slash = 10.0 * (1.5 * 0.4 + 0.30) * status_proc_total_damage('slash', 100.0, faction=0.55, status_damage=0.80, crit_avg=2.0)
    expected_heat = 10.0 * (1.5 * 0.4) * status_proc_total_damage('heat', 100.0, faction=0.55, status_damage=0.80, crit_avg=2.0, element_bonus=0.9)
    assert set(res['breakdown']) == {'slash', 'heat'}
    assert res['breakdown']['slash'] == pytest.approx(expected_slash)
    assert res['breakdown']['heat'] == pytest.approx(expected_heat)
    assert res['total_dps'] == pytest.approx(expected_slash + expected_heat)

@pytest.mark.parametrize('cc, cd, expected', [
    (0.0, 2.0, 1.0),          # no crits: no headcrit bonus
    (0.5, 3.0, 0.5 + 0.5 * 6.0),
    (1.0, 2.0, 4.0),          # every hit is a 2x crit, doubled
    (1.5, 3.0, 2.0 * (1.0 + 1.5 * 2.0)),
])
def test_headcrit_avg_mult(cc, cd, expected):
    assert headcrit_avg_mult(cc, cd) == pytest.approx(expected)


def test_hm_crit_avg_and_vigilante():
    assert hm_crit_avg(0.0, 4.0) == 1.0
    # When 0 < CC < 1, Hunter Munitions only triggers on crits -> guaranteed Tier 1 crit_mult.
    assert hm_crit_avg(0.36, 4.4) == pytest.approx(4.4)
    assert hm_crit_avg(1.5, 3.0) == pytest.approx(average_crit_mult(1.5, 3.0))
    # Vigilante enhances crits (only crits, not non-crits) by +1 tier with prob v.
    assert average_crit_mult(0.5, 3.0, vigilante_chance=0.30) == pytest.approx(1.0 + (0.5 + 0.15) * 2.0)
    assert average_crit_mult(1.5, 3.0, vigilante_chance=0.30) == pytest.approx(1.0 + (1.5 + 0.30) * 2.0)
    assert hm_crit_avg(0.5, 3.0, vigilante_chance=0.30) == pytest.approx(1.0 + 1.30 * 2.0)
    assert headcrit_avg_mult(0.5, 3.0, vigilante_chance=0.30) == pytest.approx(2.0 * (1.0 + 0.65 * 2.0) - 0.5)


def test_bow_charge_cadence_and_zero_mag_shooting_proportion():
    # Charge-per-shot bow uses 1/charge_time so reload_time is not double-counted with 1/fire_rate.
    efr = effective_fire_rate(1.0, 1.2, is_bow_charge=True)
    assert efr == pytest.approx(1.0 / 1.2)
    prop = shooting_proportion(1, efr, 0.6)
    assert efr * prop == pytest.approx(1.0 / (1.2 + 0.6))
    # magazineSize=0 with reloadTime (e.g. Nataruk) treats mag as 1; reload=0 returns 1.0.
    assert shooting_proportion(0, 1.0, 0.05) == pytest.approx(1.0 / 1.05)
    assert shooting_proportion(0, 1.0, 0.0) == 1.0


def test_status_dot_dps_gas_10_stack_cap():
    # Low proc rate stays uncapped (<10 stacks/6s); high proc rate caps at 10 ticks/sec.
    low = status_dot_dps(100.0, {'gas': 1.0}, status_chance=0.5, multishot=1.0, effective_rate=1.0)
    assert low['breakdown']['gas'] == pytest.approx(0.5 * 7.0 * 50.0)
    high = status_dot_dps(100.0, {'gas': 1.0}, status_chance=1.0, multishot=3.0, effective_rate=10.0)
    assert high['breakdown']['gas'] == pytest.approx(10.0 * 50.0)


def test_status_dot_dps_beam_multishot_squared_and_hm_single_roll():
    res = status_dot_dps(
        100.0,
        {'heat': 1.0},
        status_chance=1.0,
        multishot=3.0,
        effective_rate=10.0,
        crit_avg=2.0,
        forced_crit_procs_per_pellet={'slash': 0.30},
        forced_crit_avg=4.0,
        is_beam=True,
        beam_ms_scale=3.0,
    )
    # Beam Heat DoT double-dips multishot: 3.0 proc-rate * (3.0 * 100 base) = 9x base scaling.
    assert res['breakdown']['heat'] == pytest.approx(10.0 * 3.0 * (6.0 * 0.50 * 300.0 * 2.0))
    # Beam HM triggers once per beam tick (not 3x) on the 3x-scaled tick base, with conditional crit_avg=4.0.
    assert res['breakdown']['slash'] == pytest.approx(10.0 * 0.30 * (6.0 * 0.35 * 300.0 * 4.0))
    assert res['forced_crit_dps'] == pytest.approx(res['breakdown']['slash'])
