import pytest
from scripts.wf_data_indexer import WFDataIndexer
from scripts.screen_mod_analyzer import ScreenModAnalyzer
from scripts.riven_ocr_analyzer import RivenOCRAnalyzer

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
    assert RivenOCRAnalyzer is ScreenModAnalyzer
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
