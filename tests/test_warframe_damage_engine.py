import pytest
import math
from scripts.warframe_damage_engine import WarframeDamageEngine

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

def test_status_dps_metrics_contract_and_reload_uptime():
    engine = WarframeDamageEngine()
    w_meta = {
        'name': 'IgnisSlash',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.0,
        'crit_mult': 2.0,
        'fire_rate': 10.0,
        'base_multishot': 1.0,
        'procChance': 0.50,
        'magazineSize': 30,
        'reloadTime': 2.0,
        'attacks': [{'damage': {'slash': 60.0, 'heat': 40.0}}],
    }
    mods = [
        {'name': 'Hellfire', 'heat': 0.90},
        {'name': 'Rifle Elementalist', 'status_damage': 0.90},
    ]
    m = engine.compute_metrics(w_meta, left_stats={}, mod_objs=mods)

    # Firing 30 / 10 = 3s, reload 2s -> duty cycle = 0.60
    assert m['direct_burst_dps'] == pytest.approx(1900.0)
    assert m['direct_sustained_dps'] == pytest.approx(1140.0)
    # 5 procs/s total; Slash share = 60/190 (ignores +heat mod), Heat share = 130/190 (scaled by 1.9 heat mod)
    exp_slash = 10.0 * 0.50 * (60.0 / 190.0) * (6.0 * 0.35 * 100.0 * 1.90)
    exp_heat = 10.0 * 0.50 * (130.0 / 190.0) * (6.0 * 0.50 * 100.0 * 1.90 * 1.90)
    assert m['status_breakdown']['slash'] == pytest.approx(exp_slash)
    assert m['status_breakdown']['heat'] == pytest.approx(exp_heat)
    assert m['status_dps'] == pytest.approx(exp_slash + exp_heat)
    assert m['status_sustained_dps'] == pytest.approx(m['status_dps'] * 0.60)
    assert m['burst_dps'] == pytest.approx(m['direct_burst_dps'] + m['status_dps'])
    assert m['sustained_dps'] == pytest.approx(m['direct_sustained_dps'] + m['status_sustained_dps'])

def test_explicit_zero_status_disables_natural_dot_but_keeps_hunter_munitions():
    engine = WarframeDamageEngine()
    w_meta = {
        'name': 'CritNoStatus',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.50,
        'crit_mult': 2.0,
        'fire_rate': 2.0,
        'base_multishot': 1.0,
        'procChance': 0.0,
        'attacks': [{'damage': {'slash': 100.0}}],
    }
    plain = engine.compute_metrics(w_meta)
    assert plain['final_status'] == 0.0
    assert plain['status_dps'] == 0.0
    assert plain['burst_dps'] == pytest.approx(plain['direct_burst_dps'])

    hm = engine.compute_metrics(w_meta, mod_objs=[{'name': 'Hunter Munitions'}])
    # HM only procs on crits: when CC=0.50 < 1, every HM proc inherits Tier-1 crit_mult=2.0 (not avg 1.5).
    exp_hm_dps = 2.0 * 0.15 * (6.0 * 0.35 * 100.0 * 2.0)
    assert hm['hunter_munitions']['bleed_tick'] == pytest.approx(0.35 * 100.0 * 2.0)
    assert hm['status_breakdown'] == {'slash': pytest.approx(exp_hm_dps)}
    assert hm['status_dps'] == pytest.approx(exp_hm_dps)
    assert hm['hm_slash_dps'] == pytest.approx(exp_hm_dps)
    assert hm['burst_dps'] == pytest.approx(hm['direct_burst_dps'] + exp_hm_dps)

def test_internal_bleeding_fire_rate_threshold():
    engine = WarframeDamageEngine()
    base_meta = {
        'name': 'ImpactRifle',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.0,
        'crit_mult': 2.0,
        'base_multishot': 1.0,
        'procChance': 0.50,
        'attacks': [{'damage': {'impact': 100.0}}],
    }
    slow = engine.compute_metrics({**base_meta, 'fire_rate': 2.0}, mod_objs=[{'name': 'Internal Bleeding'}])
    fast = engine.compute_metrics({**base_meta, 'fire_rate': 3.0}, mod_objs=[{'name': 'Internal Bleeding'}])
    # < 2.5 fire rate triggers 70% bleed on impact proc; >= 2.5 triggers 35%
    assert slow['status_breakdown']['slash'] == pytest.approx(2.0 * (0.50 * 0.70) * (6.0 * 0.35 * 100.0))
    assert fast['status_breakdown']['slash'] == pytest.approx(3.0 * (0.50 * 0.35) * (6.0 * 0.35 * 100.0))

def test_valence_scales_status_base_and_faction_double_dips():
    engine = WarframeDamageEngine()
    w_meta = {
        'name': 'KuvaSlasher',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.0,
        'crit_mult': 2.0,
        'fire_rate': 1.0,
        'base_multishot': 1.0,
        'procChance': 0.50,
        'attacks': [{'damage': {'slash': 100.0}}],
    }
    bane = [{'name': 'Primed Bane of Grineer', 'faction': {'grineer': 0.55}}]
    neutral = engine.compute_metrics(w_meta, left_stats={'valence_heat': 0.60}, mod_objs=bane)
    vs_grineer = engine.compute_metrics(w_meta, left_stats={'valence_heat': 0.60}, mod_objs=bane, target_faction='grineer')
    riven_fac = engine.compute_metrics(w_meta, riven_stats={'faction_damage': 0.50})

    # Valence scales modded_base by 1.6 and shares weight 1.0 / 1.6 Slash + 0.6 / 1.6 Heat
    exp_neutral_status = 0.50 * (
        (1.0 / 1.6) * (6.0 * 0.35 * 160.0) + (0.6 / 1.6) * (6.0 * 0.50 * 160.0)
    )
    assert neutral['status_dps'] == pytest.approx(exp_neutral_status)
    assert vs_grineer['direct_burst_dps'] == pytest.approx(neutral['direct_burst_dps'] * 1.55)
    assert vs_grineer['status_dps'] == pytest.approx(neutral['status_dps'] * (1.55 ** 2))
    assert neutral['faction_status_dps']['grineer'] == pytest.approx(vs_grineer['status_dps'])

    # With target_faction='grineer', faction_status_dps must not double-count Grineer bane or leak it to Corpus
    slash_only = {**w_meta, 'attacks': [{'damage': {'slash': 100.0}}]}
    vs_g_slash = engine.compute_metrics(slash_only, mod_objs=bane, target_faction='grineer')
    plain_slash = engine.compute_metrics(slash_only)
    assert vs_g_slash['status_dps'] == pytest.approx(plain_slash['status_dps'] * (1.55 ** 2))
    assert vs_g_slash['faction_status_dps']['grineer'] == pytest.approx(vs_g_slash['status_dps'])
    assert vs_g_slash['faction_status_dps']['corpus'] == pytest.approx(plain_slash['status_dps'])

    full_vs_g = engine.compute_full_stack(slash_only, mod_objs=bane, target_faction='grineer')
    assert full_vs_g['faction_status_dps']['grineer'] == pytest.approx(full_vs_g['status_dps'])
    assert full_vs_g['faction_status_dps']['corpus'] == pytest.approx(plain_slash['status_dps'])

    # Riven faction_damage=0.5 applies once to direct, squared to status DoT
    assert riven_fac['status_dps'] == pytest.approx(0.50 * 6.0 * 0.35 * 100.0 * (1.5 ** 2))

def test_compute_full_stack_includes_status_dots_galvanized_and_melee_exposure():
    engine = WarframeDamageEngine()
    gun = {
        'name': 'StatusRifle',
        'category': 'Primary',
        'total_damage': 100.0,
        'crit_chance': 0.0,
        'crit_mult': 2.0,
        'fire_rate': 5.0,
        'base_multishot': 1.0,
        'procChance': 0.25,
        'magazineSize': 30,
        'reloadTime': 2.0,
        'attacks': [{'damage': {'slash': 100.0}}],
    }
    gun_mods = [
        {'name': 'Galvanized Elementalist', 'status_damage': 0.80, 'on_kill': [{'stat': 'status', 'value': 0.30, 'stacks': 4}]},
        {'name': 'Galvanized Aptitude', 'status': 0.80, 'on_kill': [{'stat': 'status_type_direct', 'value': 0.40, 'stacks': 2}]},
    ]
    full_gun = engine.compute_full_stack(
        gun,
        mod_objs=gun_mods,
        arcane={'name': 'Primary Merciless', 'damage_per_stack': 0.30, 'max_stacks': 12},
        status_types=3,
    )
    # Status chance: 0.25 * (1 + 0.80 + 1.20) = 0.75; buff_dmg: 3.6 + 2.4 = 6.0 (7x base)
    assert full_gun['final_status'] == pytest.approx(0.75)
    exp_gun_status = 5.0 * 0.75 * (6.0 * 0.35 * 700.0 * 1.80)
    assert full_gun['status_dps'] == pytest.approx(exp_gun_status)
    assert full_gun['direct_burst_dps'] == pytest.approx(5.0 * 700.0)
    assert full_gun['burst_dps'] == pytest.approx(full_gun['direct_burst_dps'] + exp_gun_status)
    assert full_gun['sustained_dps'] == pytest.approx(full_gun['direct_sustained_dps'] + full_gun['status_sustained_dps'])

    melee = {
        'name': 'StatusSword',
        'category': 'Melee',
        'total_damage': 100.0,
        'crit_chance': 0.0,
        'crit_mult': 2.0,
        'fire_rate': 1.0,
        'procChance': 0.20,
        'attacks': [{'damage': {'slash': 100.0}}],
    }
    melee_mods = [
        {'name': 'Weeping Wounds', 'combo_status': 0.40},
        {'name': 'Condition Overload', 'status_type_damage': 0.80},
    ]
    full_melee = engine.compute_full_stack(
        melee,
        mod_objs=melee_mods,
        arcane={'name': 'Melee Exposure', 'elemental_per_stack': 0.60, 'max_stacks': 4},
        combo_mult=12.0,
        status_types=3,
    )
    # 0.20 * (1 + 0.40 * 11) = 1.08 SC; CO adds +2.4 base dmg (3.4x); Melee Exposure adds +2.4 Corrosive -> slash share 1 / 3.4
    assert full_melee['final_status'] == pytest.approx(1.08)
    exp_melee_status = 1.0 * 1.08 * (1.0 / 3.4) * (6.0 * 0.35 * 340.0)
    assert full_melee['status_dps'] == pytest.approx(exp_melee_status)
    assert full_melee['sustained_dps'] == pytest.approx(full_melee['burst_dps'])


def test_charge_time_falls_back_to_database_attack():
    engine = WarframeDamageEngine()
    bow = {'name': 'TestBow', 'category': 'Primary', 'type': 'Bow', 'total_damage': 60.0, 'crit_chance': 0.5,
           'crit_mult': 2.0, 'fire_rate': 1.0, 'magazineSize': 1, 'reloadTime': 0.6,
           'attacks': [{'name': 'Charged Shot', 'charge_time': 1.2, 'damage': {'impact': 50.0}},
                       {'name': 'Initial Blast', 'charge_time': 1.2, 'damage': {'cold': 10.0}}]}
    m = engine.compute_metrics(bow, left_stats={}, mod_objs=[])
    # Charge-per-shot bow cadence: burst rate = 1/charge_time, sustained = 1/(charge_time + reload_time).
    assert m['effective_fire_rate'] == pytest.approx(1.0 / 1.2)
    assert m['effective_fire_rate'] * m['shooting_proportion'] == pytest.approx(1.0 / (1.2 + 0.6))
    # Speed Trigger (+60% FR, x2 for Bows -> +120% -> 2.2x) shortens charge to 1.2 / 2.2.
    fast = engine.compute_metrics(bow, left_stats={}, mod_objs=[{'name': 'Speed Trigger', 'fire_rate': 0.6}])
    assert fast['effective_fire_rate'] == pytest.approx(2.2 / 1.2)
    # The attack total_damage describes decides: an uncharged main attack has no charge.
    quick = dict(bow, total_damage=450.0, attacks=[{'name': 'Quick Shot', 'damage': {'slash': 450.0}},
                                                   {'name': 'Charged Shot', 'charge_time': 1.0, 'damage': {'slash': 900.0}}])
    assert engine.compute_metrics(quick, left_stats={}, mod_objs=[])['effective_fire_rate'] == pytest.approx(1.0)


def test_heavy_attack_falls_back_to_database_value():
    engine = WarframeDamageEngine()
    sword = {'name': 'TestSword', 'category': 'Melee', 'total_damage': 280.0, 'crit_chance': 0.26, 'crit_mult': 2.0,
             'fire_rate': 1.0, 'heavy_damage': 1680.0, 'attacks': [{'name': 'Normal Attack', 'damage': {'slash': 280.0}}]}
    m = engine.compute_metrics(sword, left_stats={}, mod_objs=[{'name': 'Pressure Point', 'damage': 1.2}])
    assert m['heavy']['heavy_hit'] == pytest.approx(1680.0 * 2.2)
    fs = engine.compute_full_stack(sword, left_stats={}, mod_objs=[{'name': 'Pressure Point', 'damage': 1.2}])
    assert fs['heavy_hit'] > m['heavy']['heavy_hit']


def test_indexer_keeps_heavy_damage_and_attack_charge_time():
    from scripts.wf_data_indexer import WFDataIndexer
    indexer = WFDataIndexer()
    assert indexer.weapons_index['galatine prime']['heavy_damage'] == pytest.approx(1680.0)
    assert WarframeDamageEngine._db_charge_time(indexer.weapons_index['lenz']) == pytest.approx(1.2)


def test_multi_pellet_shotgun_uses_per_pellet_base_damage():
    from scripts.wf_data_indexer import WFDataIndexer
    idx = WFDataIndexer()
    eng = WarframeDamageEngine()

    corinth = idx.weapons_index['corinth prime']
    m0 = eng.compute_metrics(corinth)
    # Corinth Prime: 90/pellet * 6 pellets = 540 total damage per shot.
    assert m0['per_pellet_dmg'] == pytest.approx(90.0)
    assert m0['final_dmg'] == pytest.approx(540.0)

    mods = [dict(idx.mods_index[n]) for n in ('primed point blank', 'galvanized hell', 'hunter munitions')]
    m1 = eng.compute_metrics(corinth, mod_objs=mods)
    # 90 * (1 + 1.65) = 238.5 per pellet; 6 * (1 + 1.1) = 12.6 pellets -> 3005.1 total.
    assert m1['per_pellet_dmg'] == pytest.approx(238.5)
    assert m1['final_ms'] == pytest.approx(12.6)
    assert m1['final_dmg'] == pytest.approx(238.5 * 12.6)
    # HM bleed tick uses per-pellet modded base (238.5) and Tier-1 crit_mult (2.8x since CC=0.3 < 1).
    assert m1['hunter_munitions']['bleed_tick'] == pytest.approx(0.35 * 238.5 * 2.8)

    strun = idx.weapons_index['strun prime']
    ms = eng.compute_metrics(strun)
    assert ms['per_pellet_dmg'] == pytest.approx(54.0)
    assert ms['final_dmg'] == pytest.approx(54.0 * 12.0)


def test_valence_scales_base_before_elementals_and_impact_valence():
    eng = WarframeDamageEngine()
    w = {
        'name': 'KuvaTest', 'category': 'Secondary', 'total_damage': 100.0,
        'crit_chance': 0.0, 'crit_mult': 2.0, 'fire_rate': 1.0, 'base_multishot': 1.0,
        'attacks': [{'damage': {'slash': 100.0}}],
    }
    # +60% Heat Valence -> 160 effective base; +90% Cold + +90% Toxin -> 160 * 2.8 = 448.
    m = eng.compute_metrics(w, left_stats={'valence_heat': 0.60}, mod_objs=[
        {'name': 'C', 'cold': 0.90, 'slot_index': 0},
        {'name': 'T', 'toxin': 0.90, 'slot_index': 1},
    ])
    assert m['final_dmg'] == pytest.approx(448.0)
    assert m['elements']['types']['viral'] == pytest.approx(288.0)
    assert m['elements']['types']['heat'] == pytest.approx(60.0)
    assert m['elements']['types']['slash'] == pytest.approx(100.0)

    # +60% Heat Valence + +120% Slash + +90% Cold: Slash mod scales 100 only (+120), Cold scales 160 (+144) -> 424.
    m_phys = eng.compute_metrics(w, left_stats={'valence_heat': 0.60}, mod_objs=[
        {'name': 'S', 'slash': 1.20, 'slot_index': 0},
        {'name': 'C', 'cold': 0.90, 'slot_index': 1},
    ])
    assert m_phys['final_dmg'] == pytest.approx(424.0)

    # +60% Impact Valence on 100 Impact weapon: +120% Impact mod scales all 160 Impact -> 352.
    w_imp = dict(w, attacks=[{'damage': {'impact': 100.0}}])
    m_imp = eng.compute_metrics(w_imp, left_stats={'valence_impact': 0.60}, mod_objs=[{'name': 'I', 'impact': 1.20}])
    assert m_imp['final_dmg'] == pytest.approx(352.0)
    assert m_imp['elements']['types']['impact'] == pytest.approx(352.0)


def test_melee_animosity_scales_by_base_cc_and_killing_blow_and_initial_combo():
    eng = WarframeDamageEngine()
    scythe = {
        'name': 'TestScythe', 'category': 'Melee', 'total_damage': 200.0,
        'heavy_damage': 1200.0, 'crit_chance': 0.20, 'crit_mult': 2.0, 'fire_rate': 1.0,
        'attacks': [{'damage': {'slash': 200.0}}],
    }
    mods = [
        {'name': 'Pressure Point', 'damage': 1.20},
        {'name': 'Killing Blow', 'heavy_damage_bonus': 1.20},
        {'name': 'Corrupt Charge', 'initial_combo': 30.0},
    ]
    m = eng.compute_metrics(scythe, mod_objs=mods)
    # Killing Blow additive with Pressure Point (1 + 1.2 + 1.2 = 3.4); Corrupt Charge +30 -> 2x initial combo.
    assert m['heavy']['heavy_hit'] == pytest.approx(1200.0 * 3.4 * 2.0)
    assert m['heavy']['initial_combo_mult'] == pytest.approx(2.0)

    # Melee Animosity R5 (+42% * 10 = +420%) scales base_cc (0.20 * 4.2 = +0.84 -> 1.04 CC), NOT flat +4.20!
    fs = eng.compute_full_stack(
        scythe, mod_objs=mods,
        arcane={'name': 'Melee Animosity', 'heavy_crit_per_stack': 0.42, 'max_stacks': 10},
        combo_mult=12.0,
    )
    expected_heavy_cc = 0.20 + 0.20 * 4.20
    assert fs['heavy_cc'] == pytest.approx(expected_heavy_cc)
    assert fs['heavy_hit'] == pytest.approx(1200.0 * 3.4 * 12.0 * (1.0 + expected_heavy_cc * 1.0))


def test_beam_weapon_multishot_squared_dot_and_explicit_arcane_element():
    eng = WarframeDamageEngine()
    beam = {
        'name': 'BeamGun', 'category': 'Secondary', 'trigger': 'Held', 'is_beam': True,
        'total_damage': 20.0, 'crit_chance': 0.0, 'crit_mult': 2.0, 'fire_rate': 10.0,
        'base_multishot': 1.0, 'procChance': 0.50, 'magazineSize': 100, 'reloadTime': 2.0,
        'attacks': [{'damage': {'heat': 20.0}}],
    }
    m = eng.compute_metrics(beam, mod_objs=[{'name': 'Diffusion', 'multishot': 2.0}])
    # final_ms = 3.0; Beam Heat DoT double-dips MS: (10 * 0.5 * 3.0) procs/s * (6 * 0.5 * (20 * 3.0)).
    assert m['is_beam'] is True
    assert m['status_breakdown']['heat'] == pytest.approx(10.0 * 0.50 * 3.0 * (6.0 * 0.50 * 60.0))

    # Explicit arcane['element'] routes elemental arcane share to that element (not hardcoded corrosive).
    fs = eng.compute_full_stack(
        beam,
        arcane={'name': 'HeatArcane', 'element': 'electric', 'elemental_per_stack': 0.50, 'max_stacks': 2},
    )
    assert 'electric' in fs['status_breakdown']


def test_paired_direct_radial_scopes_ips_gunco_and_internal_bleeding():
    from scripts.wf_data_indexer import WFDataIndexer
    idx = WFDataIndexer()
    eng = WarframeDamageEngine()
    zarr = idx.weapons_index['kuva zarr']  # 50 Impact direct + 673 Blast radial = 723

    # +120% Impact mod scales only the 50 Impact shell (+60), NOT the 673 Blast radial!
    m_imp = eng.compute_metrics(zarr, mod_objs=[{'name': 'Crash Course', 'impact': 1.20}])
    assert m_imp['final_dmg'] == pytest.approx(723.0 + 60.0)

    # Internal Bleeding bleed tick derives from the 50 Impact direct hit (not 723 total), and radial rolls Blast DoT.
    m_ib = eng.compute_metrics(zarr, mod_objs=[{'name': 'Internal Bleeding'}])
    exp_crit = 1.0 + 0.25 * (2.5 - 1.0)
    assert m_ib['hunter_munitions']['bleed_tick'] == pytest.approx(0.35 * 50.0 * exp_crit)
    assert m_ib['status_breakdown'].get('blast', 0.0) > 0.0

    # GunCO scales ONLY the 50 direct hit, not the 673 radial explosion.
    fs = eng.compute_full_stack(
        zarr,
        mod_objs=[{'name': 'Galvanized Aptitude', 'status': 0.8, 'on_kill': [{'stat': 'status_type_direct', 'value': 0.4, 'stacks': 2}]}],
        status_types=3,
    )
    # Direct: 50 * (1 + 2.4) = 170; Radial: 673 * 1.0 = 673 -> total 843.
    assert fs['final_dmg'] == pytest.approx(50.0 * 3.4 + 673.0)


def test_incarnon_aoe_and_full_stack_respects_lock_multishot():
    eng = WarframeDamageEngine()
    w = {
        'name': 'TestIncarnon', 'category': 'Secondary', 'total_damage': 100.0,
        'crit_chance': 0.20, 'crit_mult': 2.0, 'fire_rate': 2.0, 'base_multishot': 1.0,
        'procChance': 0.20, 'magazineSize': 12, 'reloadTime': 2.0,
        'attacks': [{'name': 'Normal', 'damage': {'slash': 100.0}}],
        'incarnon_attack': {'name': 'Incarnon Form', 'damage': {'impact': 100.0}, 'crit_chance': 20, 'crit_mult': 2.0, 'speed': 5.0},
        'incarnon_aoe': {'name': 'Incarnon Radial', 'damage': {'radiation': 300.0}, 'crit_chance': 20, 'crit_mult': 2.0, 'speed': 5.0},
    }
    m = eng.compute_metrics(w, mod_objs=[
        {'name': 'Pistol Acuity', 'weak_point_damage': 3.5, 'weak_point_crit_chance': 3.5, 'lock_multishot': True},
        {'name': 'Barrel Diffusion', 'multishot': 1.2},
    ])
    # Acuity locks Incarnon multishot to 1.0; expected_hit sums direct (100) + aoe (300) = 400 * 1.2 crit = 480.
    assert m['incarnon']['final_ms'] == pytest.approx(1.0)
    assert m['incarnon']['direct_expected_hit'] == pytest.approx(120.0)
    assert m['incarnon']['aoe_expected_hit'] == pytest.approx(360.0)
    assert m['incarnon']['expected_hit'] == pytest.approx(480.0)


def test_meta_mod_hooks_cannonade_vigilante_berserker_deadhead_and_ui_keys():
    eng = WarframeDamageEngine()
    rifle = {
        'name': 'SemiRifle', 'category': 'Primary', 'type': 'Rifle', 'total_damage': 100.0,
        'crit_chance': 0.50, 'crit_mult': 3.0, 'fire_rate': 4.0, 'base_multishot': 1.0,
        'procChance': 0.50, 'magazineSize': 20, 'reloadTime': 2.0,
        'attacks': [{'damage': {'slash': 50.0, 'heat': 50.0}}],
    }
    # Semi-Rifle Cannonade locks fire rate even with Critical Delay (-20% FR); Vigilante adds +10% crit tier upgrade.
    m = eng.compute_metrics(
        rifle,
        mod_objs=[
            {'name': 'Semi-Rifle Cannonade', 'damage': 2.4, 'lock_fire_rate': True},
            {'name': 'Critical Delay', 'crit_chance': 2.0, 'fire_rate': -0.20},
            {'name': 'Vigilante Armaments', 'multishot': 0.6, 'modSet': 'VigilanteSetMod'},
            {'name': 'Vigilante Supplies', 'modSet': 'VigilanteSetMod'},
        ],
        arcane={'name': 'Primary Deadhead', 'damage_per_stack': 1.2, 'max_stacks': 3, 'headshot_bonus': 0.30},
    )
    assert m['lock_fire_rate'] is True
    assert m['final_fr'] == pytest.approx(4.0)
    assert m['vigilante_chance'] == pytest.approx(0.10)
    # Passive Deadhead +30% headshot multiplier applies even in unstacked compute_metrics.
    assert m['wp_mult'] == pytest.approx(3.0 * 1.30)
    # UI parity Slash vs non-Slash sustained DoT keys sum to status_sustained_dps.
    assert m['slash_status_sustained_dps'] > 0.0
    assert m['non_slash_status_sustained_dps'] > 0.0
    assert m['slash_status_sustained_dps'] + m['non_slash_status_sustained_dps'] == pytest.approx(m['status_sustained_dps'])
    assert m['headshot_ratio'] == pytest.approx(m['headshot_expected_hit'] / m['expected_hit'])

    # Berserker Fury on_kill attack_speed raises full-stack fire rate & burst DPS on Melee.
    sword = {'name': 'S', 'category': 'Melee', 'total_damage': 100.0, 'crit_chance': 0.2, 'crit_mult': 2.0, 'fire_rate': 1.0}
    bf = [{'name': 'Berserker Fury', 'on_kill': [{'stat': 'attack_speed', 'value': 0.35, 'stacks': 2}]}]
    fs_m = eng.compute_full_stack(sword, mod_objs=bf)
    assert fs_m['final_fr'] == pytest.approx(1.70)
    assert fs_m['burst_dps'] == pytest.approx(100.0 * 1.2 * 1.70)


def test_float32_crit_ceil_epsilon_and_negative_multishot_clamping():
    eng = WarframeDamageEngine()
    # WFCD float32 crit_chance=0.40000001 * 2.5 = 1.000000025 must stay Tier 1 Yellow, not jump to Tier 2 Orange!
    w = {
        'name': 'FloatGun', 'category': 'Primary', 'total_damage': 100.0,
        'crit_chance': 0.40000001, 'crit_mult': 3.0, 'fire_rate': 1.0, 'base_multishot': 1.0,
    }
    m = eng.compute_metrics(w, mod_objs=[{'name': 'Point Strike', 'crit_chance': 1.5}])
    assert m['max_crit_hit'] == pytest.approx(300.0)
    assert m['min_hit'] == pytest.approx(300.0)

    # Negative multishot riven (<1.0): trough=0 (misfire), peak=1 pellet, expected=0.6 pellet.
    m_neg_ms = eng.compute_metrics(dict(w, crit_chance=0.0), riven_stats={'multishot': -0.4})
    assert m_neg_ms['ms_min_pellets'] == 0
    assert m_neg_ms['ms_max_pellets'] == 1
    assert m_neg_ms['min_hit'] == pytest.approx(0.0)
    assert m_neg_ms['expected_hit'] == pytest.approx(60.0)
    assert m_neg_ms['max_non_crit'] == pytest.approx(100.0)

    # Huge negative damage clamps to 0.0 instead of negative damage.
    m_neg_dmg = eng.compute_metrics(dict(w, crit_chance=0.0), riven_stats={'damage': -1.5})
    assert m_neg_dmg['final_dmg'] == 0.0


def test_slice1_slice2_real_weapons_integration():
    from scripts.wf_data_indexer import WFDataIndexer
    idx = WFDataIndexer()
    eng = WarframeDamageEngine()

    # Laetum: Incarnon AoE (300 Rad) + Devouring Attrition (50% chance +2000% on non-crit).
    laetum = idx.weapons_index['laetum']
    lm = eng.compute_metrics(laetum, mod_objs=[dict(idx.mods_index['hornet strike'])])
    assert lm['incarnon']['aoe_expected_hit'] > 0.0
    assert lm['incarnon']['attrition_applied'] is True
    assert lm['incarnon']['expected_hit'] > lm['expected_hit']

    # Glaive Prime: Killing Blow + Corrupt Charge + forced heavy slash proc from innate traits.
    gp = idx.weapons_index['glaive prime']
    gp_mods = [dict(idx.mods_index[n]) for n in ('primed pressure point', 'killing blow', 'corrupt charge')]
    gm = eng.compute_metrics(gp, mod_objs=gp_mods)
    assert gm['heavy']['initial_combo_mult'] == pytest.approx(2.0)
    assert gm['heavy']['forced_proc']['type'] == 'slash'
    assert gm['heavy']['forced_proc']['tick'] > 0.0

    # Nataruk: Multiplicative GunCO + Bow 2x Vile Acceleration.
    nat = idx.weapons_index['nataruk']
    nm_mods = [dict(idx.mods_index[n]) for n in ('serration', 'galvanized aptitude', 'vile acceleration')]
    nm_base = eng.compute_metrics(nat, mod_objs=nm_mods)
    nm_fs = eng.compute_full_stack(nat, mod_objs=nm_mods, status_types=3)
    # Multiplicative GunCO: Serration (+1.65) - Vile Accel (-0.15) = 2.5x base, * (1 + 2.4) = 3.4x ratio!
    assert nm_fs['final_dmg'] == pytest.approx(nm_base['final_dmg'] * 3.4)

    # Cedo: innate GunCO (+60%/status) active in full_stack even without Galvanized Savvy.
    cedo = idx.weapons_index['cedo']
    cm_base = eng.compute_metrics(cedo)
    cm_fs = eng.compute_full_stack(cedo, status_types=4)
    assert cm_fs['final_dmg'] == pytest.approx(cm_base['final_dmg'] * (1.0 + 0.60 * 4))

    # Kuva Nukor: hidden_status_types (+1 Microwave) boosts Galvanized Shot + beam multishot² DoT.
    nukor = idx.weapons_index['kuva nukor']
    assert nukor['is_beam'] is True
    nk_mods = [dict(idx.mods_index[n]) for n in ('galvanized shot', 'galvanized diffusion')]
    nk_fs = eng.compute_full_stack(nukor, left_stats={'valence_heat': 0.60}, mod_objs=nk_mods, status_types=3)
    # 3 + 1 Microwave = 4 statuses -> +120% * 4 = +480% base dmg (5.8x)
    assert nk_fs['final_dmg'] / eng.compute_metrics(nukor, left_stats={'valence_heat': 0.60}, mod_objs=nk_mods)['final_dmg'] == pytest.approx(5.8 * (3.3 / 2.1))
