import os
from PIL import Image
import pytest
from scripts.wf_data_indexer import WFDataIndexer
from scripts.screen_mod_analyzer import ScreenModAnalyzer

@pytest.fixture(scope="module")
def analyzer():
    return ScreenModAnalyzer()

def test_warframe_and_tricky_weapon_indexing():
    idx = WFDataIndexer()
    # 1. Warframe indexing
    yareli = idx.fuzzy_match_weapon("업그레이드/야렐리 [30] 우4")
    assert yareli is not None
    assert yareli.get("name") == "Yareli"
    assert yareli.get("category") == "Warframe"

    nyx = idx.fuzzy_match_weapon("업그레이드/닉스 프라임 [30]")
    assert nyx is not None
    assert nyx.get("name") == "Nyx Prime"

    hydroid = idx.fuzzy_match_weapon("업그레이드/하이드로이드 프. . [30]")
    assert hydroid is not None
    assert "Hydroid" in hydroid.get("name")

    # 2. Coda & Kuva typo tolerance
    coda = idx.fuzzy_match_weapon("고업그레이드/코다 커스타시人")
    assert coda is not None
    assert coda.get("name") == "Coda Caustacyst"

    zarr = idx.fuzzy_match_weapon("BIGG SOFF 쿠바 자르 [40]")
    assert zarr is not None
    assert zarr.get("name") == "Kuva Zarr"

def test_tight_crop_8_cards_miter(analyzer):
    fpath = "labeling/warframemode/20261018101017_1.jpg"
    if not os.path.exists(fpath):
        pytest.skip(f"{fpath} does not exist")
    img = Image.open(fpath).crop((573, 250, 1570, 540))
    res = analyzer.diagnose_screenshot(img)
    assert res.get("success") is True
    assert res.get("weapon") == "Miter"
    detected = res.get("detected_mods", [])
    assert len(detected) == 8
    assert any("리벤 모드" in m or "Riven" in m for m in detected)
    assert any("갈바나이즈드" in m for m in detected)

def test_tight_crop_with_chat_resumption(analyzer):
    fpath = "labeling/warframemode/20261018101134_1.jpg"
    if not os.path.exists(fpath):
        pytest.skip(f"{fpath} does not exist")
    img = Image.open(fpath).crop((570, 250, 1570, 540))
    res1 = analyzer.diagnose_screenshot(img)
    assert res1.get("success") is True
    assert len(res1.get("detected_mods", [])) >= 7

    # Simulate user sending weapon name via chat
    res2 = analyzer.resume_pending_diagnosis("쿠바 자르")
    assert res2.get("success") is True
    assert res2.get("weapon") == "Kuva Zarr"
    assert len(res2.get("detected_mods", [])) >= 7
    assert res2.get("metrics", {}).get("burst_dps", 0) > 1000

def test_fullscreen_warframe_diagnosis(analyzer):
    fpath = "labeling/warframemode/20260829011436_1.jpg"
    if not os.path.exists(fpath):
        pytest.skip(f"{fpath} does not exist")
    res = analyzer.diagnose_screenshot(fpath)
    assert res.get("success") is True
    assert res.get("weapon") == "Yareli"
    assert len(res.get("detected_mods", [])) >= 8
