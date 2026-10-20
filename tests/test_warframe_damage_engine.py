import pytest
import math
from scripts.warframe_damage_engine import WarframeDamageEngine

def test_sanitize_left_stats_comma_dot_fix():
    engine = WarframeDamageEngine()
    # 1.3966 was an OCR comma-read-as-dot error for 1,396.6 on Ruvox (base 170)
    raw_stats = {'total_damage': 1.3966, 'multishot': 16.75, 'crit_chance': 0.546}
    cleaned = engine.sanitize_left_stats(raw_stats, base_damage=170.0, is_melee=True)
    assert 'multishot' not in cleaned
    assert abs(cleaned['total_damage'] - 1396.6) < 0.1
    assert cleaned['crit_chance'] == 0.546

def test_sanitize_left_stats_small_noise_rejection():
    engine = WarframeDamageEngine()
    # 1.41 was noise from a trailing bracket/range on Arca Titron (base 844)
    raw_stats = {'total_damage': 1.41, 'crit_chance': 0.50}
    cleaned = engine.sanitize_left_stats(raw_stats, base_damage=844.0, is_melee=True)
    assert 'total_damage' not in cleaned
    assert cleaned['crit_chance'] == 0.50

def test_in_game_crit_tiers_and_rolls():
    engine = WarframeDamageEngine()
    # Base 50% CC weapon with +200% CC mod (Critical Delay) -> 150% final CC (Orange crit tier)
    w_meta = {
        'name': 'CritRifle',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.50,
        'crit_mult': 2.0,
        'fire_rate': 10.0,
        'base_multishot': 1.0,
        'magazineSize': 30,
        'reloadTime': 2.0
    }
    mods = [{'name': 'Critical Delay', 'crit_chance': 2.0}]
    metrics = engine.compute_metrics(w_meta, left_stats={}, mod_objs=mods)
    assert abs(metrics['final_cc'] - 1.50) < 0.01
    # Trough non-crit cannot happen when CC is 150%; minimum is Tier 1 crit (2.0x)
    assert abs(metrics['min_hit'] - 200.0) < 0.1
    # Peak is Tier 2 crit (3.0x)
    assert abs(metrics['max_crit_hit'] - 300.0) < 0.1
    # Expected hit is 2.5x base damage
    assert abs(metrics['expected_hit'] - 250.0) < 0.1

def test_melee_duty_cycle_no_reload():
    engine = WarframeDamageEngine()
    w_meta = {
        'name': 'Galatine',
        'category': 'Melee',
        'total_damage': 100.0,
        'crit_chance': 0.20,
        'crit_mult': 2.0,
        'fire_rate': 1.0
    }
    metrics = engine.compute_metrics(w_meta, left_stats={}, mod_objs=[])
    # Melee has no reload downtime; sustained DPS equals burst DPS
    assert metrics['sustained_dps'] == metrics['burst_dps']

def test_firearm_duty_cycle_sustained():
    engine = WarframeDamageEngine()
    w_meta = {
        'name': 'Braton',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.0,
        'crit_mult': 2.0,
        'fire_rate': 10.0,
        'base_multishot': 1.0,
        'magazineSize': 30,
        'reloadTime': 2.0
    }
    metrics = engine.compute_metrics(w_meta, left_stats={}, mod_objs=[])
    # Fire time = 30 / 10 = 3s. Cycle time = 3s + 2s = 5s. Duty cycle = 0.60
    assert abs(metrics['burst_dps'] - 1000.0) < 0.1
    assert abs(metrics['sustained_dps'] - 600.0) < 0.1

def test_elemental_and_base_damage_buckets():
    engine = WarframeDamageEngine()
    w_meta = {
        'name': 'TestWeapon',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.0,
        'crit_mult': 2.0,
        'fire_rate': 1.0,
        'base_multishot': 1.0
    }
    # Serration (+165%) and two 90% elementals (+180%)
    mods = [
        {'name': 'Serration', 'damage': 1.65},
        {'name': 'Hellfire', 'elemental_damage': 0.90},
        {'name': 'Cryo Rounds', 'elemental_damage': 0.90}
    ]
    metrics = engine.compute_metrics(w_meta, left_stats={}, mod_objs=mods)
    # Expected: 100 * (1 + 1.65) * (1 + 1.80) = 265 * 2.8 = 742.0
    assert abs(metrics['final_dmg'] - 742.0) < 0.1
    assert abs(metrics['expected_hit'] - 742.0) < 0.1
