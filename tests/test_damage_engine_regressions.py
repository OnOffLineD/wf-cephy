import pytest
from scripts.warframe_damage_engine import WarframeDamageEngine

def firearm():
    return {
        'name': 'R',
        'category': 'Primary',
        'total_damage': 300.0,
        'crit_chance': 0.2,
        'crit_mult': 2.0,
        'fire_rate': 5.0,
        'base_multishot': 1.0,
        'magazineSize': 30,
        'reloadTime': 2.0
    }

@pytest.fixture
def damage_engine():
    return WarframeDamageEngine()

def test_uses_codex_damage_without_panel(damage_engine):
    result = damage_engine.compute_metrics(firearm())
    assert result['final_dmg'] == pytest.approx(300.0)

def test_modded_multishot_scales_without_panel(damage_engine):
    result = damage_engine.compute_metrics(firearm(), mod_objs=[{'name': 'Split', 'multishot': 0.9}])
    assert result['burst_dps'] == pytest.approx(300.0 * 1.9 * 1.2 * 5.0)
    assert result['final_ms'] == pytest.approx(1.9)

def test_faction_applies_to_all_rolls(damage_engine):
    with_riven = damage_engine.compute_metrics(firearm(), riven_stats={'faction_damage': 0.5})
    without_riven = damage_engine.compute_metrics(firearm())
    for key in ['min_hit', 'expected_hit', 'max_crit_hit']:
        assert with_riven[key] == pytest.approx(without_riven[key] * 1.5)

def test_expected_between_min_and_max(damage_engine):
    result = damage_engine.compute_metrics(firearm(), left_stats={'total_damage': 500.0, 'crit_chance': 1.5, 'crit_mult': 3.0, 'multishot': 2.5})
    assert result['min_hit'] <= result['expected_hit'] <= result['max_crit_hit']

def test_optional_sections_only_with_data(damage_engine):
    result = damage_engine.compute_metrics(firearm())
    assert 'incarnon' not in result
    assert 'heavy' not in result
    assert 'radial' not in result
    assert 'hunter_munitions' not in result

    melee_result = damage_engine.compute_metrics({'name': 'R', 'category': 'Melee'}, left_stats={'total_damage': 500.0, 'slam_damage': 1425.0, 'heavy_damage': 6983.0})
    assert melee_result['radial']['base_damage'] == pytest.approx(1425.0)
    assert melee_result['heavy']['heavy_hit'] == pytest.approx(6983.0)

    hunter_result = damage_engine.compute_metrics(firearm(), mod_objs=[{'name': 'Hunter Munitions'}])
    assert hunter_result['hunter_munitions']['bleed_tick'] > 0