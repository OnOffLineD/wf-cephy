from unittest.mock import MagicMock, patch

import pytest
import requests

try:
    from PyQt6.QtCore import QThread
    from PyQt6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
except ImportError:
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton

from scripts.build_edit_dialog import EMPTY, BuildEditDialog
from scripts.build_store import BuildStore, GRID_SLOTS, RIVEN_MOD
from scripts.desktop_companion import OrdisCompanionApp
from scripts.llm_orchestrator import BUILD_LEAD_DEFAULT, LLMOrchestrator
from scripts.riven_compare_dialog import RivenCompareDialog, RivenRollEditDialog, format_change
from scripts.riven_quick_dialog import RivenQuickInputDialog
from scripts.screen_mod_analyzer import ScreenModAnalyzer


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def shared_analyzer():
    return ScreenModAnalyzer()


@pytest.fixture
def orc(shared_analyzer, tmp_path):
    shared_analyzer.build_store = BuildStore(str(tmp_path / "builds.json"))
    orchestrator = LLMOrchestrator()
    orchestrator.diagnoser = shared_analyzer
    orchestrator._call_llm = MagicMock(return_value=None)
    shared_analyzer.build_store.save_build({
        "weapon": "Vulkar", "kr_name": "불카", "category": "Primary",
        "slots": {"R1_C1": "Vital Sense", "R2_C1": "Rupture"},
        "arcane": "Primary Merciless", "panel": {"total_damage": 387.0, "crit_chance": 0.2, "crit_mult": 4.4, "fire_rate": 1.5},
        "panel_has_riven": False, "panel_riven": None, "panel_removed": [], "riven": None, "extra": [],
    })
    return orchestrator


@pytest.mark.parametrize("query", ["불카에 뭐 꼈어?", "불카 장착한 모드 알려줘", "방금 그 무기 뭐 꼈지?", "뭐 꼈어?"])
def test_owned_questions_list_saved_mods(orc, query):
    res = orc.chat(query)
    assert res["type"] == "BUILD_QUERY"
    assert "바이탈 센스" in res["report"] and "럽쳐" in res["report"]
    assert "프라이머리 머시리스" in res["report"]


@pytest.mark.parametrize("query", ["불카 DPS 얼마야?", "불카 화력 얼마나 나와?"])
def test_damage_question_recalculates_saved_build(orc, query):
    res = orc.chat(query)
    expected = orc.diagnoser.evaluate_saved_build(orc.diagnoser.build_store.get_build("Vulkar"))["sustained_dps"]
    assert f"{expected:,.0f}" in res["report"]
    assert "풀스택" in res["report"]


def test_list_question(orc):
    res = orc.chat("저장한 무기 뭐 있어?")
    assert res["type"] == "BUILD_QUERY"
    assert "불카" in res["report"] and "1개" in res["report"]


def test_empty_list(orc):
    orc.diagnoser.build_store.delete_build("Vulkar")
    assert "없습니다" in orc.chat("빌드 목록 보여줘")["report"]


def test_unsaved_weapon_says_so(orc):
    res = orc.chat("토리드에 뭐 꼈어?")
    assert res["type"] == "BUILD_QUERY"
    assert "저장되어 있지 않습니다" in res["report"]


def test_delete_asks_for_confirmation_and_changes_nothing(orc):
    res = orc.chat("불카 빌드 삭제해줘")
    assert res["type"] == "BUILD_DELETE_CONFIRM"
    assert res["weapon"] == "Vulkar"
    assert orc.diagnoser.build_store.get_build("Vulkar") is not None


@pytest.mark.parametrize("query", ["토리드 모드 추천해줘", "리벤이 뭐야?", "오버가드 약점", "토리드 공략 알려줘", "안녕"])
def test_game_questions_are_left_to_the_router(orc, query):
    assert orc._answer_build_query(query) is None


def test_model_text_cannot_add_numbers(orc):
    orc._call_llm = MagicMock(return_value="[MOOD:happy] 지속 DPS는 999999입니다!")
    res = orc.chat("불카에 뭐 꼈어?")
    assert "999999" not in res["report"]
    assert BUILD_LEAD_DEFAULT in res["report"]


def test_model_lead_is_used_without_tag(orc):
    orc._call_llm = MagicMock(return_value="[MOOD:proud] 기록을 가져왔습니다!\n둘째 줄")
    res = orc.chat("불카에 뭐 꼈어?")
    assert res["report"].startswith("기록을 가져왔습니다!")
    assert "둘째 줄" not in res["report"]
    assert res["mood"] == "proud"


def test_mood_tag_alone_on_first_line(orc):
    orc._call_llm = MagicMock(return_value="[MOOD:tactical]\n기록을 확인했습니다.")
    res = orc.chat("불카에 뭐 꼈어?")
    assert res["report"].startswith("기록을 확인했습니다.")
    assert res["mood"] == "tactical"


def test_model_reply_with_only_a_tag_uses_default(orc):
    orc._call_llm = MagicMock(return_value="[MOOD:tactical]")
    assert orc.chat("불카에 뭐 꼈어?")["report"].startswith(BUILD_LEAD_DEFAULT)


def test_works_with_llm_server_off(shared_analyzer, tmp_path):
    shared_analyzer.build_store = BuildStore(str(tmp_path / "b.json"))
    orchestrator = LLMOrchestrator()
    orchestrator.diagnoser = shared_analyzer
    with patch("scripts.llm_orchestrator.requests.post", side_effect=requests.ConnectionError()):
        assert "없습니다" in orchestrator.chat("빌드 목록")["report"]


CHOICES = [("바이탈 센스", "Vital Sense"), ("서레이션", "Serration"), ("헬파이어", "Hellfire")]


def test_edit_dialog_shows_and_returns_slots(qapp):
    dialog = BuildEditDialog({"R1_C1": "Vital Sense", "R2_C4": RIVEN_MOD}, CHOICES, arcane="Primary Merciless", arcane_choices=[("프라이머리 머시리스", "Primary Merciless")])
    assert dialog.combos["R1_C1"].currentText() == "바이탈 센스"
    assert dialog.combos["R2_C4"].currentText() == "리벤 모드"
    assert dialog.combos["R1_C2"].currentText() == EMPTY
    assert dialog.arcane_combo.currentText() == "프라이머리 머시리스"

    dialog.combos["R1_C1"].setCurrentText(EMPTY)
    dialog.combos["R1_C2"].setCurrentText("서레이션")
    edits = dialog.get_edits()
    assert edits["R1_C1"] == ""
    assert edits["R1_C2"] == "Serration"
    assert edits["R2_C4"] == RIVEN_MOD
    assert edits["arcane"] == "Primary Merciless"
    assert set(GRID_SLOTS) <= set(edits)


def test_edit_dialog_rejects_unknown_names(qapp):
    dialog = BuildEditDialog({}, CHOICES)
    dialog.combos["R1_C1"].setCurrentText("없는모드")
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.invalid_slots() == ["R1_C1"]
    assert "목록에 없는" in dialog.error_label.text()


def test_format_change():
    assert format_change(100.0, 150.0) == "+50.0%"
    assert format_change(0.0, 150.0) == "-"


def test_compare_dialog_lists_rows(qapp):
    res = {
        "verdict": "새 옵션이 +50.0% 더 강합니다",
        "rows": [("지속 DPS", 100.0, 150.0), ("순간 DPS", 200.0, 300.0)],
        "old_card": {"name": "A", "stats": {"base_damage": 1.0}},
        "new_card": {"name": "B", "stats": {"multishot": 0.5}},
        "unapplied": ["확대율 +80%"],
        "notes": ["노트"],
    }
    dialog = RivenCompareDialog(res)
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 3).text() == "+50.0%"
    assert dialog.table.item(1, 1).text() == "200"
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "확대율" in texts and "노트" in texts and "더 강합니다" in texts


def test_roll_edit_dialog(qapp):
    dialog = RivenRollEditDialog({"base_damage": 2.517}, {"multishot": 0.82})
    assert dialog.old_stats() == pytest.approx({"base_damage": 2.517})
    dialog.new_edit.setText("치확 150 화염 85.2")
    assert dialog.new_stats()["crit_chance"] == pytest.approx(1.5)
    assert dialog.new_stats()["heat"] == pytest.approx(0.852)
    dialog.new_edit.setText("이상한 글자")
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_quick_input_values_are_percents(qapp):
    dialog = RivenQuickInputDialog()
    dialog.quick_input.setText("피해 165 공속 60")
    stats = dialog.get_stats()
    assert stats["base_damage"] == pytest.approx(1.65)
    assert stats["fire_rate"] == pytest.approx(0.6)


def test_quick_input_curse_is_negative(qapp):
    dialog = RivenQuickInputDialog()
    dialog.curse_combo.setCurrentText("치확")
    dialog.curse_line_edit.setText("30")
    assert dialog.get_stats()["crit_chance"] == pytest.approx(-0.3)


@pytest.fixture
def panel(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    app = OrdisCompanionApp()
    app.diagnoser.build_store = BuildStore(str(tmp_path / "b.json"))
    yield app
    app.close()


def last_bubble_buttons(panel):
    item = panel.chat_list_layout.itemAt(panel.chat_list_layout.count() - 1).widget()
    return {b.text(): b for b in item.findChildren(QPushButton)}


def scan(panel):
    w = panel.diagnoser.indexer.fuzzy_match_weapon("Vulkar")
    mods = [dict(panel.diagnoser.indexer.mods_index["vital sense"], slot_name="R1_C1", slot_index=1)]
    res = {"w_meta": w, "mod_objs": mods, "stats": {"total_damage": 387.0}, "metrics": {}, "message": "결과", "review_message": "검토"}
    return res


def test_confirming_review_saves_build(panel):
    panel.on_confirm_mod_review(scan(panel))
    assert panel.diagnoser.build_store.get_build("Vulkar")["slots"] == {"R1_C1": "Vital Sense"}


def test_review_has_edit_button(panel):
    panel.add_chat_bubble("오디스", "검토", action_todo=panel._review_action(scan(panel)))
    assert any("슬롯 수정" in t for t in last_bubble_buttons(panel))


def test_reroll_screen_bubble_buttons_and_adoption(panel):
    panel.on_confirm_mod_review(scan(panel))
    w = panel.diagnoser.indexer.fuzzy_match_weapon("Vulkar")
    res = panel.diagnoser.compare_riven_rolls(w, {"stats": {"multishot": 0.5}, "unapplied": []}, {"stats": {"multishot": 0.9}, "unapplied": []})
    panel._show_riven_compare(res)
    buttons = last_bubble_buttons(panel)
    assert {"📊 상세 비교", "✏️ 옵션 수정", "💾 새 옵션 사용"} <= set(buttons)

    buttons["💾 새 옵션 사용"].click()
    assert panel.diagnoser.build_store.get_build("Vulkar")["riven"] == {"multishot": 0.9}
    assert buttons["💾 새 옵션 사용"].isEnabled() is False


def test_no_adopt_button_without_build(panel):
    w = panel.diagnoser.indexer.fuzzy_match_weapon("Vulkar")
    res = panel.diagnoser.compare_riven_rolls(w, {"stats": {"multishot": 0.5}, "unapplied": []}, {"stats": {"multishot": 0.9}, "unapplied": []})
    panel._show_riven_compare(res)
    assert "💾 새 옵션 사용" not in last_bubble_buttons(panel)


def test_delete_confirmation_button_deletes(qapp, panel):
    panel.on_confirm_mod_review(scan(panel))
    panel.orchestrator.chat = lambda text: {"type": "BUILD_DELETE_CONFIRM", "weapon": "Vulkar", "report": "삭제할까요?"}
    panel.tracker.process_chat_todo_command = lambda text: None
    panel.input_edit.setText("불카 빌드 삭제")
    before = panel.chat_list_layout.count()
    panel.send_user_message()
    for _ in range(200):
        qapp.processEvents()
        if any("삭제" == t.replace("🗑️ ", "") for t in last_bubble_buttons(panel)):
            break
        QThread.msleep(10)
    assert panel.diagnoser.build_store.get_build("Vulkar") is not None
    last_bubble_buttons(panel)["🗑️ 삭제"].click()
    assert panel.diagnoser.build_store.get_build("Vulkar") is None


def test_riven_quick_input_has_opaque_card(qapp):
    from scripts.riven_quick_dialog import QFrame
    dialog = RivenQuickInputDialog()
    card = dialog.findChild(QFrame, "framelessCard")
    assert card is not None
    assert "background-color" in card.styleSheet()
    assert dialog.quick_input.parent() is card


class _SyncThread:
    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


@pytest.fixture
def hidden_panel(panel, monkeypatch):
    # process_screen_image() pops the window up; keep it hidden so later window tests are unaffected.
    monkeypatch.setattr("scripts.desktop_companion.threading.Thread", _SyncThread)
    monkeypatch.setattr(panel, "show", lambda: None)
    return panel


def test_riven_second_f9_reads_card_and_resumes(hidden_panel):
    panel = hidden_panel
    d = panel.diagnoser
    stats = {"crit_chance": 1.5, "crit_damage": 1.2}
    d.has_pending_riven = MagicMock(return_value=True)
    d.extract_riven_stats_from_screen = MagicMock(return_value=stats)
    d.resume_pending_riven = MagicMock(return_value={"success": True, "message": "리벤 리포트"})
    d.diagnose_screenshot = MagicMock()
    panel.process_screen_image(object())
    d.resume_pending_riven.assert_called_once_with(stats)
    d.diagnose_screenshot.assert_not_called()


def test_riven_pending_without_card_falls_back_to_diagnosis(hidden_panel):
    panel = hidden_panel
    d = panel.diagnoser
    d.has_pending_riven = MagicMock(return_value=True)
    d.extract_riven_stats_from_screen = MagicMock(return_value=None)
    d.resume_pending_riven = MagicMock()
    d.diagnose_screenshot = MagicMock(return_value={"message": "분석 완료"})
    panel.process_screen_image(object())
    d.resume_pending_riven.assert_not_called()
    d.diagnose_screenshot.assert_called_once()
