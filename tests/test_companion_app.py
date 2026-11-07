import threading

import pytest
from PIL import Image

try:
    from PyQt6.QtCore import QThread
    from PyQt6.QtGui import QColor, QImage
    from PyQt6.QtWidgets import QApplication, QLabel
except ImportError:
    from PySide6.QtCore import QThread
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication, QLabel

from scripts.desktop_companion import ChatBubble, OrdisCompanionApp, qimage_to_pil, render_chat_markup


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp, monkeypatch):
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    app = OrdisCompanionApp()
    yield app
    app.close()


def drain(qapp, panel, done):
    for _ in range(200):
        qapp.processEvents()
        if done():
            return
        QThread.msleep(10)


def test_markup_renders_bold_code_and_newlines():
    out = render_chat_markup("**제목**\n`123` 값")
    assert "<b>제목</b>" in out and "<br>" in out and "123" in out and "`" not in out and "**" not in out


def test_markup_escapes_html():
    assert "<script>" not in render_chat_markup("<script>x</script>")


def test_ordis_bubble_is_rich_text_and_user_bubble_is_plain(qapp):
    ordis = ChatBubble("오디스", "**굵게**", is_user=False)
    user = ChatBubble("나", "**<b>원문</b>**", is_user=True)
    assert any("<b>굵게</b>" in label.text() for label in ordis.findChildren(QLabel))
    assert any(label.text() == "**<b>원문</b>**" for label in user.findChildren(QLabel))


@pytest.mark.parametrize("width", [1366, 1367, 1921])
def test_qimage_conversion_handles_row_padding(qapp, width):
    image = QImage(width, 4, QImage.Format.Format_RGB32)
    image.fill(QColor(10, 20, 30))
    image.setPixelColor(width - 1, 3, QColor(200, 100, 50))
    converted = qimage_to_pil(image)
    assert converted.size == (width, 4)
    assert converted.getpixel((0, 1)) == (10, 20, 30)
    assert converted.getpixel((width - 1, 3)) == (200, 100, 50)


def test_creating_panel_does_not_start_llm(panel):
    assert panel.llm_runner.process is None


def test_closing_panel_keeps_llm_running(panel):
    calls = []
    panel.llm_runner.stop_server = lambda: calls.append(1)
    panel.close()
    assert calls == []


def test_failed_llm_start_is_reported_in_chat(qapp, panel):
    panel.llm_runner.start_server = lambda wait_ready=False: False
    panel.llm_runner.last_error = "실행 파일이 없습니다"
    before = panel.chat_list_layout.count()
    panel.start_llm_in_background()
    drain(qapp, panel, lambda: panel.chat_list_layout.count() > before)
    assert panel.chat_list_layout.count() > before
    assert any("실행 파일이 없습니다" in label.text() for label in panel.chat_list_layout.itemAt(before).widget().findChildren(QLabel))


def test_llm_ready_is_announced_in_chat(qapp, panel):
    panel.llm_runner.start_server = lambda wait_ready=False: True
    before = panel.chat_list_layout.count()
    panel.start_llm_in_background()
    drain(qapp, panel, lambda: panel.chat_list_layout.count() > before)
    assert any("준비" in label.text() for label in panel.chat_list_layout.itemAt(before).widget().findChildren(QLabel))


def test_pet_is_updated_on_ui_thread(qapp, panel):
    seen = []

    class FakePet:
        def set_mood(self, *a, **k):
            seen.append(threading.current_thread() is threading.main_thread())

        def start_talking(self, *a, **k):
            seen.append(threading.current_thread() is threading.main_thread())

    panel.pet = FakePet()
    panel.orchestrator.chat = lambda text: {"report": "응답", "mood": "happy", "intensity": 1}
    panel.tracker.process_chat_todo_command = lambda text: None
    panel.input_edit.setText("안녕")
    panel.send_user_message()
    drain(qapp, panel, lambda: len(seen) >= 3)
    assert len(seen) >= 3
    assert all(seen)


def test_diagnosis_without_breakdown_but_pending_riven_does_not_crash(qapp, panel):
    panel.diagnoser.has_pending_riven = lambda: True
    action = panel._result_action({"message": "x"})
    assert action["has_pending_riven"] is True


def test_result_action_is_none_when_nothing_to_offer(panel):
    panel.diagnoser.has_pending_riven = lambda: False
    assert panel._result_action({"message": "x"}) is None


def test_confirm_mod_review_without_breakdown_does_not_crash(panel):
    panel.diagnoser.has_pending_riven = lambda: True
    panel.on_confirm_mod_review({"message": "결과"})


def test_typed_confirmation_runs_pending_review(qapp, panel):
    panel.diagnoser.has_pending_riven = lambda: False
    panel.diagnoser.diagnose_screenshot = lambda img: {"review_message": "검토", "message": "최종 결과", "calculation_breakdown": ""}
    panel.process_screen_image(Image.new("RGB", (10, 10)))
    drain(qapp, panel, lambda: getattr(panel, "_pending_mod_review", None) is not None)
    assert panel._pending_mod_review is not None
    panel.tracker.process_chat_todo_command = lambda text: None
    panel.input_edit.setText("맞아")
    panel.send_user_message()
    assert panel._pending_mod_review is None


def test_other_message_clears_pending_review(qapp, panel):
    panel._pending_mod_review = {"message": "오래된 결과"}
    panel.orchestrator.chat = lambda text: {"report": "응답"}
    panel.tracker.process_chat_todo_command = lambda text: None
    panel.input_edit.setText("보스 공략 알려줘")
    panel.send_user_message()
    assert panel._pending_mod_review is None


def test_show_and_hide_animations_settle_final_opacity(qapp, panel):
    panel.animate_show()
    drain(qapp, panel, lambda: panel._anim_group.state() == panel._anim_group.State.Stopped)
    assert abs(panel.windowOpacity() - 0.94) < 0.02
    panel.animate_hide()
    drain(qapp, panel, lambda: not panel.isVisible())
    assert not panel.isVisible()
    # Reset while hidden, so a later plain show() is not an invisible click-blocker.
    assert abs(panel.windowOpacity() - 0.94) < 0.02


def test_name_translator_uses_codex_korean(panel):
    assert panel.tracker.name_translator("Braton") == "브래튼"
    assert panel.tracker.name_translator("없는무기") == "없는무기"
