import pytest
from scripts.wf_data_indexer import WFDataIndexer
from scripts.screen_mod_analyzer import ScreenModAnalyzer

def test_wfcd_korean_name_indexing():
    indexer = WFDataIndexer()
    
    # 1. Official Korean names
    laetum = indexer.fuzzy_match_weapon('레이텀')
    assert laetum is not None
    assert laetum['name'] == 'Laetum'
    assert laetum['crit_chance'] == 0.22
    assert laetum['crit_mult'] == 2.2
    
    torid = indexer.fuzzy_match_weapon('토리드')
    assert torid is not None
    assert torid['name'] == 'Torid'
    
    # 2. Token / N-gram matching from OCR line
    ocr_weapon = indexer.fuzzy_match_weapon('토리드 모딩 A (수용량 60/60)')
    assert ocr_weapon is not None
    assert ocr_weapon['name'] == 'Torid'

    # Truncated Kuva Lich weapon test cases
    kuva_saw1 = indexer.fuzzy_match_weapon('업그레이드 / VONN HAA 쿠바 구울... [40]')
    assert kuva_saw1 is not None
    assert kuva_saw1['name'] == 'Kuva Ghoulsaw'

    kuva_saw2 = indexer.fuzzy_match_weapon('표고업그레이드/VONN 수용량 25/90 HAA 쿠바 구울. 구성A 구성 3 [4이 성C 0')
    assert kuva_saw2 is not None
    assert kuva_saw2['name'] == 'Kuva Ghoulsaw'
    
    # 3. All mods matching
    galv = indexer.match_mod('갈바나이즈드 체임버 10랭크')
    assert galv is not None
    assert galv['name'] == 'Galvanized Chamber'
    assert galv['kr_name'] == '갈바나이즈드 체임버'

def test_screen_mod_analyzer_diagnosis():
    analyzer = ScreenModAnalyzer()
    sample_ocr = (
        "레이텀 모딩\n"
        "갈바나이즈드 체임버\n"
        "서레이션\n"
        "+140.5% 피해\n"
    )
    parsed = analyzer.parse_stats(sample_ocr)
    assert parsed['weapon'] == 'Laetum'
    assert '갈바나이즈드 체임버' in parsed['detected_mods']
    assert '서레이션' in parsed['detected_mods']
    
    # Failsafe warning when blurry
    analyzer.ocr_image = lambda img: "흐릿하고 알수없는 텍스트 123"
    res = analyzer.diagnose_screenshot("dummy.png")
    assert res['success'] is False
    assert "재촬영 요청 가이드" in res['message']


def test_special_weapon_metadata_and_type_overrides():
    ix = WFDataIndexer()

    # 1. Type overrides & Melee-labeled-Rifle cleanup
    assert ix.weapons_index['coda bubonico']['type'] == 'Shotgun'
    assert ix.weapons_index['perigale prime']['type'] == 'Sniper'
    assert ix.weapons_index['mutalist cernos']['type'] == 'Bow'
    assert ix.weapons_index['sancti castanas']['type'] == 'Throwing'
    for melee_name in ('ruvox', 'paracesis', 'prisma skana', 'ekhein', 'dual viciss', 'venato', 'prova', 'prova vandal'):
        assert ix.weapons_index[melee_name]['category'] == 'Melee'
        assert ix.weapons_index[melee_name]['type'] == 'Melee'

    # 2. Beam flag, trigger, disposition/omega, max_level_cap, melee special fields
    nukor = ix.weapons_index['kuva nukor']
    assert nukor['trigger'] == 'Held'
    assert nukor['is_beam'] is True
    assert nukor['max_level_cap'] == 40
    assert 'disposition' in nukor and 'omega_attenuation' in nukor

    glaive = ix.weapons_index['glaive prime']
    assert glaive['wind_up'] == pytest.approx(1.2)
    assert glaive['follow_through'] == pytest.approx(0.7, abs=1e-3)
    assert glaive['slam_attack'] == pytest.approx(492.0)
    assert glaive['combo_duration'] == pytest.approx(5.0)
    assert glaive['range'] == pytest.approx(1.25)
    assert glaive['attack_modes']['heavy_throw']['damage'] == pytest.approx(1184.0)

    # 3. Grimoire dedup, Dark Split-Sword status fallback, Lanka fire_rate fallback
    grimoire = ix.weapons_index['grimoire']
    assert grimoire['total_damage'] == pytest.approx(150.0)
    assert grimoire['crit_chance'] == pytest.approx(0.20)
    assert ix.weapons_index['dark split-sword']['status_chance'] == pytest.approx(0.25)
    assert ix.weapons_index['lanka']['fire_rate'] == pytest.approx(1.0)
    assert ix.weapons_index['lanka']['crit_chance'] == pytest.approx(0.25)


def test_frankenstein_modes_laetum_aoe_and_exalted_hydration():
    ix = WFDataIndexer()

    # Nataruk aligns to Perfect Shot (900 dmg, 60% CC, 2.4x CM) with full attack_modes
    nataruk = ix.weapons_index['nataruk']
    assert nataruk['crit_chance'] == pytest.approx(0.60)
    assert nataruk['crit_mult'] == pytest.approx(2.4)
    assert nataruk['attacks'][0]['name'] == 'Perfect Shot'
    assert nataruk['attack_modes']['quick']['damage'] == pytest.approx(450.0)
    assert nataruk['attack_modes']['charged']['crit_chance'] == pytest.approx(0.50)
    assert nataruk['attack_modes']['perfect']['crit_chance'] == pytest.approx(0.60)

    # Epitaph Prime aligns to Charged Shot (315 dmg, 50% CC, 3.0x CM) while keeping Quick AoE mode
    ep = ix.weapons_index['epitaph prime']
    assert ep['crit_chance'] == pytest.approx(0.50)
    assert ep['crit_mult'] == pytest.approx(3.0)
    assert ep['attack_modes']['quick']['radial_damage'] == pytest.approx(30.0)
    assert ep['attack_modes']['quick']['status_chance'] == pytest.approx(0.50)

    # Fulmin Prime aligns to Semi-Auto Mode (550 dmg, impact+electric) while keeping Full Auto alt_fire
    fulmin = ix.weapons_index['fulmin prime']
    assert fulmin['attacks'][0]['name'] == 'Semi-Auto Mode'
    assert fulmin['attack_modes']['normal']['damage'] == pytest.approx(550.0)
    assert 'impact' in fulmin['attack_modes']['normal']['damage_types']
    assert fulmin['attack_modes']['alt_fire']['damage'] == pytest.approx(33.0)

    # Laetum Auto Radial Attack belongs to incarnon_aoe (300), NOT normal radial_attack
    laetum = ix.weapons_index['laetum']
    assert 'radial_attack' not in laetum
    assert laetum['incarnon_aoe']['name'] == 'Auto Radial Attack'
    assert laetum['attack_modes']['incarnon']['damage'] == pytest.approx(100.0)
    assert laetum['attack_modes']['incarnon']['radial_damage'] == pytest.approx(300.0)

    # Torid Incarnon mode is flagged as beam
    torid = ix.weapons_index['torid']
    assert torid['is_beam'] is False
    assert torid['attack_modes']['incarnon']['is_beam'] is True

    # Kuva Zarr preserves Direct + Radial split cleanly in attack_modes
    zarr = ix.weapons_index['kuva zarr']
    assert zarr['attack_modes']['normal']['damage'] == pytest.approx(50.0)
    assert zarr['attack_modes']['normal']['radial_damage'] == pytest.approx(673.0)
    assert zarr['attack_modes']['alt_fire']['name'] == 'Barrage Mode'

    # Exalted weapons hydrated from game_catalog.json (EN + KR)
    for en, kr, cat, w_type in (
        ('exalted blade', '익절티드 블레이드', 'Melee', 'Melee'),
        ('regulators prime', '레귤레이터즈 프라임', 'Secondary', 'Pistol'),
        ('artemis bow prime', '아르테미스 보우 프라임', 'Primary', 'Bow'),
        ('desert wind prime', '데저트 윈드 프라임', 'Melee', 'Melee'),
        ('noctua', '녹투아', 'Secondary', 'Pistol'),
        ('iron staff prime', '아이언 스태프 프라임', 'Melee', 'Melee'),
        ('arquebex', '알퀘벡스', 'Arch-Gun', 'Arch-Gun'),
    ):
        w = ix.weapons_index.get(en)
        assert w is not None and w.get('is_exalted') is True
        assert w['category'] == cat and w['type'] == w_type
        assert w['total_damage'] > 0
        assert ix.weapons_index.get(kr) is w


def test_special_mod_stat_parsing_and_arcanes():
    ix = WFDataIndexer()

    kb = ix.mods_index['killing blow']
    assert kb['heavy_damage_bonus'] == pytest.approx(1.2)
    assert kb['wind_up_speed'] == pytest.approx(0.6)

    assert ix.mods_index['corrupt charge']['initial_combo'] == pytest.approx(30.0)
    assert ix.mods_index['galvanized reflex']['on_kill'] == [{'stat': 'initial_combo', 'value': 20.0, 'stacks': 4}]
    assert ix.mods_index['berserker fury']['on_kill'] == [{'stat': 'attack_speed', 'value': 0.35, 'stacks': 2}]

    for bow_fr_mod in ('vile acceleration', 'shred', 'primed shred', 'speed trigger', 'critical delay'):
        assert ix.mods_index[bow_fr_mod]['bow_fire_rate_mult'] == pytest.approx(2.0), bow_fr_mod

    for cannonade in ('semi-rifle cannonade', 'semi-shotgun cannonade', 'semi-pistol cannonade'):
        assert ix.mods_index[cannonade]['lock_fire_rate'] is True
        assert ix.mods_index[cannonade]['damage'] >= 2.4
    assert 'shotgun cannonade' not in ix.mods_index
    assert 'pistol cannonade' not in ix.mods_index

    for gmod in ('galvanized scope', 'galvanized crosshairs'):
        assert ix.mods_index[gmod]['on_weakpoint'] == [{'stat': 'crit_chance', 'value': 1.2, 'stacks': 1}]
        assert ix.mods_index[gmod]['on_kill'] == [{'stat': 'crit_chance', 'value': 0.4, 'stacks': 5}]
    assert ix.mods_index['argon scope']['on_weakpoint'] == [{'stat': 'crit_chance', 'value': 1.35, 'stacks': 1}]
    assert ix.mods_index['bladed rounds']['on_kill'] == [{'stat': 'crit_damage', 'value': 1.2, 'stacks': 1}]

    # Target Acquired routes to headshot_bonus, NOT weak_point_damage
    ta = ix.mods_index['target acquired']
    assert ta['headshot_bonus'] == pytest.approx(0.6)
    assert ta['weak_point_damage'] == pytest.approx(0.0)

    # Newly synced weapon arcanes from data/weapon_arcanes.json
    for arc_name in ('cascadia flare', 'longbow sharpshot', 'shotgun vendetta', 'conjunction voltage', 'pax seeker', 'fractalized reset'):
        arc = ix.mods_index.get(arc_name)
        assert arc is not None and arc['is_arcane'] is True

    # Dual Coda Torxica fuzzy matching preserves 'Dual '/'듀얼 '
    assert ix.fuzzy_match_weapon('Dual Coda Torxica')['name'] == 'Dual Coda Torxica'
    assert ix.fuzzy_match_weapon('업그레이드 / 듀얼 코다 톡시카 [40]')['name'] == 'Dual Coda Torxica'

