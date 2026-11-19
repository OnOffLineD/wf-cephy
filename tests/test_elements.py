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

def test_innate_electricity_key_combines():
    weapon = _weapon(attacks=[dict(damage=dict(electricity=100.0))])
    el = WarframeDamageEngine().compute_metrics(weapon, mod_objs=[dict(name='T', toxin=1.0, slot_index=0)])['elements']
    assert el['pairs'] == [('toxin', 'electric', 'corrosive')]

def test_valence_acts_as_innate_element():
    weapon = _weapon(attacks=[dict(damage=dict(impact=100.0))])
    left = dict(valence_toxin=0.5)
    el = WarframeDamageEngine().compute_metrics(weapon, left_stats=left, mod_objs=[dict(name='C', cold=1.0, slot_index=0)])['elements']
    assert el['pairs'] == [('cold', 'toxin', 'viral')]
    # Valence increases base damage to 150 (100 impact + 50 toxin), so +100% cold adds 150 cold -> 200 viral.
    assert el['types']['viral'] == pytest.approx(200.0)
    assert el['types']['impact'] == pytest.approx(100.0)

def test_multi_attack_weapon_uses_first_attack_only(idx):
    # Kuva Zarr total 723 mixes the 50 Impact shell with its 673 Blast explosion. Game panel shows Impact 210.1 per shell.
    mods = [idx.mods_index[n.lower()] for n in ['Amalgam Serration', 'Heavy Caliber']]
    el = WarframeDamageEngine().compute_metrics(idx.fuzzy_match_weapon('Kuva Zarr'), left_stats=dict(multishot=1.0), mod_objs=mods)['elements']
    assert el['first_attack_only'] is True
    assert el['types']['impact'] == pytest.approx(210.0)

def test_sacrificial_set_scales_faction_bonus():
    # Wiki: Sacrificial set scales the bonus (+32% * 1.25 = +40%), not (1 + 0.32) * 1.25 - 1.
    mods = [dict(name=n, modSet='S', modSetValues=[0.25, 0.5], faction=dict(sentients=0.32)) for n in ('A', 'B')]
    out = WarframeDamageEngine()._apply_mod_sets(mods)
    assert out[0]['faction']['sentients'] == pytest.approx(0.40)

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

def test_full_stack_keeps_riven_slot_for_element_order():
    weapon = dict(name='W', category='Primary', type='Rifle', total_damage=100.0, crit_chance=0.2, crit_mult=2.0,
                  fire_rate=5.0, procChance=0.3, magazineSize=30, reloadTime=2.0,
                  attacks=[dict(damage=dict(impact=50.0, puncture=50.0))])
    mods = [dict(name='Riven Mod', slot_index=0), dict(name='C', cold=0.9, slot_index=1), dict(name='H', heat=0.9, slot_index=2)]
    riven = dict(toxin=0.9)
    engine = WarframeDamageEngine()
    metrics = engine.compute_metrics(weapon, mod_objs=mods, riven_stats=riven)
    full = engine.compute_full_stack(weapon, mod_objs=mods, riven_stats=riven)
    # Riven toxin sits in slot 0, so it pairs with cold (viral) and heat is left over.
    assert metrics['elements']['pairs'] == [('toxin', 'cold', 'viral')]
    assert full['status_breakdown'] == pytest.approx(metrics['status_breakdown'])
    assert full['burst_dps'] == pytest.approx(metrics['burst_dps'])


def test_riven_faction_damage_included_in_elements_faction_multipliers():
    weapon = _weapon(attacks=[dict(damage=dict(slash=100.0))])
    el = WarframeDamageEngine().compute_metrics(weapon, riven_stats={'faction_damage': 0.50})['elements']
    assert el['faction_multipliers']['grineer'] == pytest.approx(1.50)
    assert el['faction_multipliers']['infested'] == pytest.approx(1.5 * 1.50)
