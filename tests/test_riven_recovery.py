import json
import os

import pytest
from PIL import Image

try:
    from PyQt6.QtWidgets import QApplication, QPushButton
except ImportError:
    from PySide6.QtWidgets import QApplication, QPushButton

from scripts.build_store import BuildStore, RIVEN_MOD, is_riven_name, slot_order
from scripts.desktop_companion import OrdisCompanionApp
from scripts.screen_mod_analyzer import ScreenModAnalyzer, looks_like_riven_card

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ocrTestImg", "corinth_prime_riven.jpg")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def shared_analyzer():
    return ScreenModAnalyzer()


@pytest.fixture
def analyzer(shared_analyzer, tmp_path):
    shared_analyzer.build_store = BuildStore(str(tmp_path / "builds.json"))
    shared_analyzer.clear_pending_riven()
    shared_analyzer.entered_rivens.clear()
    return shared_analyzer


def scan(analyzer, slots=None):
    w_meta = analyzer.indexer.fuzzy_match_weapon("Corinth Prime")
    slots = slots or {"R1_C1": "Hunter Munitions", "R1_C4": "Atomic Fallout"}
    mods = [dict(analyzer.indexer.mods_index[n.lower()], slot_name=s, slot_index=slot_order(s)) for s, n in slots.items()]
    return {"w_meta": w_meta, "mod_objs": mods, "stats": {"total_damage": 3667.4, "crit_chance": 0.816, "crit_mult": 7.1, "multishot": 12.6, "fire_rate": 1.98}, "metrics": {}, "message": "결과", "review_message": "검토"}


@pytest.mark.parametrize("text, expected", [
    ("코힌- Crita\n\\avmatox\n- A ||| 1\n코린- Crita-\n\\armatox ||| 코린*\narmatox\n코린- Crita-", True),
    ("나타루크 Visilis ||| 나타루크 Visilis", True),
    ("프라임드 피비\n스트라이크 ||| 드리임드 JtlHI ||| 프라임드 피비", False),
    ("바이탈 센스 ||| 바이믿 센스 ||| 바비곧 ,프스", False),
    ("코힌 Crita ||| 없음", False),
])
def test_riven_card_needs_repeated_latin_words(text, expected):
    assert looks_like_riven_card(text) is expected


def test_english_client_is_not_treated_as_riven():
    assert looks_like_riven_card("Vital Sense ||| Vital Sense") is False


@pytest.mark.parametrize("name, expected", [("Shotgun Riven Mod", True), ("Rifle Riven Mod", True), (RIVEN_MOD, True), ("Serration", False), ("", False)])
def test_is_riven_name(name, expected):
    assert is_riven_name(name) is expected


def test_codex_riven_entries_are_not_mod_candidates(analyzer):
    w_meta = analyzer.indexer.fuzzy_match_weapon("Corinth Prime")
    assert not [name for _, name in analyzer.mod_choices(w_meta) if is_riven_name(name)]


def test_slot_edit_to_riven_waits_for_riven_values(analyzer):
    res = scan(analyzer)
    assert analyzer.has_pending_riven() is False
    analyzer.apply_slot_edits(res, {"R1_C1": "Hunter Munitions", "R1_C4": RIVEN_MOD})
    assert analyzer.has_pending_riven() is True
    assert "리벤 고유 옵션" in res["review_message"]
    assert "리벤 수치" in res["message"]


def test_codex_riven_name_counts_as_riven(analyzer):
    res = scan(analyzer)
    analyzer.apply_slot_edits(res, {"R1_C4": "Shotgun Riven Mod"})
    assert analyzer.has_pending_riven() is True
    assert res["mod_objs"][0]["name"] == RIVEN_MOD


def test_removing_riven_in_edit_cancels_waiting(analyzer):
    res = scan(analyzer)
    analyzer.apply_slot_edits(res, {"R1_C4": RIVEN_MOD})
    analyzer.apply_slot_edits(res, {"R1_C4": "Serration"})
    assert analyzer.has_pending_riven() is False


def test_riven_values_entered_before_saving_are_kept(analyzer):
    res = scan(analyzer)
    analyzer.apply_slot_edits(res, {"R1_C1": "Hunter Munitions", "R1_C4": RIVEN_MOD})
    out = analyzer.resume_pending_riven({"multishot": 0.9, "crit_chance": 1.0})
    assert out["success"] is True
    expected_dmg = res["w_meta"]["total_damage"] * res["w_meta"]["base_multishot"] * (1.0 + 0.9)
    assert out["metrics"]["final_dmg"] == pytest.approx(expected_dmg)  # DB + mods/riven only, ignoring panel OCR.

    analyzer.save_scanned_build(res)
    build = analyzer.build_store.get_build("Corinth Prime")
    assert build["panel_has_riven"] is True
    assert build["riven"] == {"multishot": 0.9, "crit_chance": 1.0}
    assert analyzer.evaluate_saved_build(build)["final_dmg"] == pytest.approx(expected_dmg)


def test_riven_values_entered_after_saving_update_build(analyzer):
    res = scan(analyzer)
    analyzer.apply_slot_edits(res, {"R1_C4": RIVEN_MOD})
    analyzer.save_scanned_build(res)
    analyzer.resume_pending_riven({"multishot": 0.9})
    assert analyzer.build_store.get_build("Corinth Prime")["riven"] == {"multishot": 0.9}


def test_store_migrates_builds_saved_with_codex_riven(tmp_path):
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"version": 1, "builds": {"corinth prime": {
        "weapon": "Corinth Prime", "slots": {"R1_C4": "Shotgun Riven Mod"}, "panel_has_riven": False, "panel_riven": None,
    }}}), encoding="utf-8")
    build = BuildStore(str(path)).get_build("Corinth Prime")
    assert build["slots"]["R1_C4"] == RIVEN_MOD
    assert build["panel_has_riven"] is True


def test_app_shows_riven_input_after_slot_edit(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    panel = OrdisCompanionApp()
    panel.diagnoser.build_store = BuildStore(str(tmp_path / "b.json"))
    panel.diagnoser.clear_pending_riven()
    res = scan(panel.diagnoser)
    panel.diagnoser.apply_slot_edits(res, {"R1_C4": RIVEN_MOD})
    panel.add_chat_bubble("오디스", res["review_message"], action_todo=panel._review_action(res))
    bubble = panel.chat_list_layout.itemAt(panel.chat_list_layout.count() - 1).widget()
    assert any("리벤 옵션 간편 입력" in b.text() for b in bubble.findChildren(QPushButton))
    panel.on_confirm_mod_review(res)
    last = panel.chat_list_layout.itemAt(panel.chat_list_layout.count() - 1).widget()
    assert any("리벤 옵션 간편 입력" in b.text() for b in last.findChildren(QPushButton))
    panel.close()


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="sample missing")
def test_real_capture_detects_riven_slot(analyzer):
    res = analyzer.diagnose_screenshot(SAMPLE)
    assert res["weapon"] == "Corinth Prime"
    assert analyzer.result_slots(res)["R1_C4"] == RIVEN_MOD
    assert analyzer.has_pending_riven() is True
    assert not any("Atomic Fallout" in m for m in res["detected_mods"])


def test_panel_ocr_stats_are_ignored_while_valence_bonus_is_preserved(analyzer):
    w_meta = analyzer.indexer.fuzzy_match_weapon("Kuva Hek")
    mods = [dict(analyzer.indexer.mods_index["point blank"])]
    bogus_panel = {
        "total_damage": 99999.0,
        "crit_chance": 0.99,
        "crit_mult": 15.0,
        "multishot": 12.0,
        "fire_rate": 25.0,
        "status_chance": 0.95,
    }
    clean = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={}, mod_objs=mods)
    with_bogus = analyzer.calculate_comprehensive_metrics(w_meta, left_stats=bogus_panel, mod_objs=mods)
    for key in ("final_dmg", "final_cc", "final_cd", "final_ms", "final_fr", "burst_dps", "sustained_dps"):
        assert with_bogus[key] == pytest.approx(clean[key])

    with_valence = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={**bogus_panel, "valence_heat": 0.6}, mod_objs=mods)
    assert with_valence["final_dmg"] == pytest.approx(clean["final_dmg"] * 1.6)


def test_formatters_show_db_basis_and_optional_status_dps(analyzer):
    w_meta = analyzer.indexer.fuzzy_match_weapon("Corinth Prime")
    mods = [dict(analyzer.indexer.mods_index["hunter munitions"])]
    base_metrics = analyzer.calculate_comprehensive_metrics(w_meta, left_stats={}, mod_objs=mods)
    no_status = {k: v for k, v in base_metrics.items() if k not in ("status_dps", "direct_burst_dps")}

    briefing = analyzer.format_ordis_briefing(w_meta, ["헌터 뮤니션즈 (Hunter Munitions)"], no_status)
    breakdown = ScreenModAnalyzer.format_calculation_breakdown(None, w_meta, mods, no_status)
    card = analyzer.build_diagnostic_card(w_meta, ["헌터 뮤니션즈 (Hunter Munitions)"], no_status)
    assert "총계를 읽지 못해" not in briefing
    assert "총계를 읽지 못해" not in card["detail_html"]
    assert "DB 원본" in briefing and "DB 원본" in breakdown
    assert "상태이상 DoT" not in briefing

    assert base_metrics["status_dps"] > 0
    with_status = {**base_metrics, "status_dps": 1234.0, "direct_burst_dps": 5000.0, "burst_dps": 6234.0}
    briefing_dot = analyzer.format_ordis_briefing(w_meta, ["헌터 뮤니션즈 (Hunter Munitions)"], with_status)
    breakdown_dot = ScreenModAnalyzer.format_calculation_breakdown(None, w_meta, mods, with_status)
    card_dot = analyzer.build_diagnostic_card(w_meta, ["헌터 뮤니션즈 (Hunter Munitions)"], with_status)
    assert "상태이상 DoT DPS" in briefing_dot and "1,234" in briefing_dot
    assert "상태이상 DoT 1,234 DPS" in breakdown_dot
    assert "1,234" in card_dot["summary_html"]
