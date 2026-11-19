import pytest

from scripts.wf_data_indexer import WFDataIndexer
from scripts.warframe_damage_engine import WarframeDamageEngine
from scripts.screen_mod_analyzer import ScreenModAnalyzer


RIFLE = {
    'name': 'TestRifle',
    'category': 'Primary',
    'total_damage': 100.0,
    'crit_chance': 0.30,
    'crit_mult': 2.5,
    'fire_rate': 5.0,
    'base_multishot': 1.0,
    'magazineSize': 30,
    'reloadTime': 2.0,
}


@pytest.fixture(scope='module')
def indexer():
    return WFDataIndexer()


def _mods(indexer, *names):
    return [dict(indexer.mods_index[n]) for n in names]


@pytest.mark.parametrize('name', ['primary acuity', 'pistol acuity'])
def test_acuity_indexing(indexer, name):
    mod = indexer.mods_index[name]
    assert mod['weak_point_damage'] == pytest.approx(3.5)
    assert mod['weak_point_crit_chance'] == pytest.approx(3.5)
    assert mod['lock_multishot'] is True


def test_headshot_and_weak_point_phrases_indexed(indexer):
    # Target Acquired grants +60% to Headshot Multiplier (multiplicative bucket, like Deadhead), not additive weak_point_damage.
    assert indexer.mods_index['target acquired']['headshot_bonus'] == pytest.approx(0.6)
    assert indexer.mods_index['target acquired']['weak_point_damage'] == 0.0
    assert indexer.mods_index['meticulous aim']['weak_point_damage'] == pytest.approx(1.05)
    serration = indexer.mods_index['serration']
    assert serration['weak_point_crit_chance'] == 0.0
    assert serration['lock_multishot'] is False


def test_target_acquired_headshot_bonus_multiplies_weak_point(indexer):
    engine = WarframeDamageEngine()
    sniper = dict(RIFLE, type='Sniper')
    mods = _mods(indexer, 'target acquired')
    m = engine.compute_metrics(sniper, mod_objs=mods)
    # 3.0 base headshot * (1 + 0.60) = 4.80x (NOT 3.0 + 1.5*0.60 = 3.90x).
    assert m['wp_mult'] == pytest.approx(4.8)
    # Stacks additively with Primary Deadhead passive +30% -> 3.0 * (1 + 0.60 + 0.30) = 5.70x.
    m_dh = engine.compute_metrics(sniper, mod_objs=mods, arcane={'name': 'Primary Deadhead', 'headshot_bonus': 0.30})
    assert m_dh['wp_mult'] == pytest.approx(5.7)


def test_acuity_locks_multishot(indexer):
    engine = WarframeDamageEngine()
    free = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=_mods(indexer, 'serration', 'split chamber'))
    assert free['final_ms'] == pytest.approx(1.9)
    assert free['lock_multishot'] is False

    locked = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=_mods(indexer, 'primary acuity', 'serration', 'split chamber'),
                                    riven_stats={'multishot': 1.0})
    assert locked['lock_multishot'] is True
    assert locked['final_ms'] == pytest.approx(RIFLE['base_multishot'])
    assert locked['final_dmg'] == pytest.approx(100.0 * 2.65)

    by_name = engine.compute_metrics(RIFLE, left_stats={'multishot': 3.0}, mod_objs=[{'name': 'Pistol Acuity'}, {'name': 'Barrel Diffusion', 'multishot': 1.2}])
    assert by_name['lock_multishot'] is True
    assert by_name['final_ms'] == pytest.approx(1.0)


def test_weak_point_headcrit_peak(indexer):
    engine = WarframeDamageEngine()
    mods = _mods(indexer, 'primary acuity', 'serration', 'split chamber', 'point strike', 'vital sense')
    m = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=mods)

    assert m['wp_mult'] == pytest.approx(8.25)
    assert m['final_cc'] == pytest.approx(0.75)
    assert m['final_cc_wp'] == pytest.approx(0.75 + 0.30 * 3.5)
    final_cd = 2.5 * 2.2
    assert m['final_cd'] == pytest.approx(final_cd)

    max_crit_wp = 1.0 + 2 * (final_cd - 1.0)
    assert m['headshot_max_crit_hit'] == pytest.approx(265.0 * 8.25 * max_crit_wp * 2.0)
    assert m['headshot_max_crit_hit'] > 30000
    assert m['headshot_max_crit_hit'] > m['max_crit_hit'] * 8.25 * 2.0
    assert m['headshot_min_hit'] == pytest.approx(265.0 * 8.25 * (1.0 + 1 * (final_cd - 1.0)) * 2.0)
    assert m['headshot_expected_hit'] == pytest.approx(265.0 * 8.25 * (1.0 + 1.8 * (final_cd - 1.0)) * 2.0)
    assert m['headshot_burst_dps'] == pytest.approx(m['headshot_expected_hit'] * m['effective_fire_rate'])


def test_melee_has_no_weak_point_scaling():
    engine = WarframeDamageEngine()
    sword = dict(RIFLE, name='TestSword', category='Melee')
    m = engine.compute_metrics(sword, left_stats={}, mod_objs=[{'name': 'Pressure Point', 'damage': 1.2}])
    assert m['wp_mult'] == 1.0
    assert m['headshot_max_crit_hit'] == m['max_crit_hit']


def test_report_shows_headshot_peak_and_acuity_notice(indexer):
    analyzer = ScreenModAnalyzer()
    engine = WarframeDamageEngine()
    mods = _mods(indexer, 'primary acuity', 'serration', 'split chamber', 'point strike', 'vital sense')
    m = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=mods)

    briefing = analyzer.format_ordis_briefing(RIFLE, ['Primary Acuity', 'Serration'], m)
    assert '🎯 헤드샷 최고점 (약점 치명타 최고 롤)' in briefing
    assert f"{m['headshot_max_crit_hit']:,.0f}" in briefing
    assert '멀티샷 고정' in briefing
    assert briefing.index('🔥 최고점') < briefing.index('헤드샷 최고점')

    base = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=mods)
    with_riven = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=mods, riven_stats={'crit_damage': 1.0})
    report = analyzer.format_riven_comparison_report(RIFLE, 'Riven', {'crit_damage': 1.0}, base, with_riven)
    expected = (f"{base['max_crit_hit']:,.0f} ➔ **{with_riven['max_crit_hit']:,.0f}** "
                f"(헤드샷: {base['headshot_max_crit_hit']:,.0f} ➔ **{with_riven['headshot_max_crit_hit']:,.0f}**)")
    assert expected in report

    plain = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=_mods(indexer, 'serration'))
    assert '멀티샷 고정' not in analyzer.format_ordis_briefing(RIFLE, ['Serration'], plain)


def test_headcrit_bonus_only_applies_to_crits():
    engine = WarframeDamageEngine()
    no_crit = engine.compute_metrics(dict(RIFLE, crit_chance=0.0), left_stats={}, mod_objs=[])
    # Without any crit, a headshot is the plain 3x weak point hit, never the 2x headcrit on top.
    assert no_crit['headshot_expected_hit'] == pytest.approx(no_crit['expected_hit'] * 3.0)
    assert no_crit['headshot_min_hit'] == pytest.approx(no_crit['min_hit'] * 3.0)
    assert no_crit['headshot_max_crit_hit'] == pytest.approx(no_crit['max_non_crit'] * 3.0)

    m = engine.compute_metrics(RIFLE, left_stats={}, mod_objs=[])  # 30% crit, 2.5x
    assert m['headshot_expected_hit'] == pytest.approx(100.0 * 3.0 * (0.7 * 1.0 + 0.3 * 2.5 * 2.0))
    assert m['headshot_min_hit'] == pytest.approx(100.0 * 3.0)
    assert m['headshot_max_crit_hit'] == pytest.approx(100.0 * 3.0 * 2.5 * 2.0)


def test_full_stack_headshot_matches_metrics_with_riven_weak_point():
    engine = WarframeDamageEngine()
    riven = {'weak_point_damage': 1.0, 'headshot_bonus': 0.5, 'weak_point_crit_chance': 0.5}
    for weapon in (RIFLE, dict(RIFLE, crit_chance=0.0), dict(RIFLE, crit_chance=0.8)):
        m = engine.compute_metrics(weapon, left_stats={}, mod_objs=[], riven_stats=riven)
        fs = engine.compute_full_stack(weapon, left_stats={}, mod_objs=[], riven_stats=riven)
        assert fs['headshot_burst_dps'] == pytest.approx(m['headshot_burst_dps'])
