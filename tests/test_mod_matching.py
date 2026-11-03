import pytest
from scripts.screen_mod_analyzer import ScreenModAnalyzer


@pytest.fixture(scope="module")
def analyzer():
    return ScreenModAnalyzer()


def names(analyzer, weapon):
    w_meta = analyzer.indexer.fuzzy_match_weapon(weapon) if isinstance(weapon, str) else weapon
    return {c[2].get("name") for c in analyzer._build_slot_candidates(w_meta, w_meta.get("category", "").lower())}


def top(analyzer, weapon, text):
    w_meta = analyzer.indexer.fuzzy_match_weapon(weapon)
    cands = analyzer._build_slot_candidates(w_meta, w_meta.get("category", "").lower())
    return analyzer._match_single_slot(text, cands, return_all=True)[0][1]["name"]


@pytest.mark.parametrize("weapon", ["Vulkar", "Lanka", "Paris", "Dread"])
def test_rifle_mods_allowed_on_snipers_and_bows(analyzer, weapon):
    assert {"Vital Sense", "Serration", "Rupture"} <= names(analyzer, weapon)


def test_mods_also_sold_by_conclave_are_not_pvp(analyzer):
    assert analyzer.indexer.mods_index["reach"]["is_pvp"] is False
    assert "Reach" in names(analyzer, "Dark Split-Sword")


def test_exclusive_mods_stay_exclusive(analyzer):
    assert "Point Blank" not in names(analyzer, "Vulkar")
    assert "Vital Sense" in names(analyzer, "Braton")


def test_thrown_melee_mods_allowed_on_glaives(analyzer):
    assert {"Power Throw", "Volatile Quick Return"} <= names(analyzer, "Glaive Prime")


def test_weapon_augment_only_on_its_weapon(analyzer):
    assert "Photon Overcharge" not in names(analyzer, "Braton")
    assert "Photon Overcharge" in names(analyzer, "Glaxion")


def test_weapon_augment_kept_when_weapon_is_only_inferred(analyzer):
    inferred = {"name": "인식된 주무기", "category": "Primary", "type": "Rifle", "is_inferred": True}
    assert "Photon Overcharge" in names(analyzer, inferred)


@pytest.mark.parametrize("weapon, text, expected", [
    # Real OCR strings captured from ocrTestImg samples.
    ("Braton", "- 화라EI결딜레이 1\n화라EI결딜레이 1 ||| 화라EI길딜레이 1 ||| 크리ä 딛레01 ||| 화라EI권님레이 1 ||| -화라EI길딜레이 1", "Critical Delay"),
    ("Dark Split-Sword", "트루 스틸\n1 ||| 트루스릴』 1\n트루스틸& 1 ||| 5卜” ||| 트루 스틸\n1 ||| 1\n트루 스틸\n트루 스틸?", "True Steel"),
    ("Dark Split-Sword", "7尸\n7Y ||| 7Y\n-리치'C\n-리치별鬱 ||| 7尸\n-리치 ||| 7Y\n-리치f″\n-리치( ||| -국치,\n7Y\n-리치1", "Reach"),
    ("Sampotes", "프라임 드 프리\n포인트 .•\n포인트 ||| 7 Y\n프라임 드\n포인트 ||| 프라일드 프己袋M\n포인L ||| 프라임 드\n포이 「\n프라임 드 희라\n포이E ||| 7\n프라임드", "Primed Pressure Point"),
    ("Sampotes", "구 크러쉽루인 - , ||| 크러췅루인 - ||| 크러원 무인 ||| 크러원루인 ||| 크러쉽구인", "Crushing Ruin"),
    ("Stropha", "! 아말감 오르건 새터 ||| ( 아말감 오르건 새터 ||| 4 아말감 오르건 새터", "Amalgam Organ Shatter"),
    ("Dark Split-Sword", "/깐우르건새터 1\n우르건시터 ||| 오르건섀터 1 ||| 오르건 새터 ||| 수! 우르건새터 5 1", "Organ Shatter"),
    ("Stropha", "16닣\n1 사|크리피전프레셔 ||| 16날\n재크리피설 프레셔 ||| 16v\n새크리피셜 프레서", "Sacrificial Pressure"),
    ("Braton", "갈바나이즈드\n서임비 1」 \\ ||| ' 갈바나이즈드\n``서임비 111• ||| 갇바LIC가스드\n세'긴비 ||| 갈바나이즈드 ||| 72갈바나이즈드 ||| 갈바나이즈드", "Galvanized Chamber"),
    ("Tenet Exec", "요 트라0 보\n, 으규념녑띱1브 ; ||| 디스크•..R卜\n오비느리'기브 ||| 스매\n드라0 보 ||| 1\n스매XI\n드라0 보\n스피3A1\n9 c:라0브", "Dispatch Overdrive"),
])
def test_top_match_from_real_ocr(analyzer, weapon, text, expected):
    assert top(analyzer, weapon, text) == expected
