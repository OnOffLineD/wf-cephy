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
    assert indexer.mods_index['target acquired']['weak_point_damage'] == pytest.approx(0.6)
    assert indexer.mods_index['meticulous aim']['weak_point_damage'] == pytest.approx(1.05)
    serration = indexer.mods_index['serration']
    assert serration['weak_point_crit_chance'] == 0.0
    assert serration['lock_multishot'] is False


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
