import pytest

from scripts.wf_data_indexer import WFDataIndexer
from scripts.warframe_damage_engine import WarframeDamageEngine
from scripts.screen_mod_analyzer import ScreenModAnalyzer


@pytest.fixture(scope='module')
def indexer():
    return WFDataIndexer()


@pytest.fixture(scope='module')
def engine():
    return WarframeDamageEngine()


def _weapon(indexer, name):
    return indexer.weapons_index[name.lower()]


def _mod(indexer, name):
    return dict(indexer.mods_index[name.lower()])


def test_entropy_burst_indexed_as_flat_status(indexer):
    mod = indexer.mods_index['entropy burst']
    assert mod['flat_status'] == pytest.approx(0.20)
    assert mod['status'] == 0.0
    assert mod['compatName'] == 'Supra'


def test_flat_crit_phrases_classified(indexer):
    stats = {}
    indexer._classify_mod_stat('+25% Base Critical Chance', stats)
    indexer._classify_mod_stat('+50% Final Critical Chance', stats)
    indexer._classify_mod_stat('+1.2x Final Critical Damage Multiplier', stats)
    indexer._classify_mod_stat('+30 Flat Status Chance', stats)
    assert stats['flat_crit_chance'] == pytest.approx(0.75)
    assert stats['flat_crit_damage'] == pytest.approx(1.2)
    assert stats['flat_status'] == pytest.approx(0.30)


@pytest.mark.parametrize('weapon, mod, expected', [
    ('Supra Vandal', 'Entropy Burst', True),
    ('Supra', 'Entropy Burst', True),
    ('Mk1-Braton', 'Entropy Burst', False),
    ('Skana Prime', 'Bright Purity', True),
    ('Dual Skana', 'Bright Purity', False),
    ('Prisma Dual Cleavers', 'Justice Blades', True),
    ('Kuva Hek', 'Scattered Justice', True),
    ('Mk1-Braton', 'Scattered Justice', False),
    ('Mk1-Braton', 'Serration', True),
    ('Skana Prime', 'Serration', False),
])
def test_is_mod_compatible(indexer, engine, weapon, mod, expected):
    assert engine.is_mod_compatible(_weapon(indexer, weapon), _mod(indexer, mod)) is expected


def test_generic_mods_without_category_stay_compatible(engine):
    assert engine.is_mod_compatible({'name': 'TestRifle'}, {'name': 'Serration', 'compatName': 'Rifle'})
    assert engine.is_mod_compatible({'name': 'TestRifle', 'category': 'Primary'}, {'name': 'X', 'compatName': ''})


def test_entropy_burst_adds_flat_status_on_supra(indexer, engine):
    supra = _weapon(indexer, 'Supra')
    base = engine.compute_metrics(supra, left_stats={}, mod_objs=[])
    modded = engine.compute_metrics(supra, left_stats={}, mod_objs=[_mod(indexer, 'Entropy Burst')])
    assert base['final_status'] == pytest.approx(0.30)
    assert modded['final_status'] == pytest.approx(0.50)
    assert modded['incompatible_mods'] == []


def test_flat_status_added_after_percent_status(indexer, engine):
    supra = _weapon(indexer, 'Supra')
    mods = [_mod(indexer, 'Entropy Burst'), {'name': 'Rifle Aptitude', 'status': 0.9}]
    m = engine.compute_metrics(supra, left_stats={}, mod_objs=mods)
    assert m['final_status'] == pytest.approx(0.30 * 1.9 + 0.20)


def test_entropy_burst_ignored_on_mk1_braton(indexer, engine):
    braton = _weapon(indexer, 'Mk1-Braton')
    base = engine.compute_metrics(braton, left_stats={}, mod_objs=[])
    modded = engine.compute_metrics(braton, left_stats={}, mod_objs=[_mod(indexer, 'Entropy Burst')])
    assert modded['final_status'] == pytest.approx(base['final_status'])
    assert modded['incompatible_mods'] == ['Entropy Burst']


def test_incompatible_exclusive_mod_contributes_no_damage(indexer, engine):
    braton = _weapon(indexer, 'Mk1-Braton')
    base = engine.compute_metrics(braton, left_stats={}, mod_objs=[_mod(indexer, 'Serration')])
    with_other = engine.compute_metrics(braton, left_stats={}, mod_objs=[_mod(indexer, 'Serration'), {'name': 'Fake Hek Mod', 'compatName': 'Hek', 'damage': 5.0}])
    assert with_other['final_dmg'] == pytest.approx(base['final_dmg'])
    assert with_other['incompatible_mods'] == ['Fake Hek Mod']


def test_flat_crit_added_to_final_crit(engine):
    rifle = {'name': 'TestRifle', 'category': 'Primary', 'total_damage': 100.0, 'crit_chance': 0.2,
             'crit_mult': 2.0, 'fire_rate': 5.0}
    m = engine.compute_metrics(rifle, left_stats={}, mod_objs=[{'name': 'Flat', 'flat_crit_chance': 0.25, 'flat_crit_damage': 1.2}])
    assert m['final_cc'] == pytest.approx(0.45)
    assert m['final_cd'] == pytest.approx(3.2)


def test_report_shows_status_and_incompatible_notice(indexer, engine):
    analyzer = ScreenModAnalyzer()
    braton = _weapon(indexer, 'Mk1-Braton')
    m = engine.compute_metrics(braton, left_stats={}, mod_objs=[_mod(indexer, 'Entropy Burst')])
    briefing = analyzer.format_ordis_briefing(braton, ['Entropy Burst'], m)
    assert f"• 상태이상 확률: {m['final_status'] * 100:.1f}%" in briefing
    assert '⚠️ **[호환 불가 모드 감지]**: Entropy Burst은(는) 해당 무기 전용 모드가 아니므로 계산에서 제외되었습니다.' in briefing

    supra = _weapon(indexer, 'Supra')
    ok = engine.compute_metrics(supra, left_stats={}, mod_objs=[_mod(indexer, 'Entropy Burst')])
    assert '호환 불가 모드' not in analyzer.format_ordis_briefing(supra, ['Entropy Burst'], ok)
    assert '상태이상 확률: 50.0%' in analyzer.format_ordis_briefing(supra, ['Entropy Burst'], ok)
