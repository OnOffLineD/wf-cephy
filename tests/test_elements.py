import pytest
from scripts.damage_formulas import combine_elements, faction_multipliers
from scripts.wf_data_indexer import WFDataIndexer
from scripts.warframe_damage_engine import WarframeDamageEngine

@pytest.fixture(scope="module")
def idx():
    return WFDataIndexer()

def breakdown(idx, weapon, names):
    mods = [dict(idx.mods_index[n.lower()], slot_index=i) for i, n in enumerate(names)]
    return WarframeDamageEngine().compute_metrics(idx.fuzzy_match_weapon(weapon), mod_objs=mods)['elements']

def _weapon(**extra):
    return dict(dict(name='W', category='Primary', total_damage=100.0, crit_chance=0.1, crit_mult=2.0, fire_rate=1.0, base_multishot=1.0, attacks=[dict(damage=dict(slash=100.0))]), **extra)

def test_panel_rows_are_per_projectile():
    # Secura Penta in game: Heat 861.3 per projectile, Multishot 1.8, Total 1,550.3.
    left = dict(total_damage=1550.3, multishot=1.8, el_heat=861.3)
    el = WarframeDamageEngine().compute_metrics(_weapon(attacks=[dict(damage=dict(heat=100.0))]), left_stats=left)['elements']
    assert el['source'] == 'panel'
    assert el['types']['heat'] == pytest.approx(1550.3, rel=0.001)

def test_one_unreadable_row_recovered_from_total():
    # Dark Split-Sword in game: Radiation 32 read as 6 by OCR, total 255.2.
    left = dict(total_damage=255.2, el_corrosive=139.2, el_slash=28.0, el_puncture=56.0, el_radiation=6.0)
    weapon = _weapon(category='Melee', attacks=[dict(damage=dict(slash=50.0, puncture=50.0, radiation=50.0))])
    mods = [dict(name='T', toxin=0.6, slot_index=1), dict(name='E', electric=0.6, slot_index=2)]
    el = WarframeDamageEngine().compute_metrics(weapon, left_stats=left, mod_objs=mods)['elements']
    assert el['source'] == 'panel'
    assert el['types']['radiation'] == pytest.approx(32.0, abs=0.01)

def test_innate_electricity_key_combines():
    weapon = _weapon(attacks=[dict(damage=dict(electricity=100.0))])
    el = WarframeDamageEngine().compute_metrics(weapon, mod_objs=[dict(name='T', toxin=1.0, slot_index=0)])['elements']
    assert el['pairs'] == [('toxin', 'electric', 'corrosive')]

def test_valence_acts_as_innate_element():
    weapon = _weapon(attacks=[dict(damage=dict(impact=100.0))])
    left = dict(valence_toxin=0.5)
    el = WarframeDamageEngine().compute_metrics(weapon, left_stats=left, mod_objs=[dict(name='C', cold=1.0, slot_index=0)])['elements']
    assert el['pairs'] == [('cold', 'toxin', 'viral')]
    assert el['types']['viral'] == pytest.approx(150.0)

def test_multi_attack_weapon_uses_first_attack_only(idx):
    # Kuva Zarr total 723 mixes the 50 Impact shell with its 673 Blast explosion. Game panel shows Impact 210.1 per shell.
    mods = [idx.mods_index[n.lower()] for n in ['Amalgam Serration', 'Heavy Caliber']]
    el = WarframeDamageEngine().compute_metrics(idx.fuzzy_match_weapon('Kuva Zarr'), left_stats=dict(multishot=1.0), mod_objs=mods)['elements']
    assert el['first_attack_only'] is True
    assert el['types']['impact'] == pytest.approx(210.0)

def test_sacrificial_set_scales_faction_bonus():
    mods = [dict(name=n, modSet='S', modSetValues=[0.25, 0.5], faction=dict(sentients=0.32)) for n in ('A', 'B')]
    out = WarframeDamageEngine()._apply_mod_sets(mods)
    assert out[0]['faction']['sentients'] == pytest.approx(0.65)

def test_sibear_toxin_mod_combines_with_innate_cold(idx):
    # Game panel shows Viral on this build. Codex base damage differs from the game (Incarnon), so only the type is pinned.
    el = breakdown(idx, 'Sibear', ['Primed Pressure Point','Blood Rush','Galvanized Reflex','Galvanized Steel','Seismic Wave','Primed Fever Strike','Organ Shatter','Corrupt Charge'])
    assert 'viral' in el['types']
    assert 'cold' not in el['types'] and 'toxin' not in el['types']

@pytest.mark.parametrize("weapon, names, expected", [
    ('Sampotes', ['Primed Pressure Point','Galvanized Elementalist','Organ Shatter','Galvanized Steel','Seismic Wave','Primed Fever Strike','Volcanic Edge','Voltaic Strike'], dict(gas=1478.7, electric=394.3, impact=460.0)),
    ('Ruvox', ['Primed Pressure Point','Galvanized Steel','Weeping Wounds','Galvanized Reflex','Virulent Scourge','Volcanic Edge','Shocking Touch','Seismic Wave'], dict(gas=540.6, electric=405.5, impact=450.5)),
    ('Stropha', ['Sacrificial Pressure','Corrupt Charge','Gladiator Might','Voltaic Strike','Sacrificial Steel','Amalgam Organ Shatter','Killing Blow','Volcanic Edge'], dict(radiation=627.0, impact=146.3, puncture=177.7, slash=198.6)),
    ('Arca Titron', ['Galvanized Reflex','Primed Pressure Point','Blood Rush','Galvanized Steel','Shocking Touch','Galvanized Elementalist','Organ Shatter','Seismic Wave'], dict(electric=858.6, impact=620.1, slash=333.9)),
])
def test_game_panel_types(idx, weapon, names, expected):
    el = breakdown(idx, weapon, names)
    for t, v in expected.items():
        assert el['types'][t] == pytest.approx(v, rel=0.015), t
    assert set(expected) <= set(el['types'])

def test_user_example_blast_and_toxin():
    result = combine_elements([('heat', 0.9), ('cold', 0.9), ('toxin', 0.9)])
    assert result['types'] == dict(blast=1.8, toxin=0.9)
    assert result['pairs'] == [('heat', 'cold', 'blast')]

def test_order_changes_result():
    result = combine_elements([('heat', 1.0), ('toxin', 1.0), ('cold', 1.0)])['types']
    assert result.get('gas') == 2.0
    assert result.get('cold') == 1.0
    assert 'blast' not in result

def test_same_element_keeps_first_position():
    result = combine_elements([('heat', 1.0), ('cold', 1.0), ('heat', 1.0)])['types']
    assert result == dict(blast=3.0)

def test_four_primaries_two_pairs():
    result = combine_elements([('cold', 1), ('toxin', 1), ('heat', 1), ('electric', 1)])['types']
    assert result == dict(viral=2, radiation=2)

def test_prova_innate_last():
    result = combine_elements([('cold', 1.0), ('toxin', 1.0), ('heat', 1.0)], dict(electric=0.5))['types']
    assert result == dict(viral=2.0, radiation=1.5)

def test_mod_pulls_innate_forward():
    result = combine_elements([('electric', 1.0), ('cold', 1.0), ('toxin', 1.0)], dict(electric=0.5))['types']
    assert result == dict(magnetic=2.5, toxin=1.0)

def test_innate_secondary_stays_independent():
    result = combine_elements([('heat', 1.0), ('toxin', 1.0)], dict(blast=0.5))['types']
    assert result == dict(gas=2.0, blast=0.5)

def test_faction_multiplier():
    assert faction_multipliers(dict(corrosive=50.0, slash=50.0))['grineer'] == pytest.approx(1.25)
    assert faction_multipliers(dict(corrosive=50.0, slash=50.0))['infested'] == pytest.approx(1.25)
    assert faction_multipliers(dict(corrosive=50.0, slash=50.0))['sentient'] == pytest.approx(0.75)
    assert faction_multipliers(dict(slash=100.0), dict(infested=0.55))['infested'] == pytest.approx(1.5 * 1.55)

def test_slot_index_sorts_input():
    weapon = dict(name='W', category='Melee', total_damage=100.0, crit_chance=0.1, crit_mult=2.0, fire_rate=1.0, attacks=[dict(damage=dict(slash=100.0))])
    mods = [dict(name='T', toxin=0.9, slot_index=4), dict(name='H', heat=0.9, slot_index=0), dict(name='C', cold=0.9, slot_index=3)]
    result = WarframeDamageEngine().compute_metrics(weapon, mod_objs=mods)['elements']
    assert result['pairs'] == [('heat', 'cold', 'blast')]
    assert result['types']['blast'] == pytest.approx(180.0)
    assert result['types']['toxin'] == pytest.approx(90.0)
    assert result['types']['slash'] == pytest.approx(100.0)

def test_riven_element_uses_riven_slot():
    weapon = dict(name='W', category='Melee', total_damage=100.0, crit_chance=0.1, crit_mult=2.0, fire_rate=1.0, attacks=[dict(damage=dict(slash=100.0))])
    mods = [dict(name='Riven Mod', slot_index=0), dict(name='H', heat=1.0, slot_index=1)]
    riven_stats = dict(toxin=1.0)
    result = WarframeDamageEngine().compute_metrics(weapon, mod_objs=mods, riven_stats=riven_stats)['elements']
    assert result['pairs'] == [('toxin', 'heat', 'gas')]