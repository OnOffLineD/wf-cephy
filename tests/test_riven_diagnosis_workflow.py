import pytest
from unittest.mock import patch, MagicMock
from PIL import Image
from scripts.screen_mod_analyzer import ScreenModAnalyzer
from scripts.llm_orchestrator import LLMOrchestrator

@pytest.fixture
def analyzer():
    a = ScreenModAnalyzer()
    a.clear_pending_diagnosis()
    a.clear_pending_riven()
    return a

def test_riven_slot_detection_prompts_followup(analyzer):
    w_meta = {"name": "Kronen Prime", "kr_name": "크로넨 프라임", "category": "Melee", "total_damage": 212, "crit_chance": 0.24, "crit_mult": 2.2, "fire_rate": 1.17}
    analyzer.indexer.fuzzy_match_weapon = MagicMock(return_value=w_meta)

    # Mock crop_and_ocr_mod_slots to return a slot with a Riven name
    fake_slots = {
        "slot_results": [
            ("slot_1", "블러드 러시"),
            ("slot_2", "컨디션 오버로드"),
            ("slot_3", "Kronen Visi-critacan")  # Riven slot
        ],
        "is_fullscreen": True,
        "offset_x": 0,
        "base_w": 1920
    }
    analyzer.crop_and_ocr_mod_slots = MagicMock(return_value=fake_slots)
    analyzer.ocr_image = MagicMock(return_value="Kronen Prime")

    img = Image.new("RGB", (1920, 1080), color=(0, 0, 0))
    res = analyzer.diagnose_screenshot(img)

    assert res["success"] is True
    assert analyzer.has_pending_riven() is True
    assert "장착된 리벤 모드" in res["message"]
    assert "Kronen Visi-critacan" not in res["message"]

def test_riven_detail_card_comparison_workflow(analyzer):
    w_meta = {"name": "Torid", "kr_name": "토리드", "category": "Primary", "total_damage": 100, "crit_chance": 0.20, "crit_mult": 2.0, "fire_rate": 1.0}
    base_metrics = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={}, mod_objs=[])

    # Set up pending riven context
    analyzer.pending_riven_context = {
        "w_meta": w_meta,
        "left_stats": {},
        "mod_objs": [],
        "riven_name": "Torid Crita-visican",
        "base_metrics": base_metrics
    }

    # Follow-up Riven detail card OCR text
    riven_ocr = "+150.0% 치명타 확률\n+120.0% 치명타 피해\n+100.0% 피해"
    analyzer.ocr_image = MagicMock(return_value=riven_ocr)
    analyzer.indexer.fuzzy_match_weapon = MagicMock(return_value=None)

    img = Image.new("RGB", (600, 800), color=(0, 0, 0))
    res = analyzer.diagnose_screenshot(img)

    assert res.get("is_riven_report") is True
    assert analyzer.has_pending_riven() is False
    assert res["metrics"]["sustained_dps"] > base_metrics["sustained_dps"]
    assert "리벤 모드 정밀 분석 리포트" in res["message"]
    assert "실전 화력 비교" in res["message"]
    assert "Torid Crita-visican" not in res["message"]

def test_finisher_damage_not_confused_with_base_damage(analyzer):
    # OCR text containing finisher damage and crit chance
    ocr_text = "글레이브 Critaum\n+312.5% 치명타 확률 (강공격 시 2배)\n-75.3% 마무리 일격 피해"
    parsed = analyzer.parse_stats(ocr_text)

    # Must accurately separate finisher_damage from base_damage
    assert "finisher_damage" in parsed["stats"]
    assert parsed["stats"]["finisher_damage"] == pytest.approx(-0.753, rel=1e-3)
    assert parsed["stats"]["crit_chance"] == pytest.approx(3.125, rel=1e-3)
    assert "base_damage" not in parsed["stats"]

    # In report, verify finisher damage is listed cleanly without exposing randomized name
    w_meta = {"name": "Glaive", "kr_name": "글레이브", "category": "Melee", "total_damage": 105, "crit_chance": 0.12, "crit_mult": 2.0, "fire_rate": 1.0}
    base_m = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={}, mod_objs=[])
    with_m = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={}, mod_objs=[], riven_stats=parsed["stats"])
    report = analyzer.format_riven_comparison_report(w_meta, "글레이브 Critaum", parsed["stats"], base_m, with_m)

    assert "마무리 일격 피해" in report
    assert "-75.3%" in report
    assert "글레이브 Critaum" not in report

def test_orchestrator_cancels_pending_riven():
    orc = LLMOrchestrator()
    orc.diagnoser = ScreenModAnalyzer()
    orc.diagnoser.pending_riven_context = {"dummy": True}
    assert orc.diagnoser.has_pending_riven() is True

    res = orc.chat("취소")
    assert orc.diagnoser.has_pending_riven() is False
    assert "취소했습니다" in res["report"]

def test_resume_pending_riven_comprehensive_stats(analyzer):
    w_meta = {"name": "Hate", "kr_name": "헤이트", "category": "Melee", "total_damage": 230, "crit_chance": 0.20, "crit_mult": 2.0, "fire_rate": 1.0}
    base_metrics = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={}, mod_objs=[])
    # Set up pending riven context
    analyzer.pending_riven_context = {
        "w_meta": w_meta,
        "left_stats": {},
        "mod_objs": [],
        "riven_name": "Hate Critaum",
        "base_metrics": base_metrics
    }
    # Resume pending riven with new stats
    riven_stats = {
        "crit_chance": 1.5,
        "crit_damage": 1.2,
        "multishot": 0.8,
        "slash": 1.2,
        "faction_damage": 0.45,
        "initial_combo": 20
    }
    res = analyzer.resume_pending_riven(riven_stats)
    assert res['success'] is True
    assert analyzer.has_pending_riven() is False
    assert res['metrics']['sustained_dps'] > res['base_metrics']['sustained_dps']
    assert '리벤 모드 정밀 분석 리포트' in res['message']

def test_riven_quick_input_dialog_and_shorthand(analyzer):
    from PyQt6.QtWidgets import QApplication
    from scripts.riven_quick_dialog import RivenQuickInputDialog

    app = QApplication.instance() or QApplication([])

    dlg = RivenQuickInputDialog()
    stats = dlg.get_stats()
    assert isinstance(stats, dict)

    # Test analyzer.resume_pending_riven shorthand
    w_meta = {"name": "Torid", "kr_name": "토리드", "category": "Primary", "total_damage": 100, "crit_chance": 0.20, "crit_mult": 2.0, "fire_rate": 1.0}
    base_metrics = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={}, mod_objs=[])
    analyzer.pending_riven_context = {
        "w_meta": w_meta,
        "left_stats": {},
        "mod_objs": [],
        "riven_name": "Torid Crita-visican",
        "base_metrics": base_metrics
    }

    # Resume pending riven with shorthand
    res = analyzer.resume_pending_riven("cc 150 cd 120 ms 80")
    assert res["success"] is True

