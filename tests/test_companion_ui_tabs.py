import sys
import os
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QRect
except ImportError:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QRect

from scripts.desktop_companion import OrdisCompanionApp, DesktopPet


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_ordis_companion_headless_and_tabs(qapp):
    panel = OrdisCompanionApp()
    try:
        # 1. Verify headless/frameless window flags
        flags = panel.windowFlags()
        assert bool(flags & Qt.WindowType.FramelessWindowHint), "Window must have FramelessWindowHint"
        assert bool(flags & Qt.WindowType.WindowStaysOnTopHint), "Window must have WindowStaysOnTopHint"

        # 2. Verify tab stack exists and has 4 tabs (Chat, Todo, Status, Build)
        assert hasattr(panel, "tab_stack"), "OrdisCompanionApp must have tab_stack"
        assert panel.tab_stack.count() == 4, f"Expected 4 tabs, got {panel.tab_stack.count()}"
        assert panel.tab_bar.tabs[3]['text'] == '빌드'

        # 3. Verify default tab is Chat (index 0)
        assert panel.tab_stack.currentIndex() == 0, f"Expected default tab index 0 (Chat), got {panel.tab_stack.currentIndex()}"

        # 4. Verify tab switching
        panel.switch_tab(1)
        assert panel.tab_stack.currentIndex() == 1, "Switching to tab 1 (Todo) failed"

        panel.switch_tab(2)
        assert panel.tab_stack.currentIndex() == 2, "Switching to tab 2 (Status) failed"

        panel.switch_tab(3)
        assert panel.tab_stack.currentIndex() == 3, "Switching to tab 3 (Build) failed"
        assert panel.tab_stack.currentWidget() is panel.build_page

        panel.switch_tab(0)
        assert panel.tab_stack.currentIndex() == 0, "Switching back to tab 0 (Chat) failed"

        # 5. Verify reposition_above_pet method
        pet_rect = QRect(500, 700, 130, 130)
        panel.reposition_above_pet(pet_rect)
        pos = panel.pos()
        assert pos.y() < pet_rect.y(), f"Panel y ({pos.y()}) should be above pet y ({pet_rect.y()})"

        # 6. Verify animate_show and animate_hide methods
        assert hasattr(panel, "animate_show"), "OrdisCompanionApp must have animate_show"
        assert hasattr(panel, "animate_hide"), "OrdisCompanionApp must have animate_hide"
        panel.animate_show(pet_rect)
        assert panel.isVisible(), "Panel must be visible after animate_show"

    finally:
        panel.close()


def test_companion_hud_buttons_and_icon_tabs(qapp):
    from scripts.hud_widgets import HudButton

    panel = OrdisCompanionApp()
    try:
        assert [t["icon_name"] for t in panel.tab_bar.tabs] == ["chat", "todo", "status", "build"]
        assert [t["text"] for t in panel.tab_bar.tabs] == ["채팅", "숙제", "현황", "빌드"]

        for name in ("btn_full", "btn_clip", "btn_refresh", "btn_send", "refresh_btn", "persona_btn", "close_btn"):
            assert isinstance(getattr(panel, name), HudButton), f"{name} must be a HudButton"
        assert panel.btn_full.icon_name == "capture" and panel.btn_full.icon_only
        assert panel.btn_clip.icon_name == "clipboard" and panel.btn_clip.icon_only
        assert panel.btn_refresh.icon_name == "refresh" and panel.btn_refresh.icon_only
        assert panel.btn_send.icon_name == "send" and not panel.btn_send.icon_only
        assert panel.persona_btn.icon_name in ("settings", "persona") and panel.persona_btn.text() == ""
        assert "설정" in panel.persona_btn.toolTip()
        assert panel.close_btn.icon_name == "close"

        emojis = ("💬", "📋", "🌍", "🎭", "🖥️", "🔄")
        texts = [t["text"] for t in panel.tab_bar.tabs] + [
            getattr(panel, n).text() for n in ("btn_full", "btn_clip", "btn_refresh", "btn_send", "refresh_btn", "persona_btn", "close_btn")
        ]
        for text in texts:
            assert not any(e in text for e in emojis), f"emoji left in {text!r}"

        # Busy feedback: set on refresh start, cleared by the done signal.
        panel.btn_refresh.set_busy(False)
        panel.tracker.fetch_live_events = lambda: {}
        import threading as _t
        orig_thread = _t.Thread
        started = []

        class _NoThread:
            def __init__(self, target=None, daemon=None):
                started.append(target)

            def start(self):
                pass

        _t.Thread = _NoThread
        try:
            panel.refresh_world_events()
        finally:
            _t.Thread = orig_thread
        assert panel.btn_refresh.is_busy
        panel.world_events_done_signal.emit()
        assert not panel.btn_refresh.is_busy
        assert started, "refresh_world_events must start a fetch thread"
    finally:
        panel.close()


def test_build_vault_tab_empty_and_saved_build(qapp, tmp_path, monkeypatch):
    from scripts import desktop_companion as dc
    from scripts.build_store import BuildStore, RIVEN_MOD

    panel = OrdisCompanionApp()
    try:
        store = BuildStore(str(tmp_path / "user_builds.json"))
        panel.diagnoser.build_store = store

        # Empty vault: the empty-state label shows and the build card hides.
        panel.switch_tab(3)
        assert panel.tab_stack.currentWidget() is panel.build_page
        assert panel.build_combo.count() == 0
        assert not panel.build_empty_label.isHidden()
        assert "저장된 모딩이 없습니다" in panel.build_empty_label.text()
        assert panel.build_card.isHidden()

        # 2x4 grid of slot cards and the three action buttons.
        assert len(panel.build_slot_labels) == 8
        positions = [panel.build_grid.getItemPosition(panel.build_grid.indexOf(lbl))[:2] for lbl in panel.build_slot_labels]
        assert positions == [(r, c) for r in range(2) for c in range(4)]
        assert panel.build_analyze_btn.text() == "📊 데미지 분석"
        assert panel.build_edit_btn.text() == "✏️ 슬롯 수정"
        assert panel.build_delete_btn.text() == "🗑️ 빌드 삭제"

        store.save_build({
            "weapon": "TestGun", "kr_name": "테스트건", "category": "Primary",
            "slots": {"R1_C1": "Serration", "R2_C4": RIVEN_MOD}, "extra": [], "arcane": None,
            "panel": {}, "panel_has_riven": True, "panel_riven": None, "panel_removed": [],
            "riven": {"crit_chance": 1.5},
        })
        panel.switch_tab(0)
        panel.switch_tab(3)  # switching to the tab refreshes the vault
        assert panel.build_combo.count() == 1
        assert panel.build_combo.currentData() == "TestGun"
        assert "테스트건" in panel.build_combo.currentText()
        assert panel.build_empty_label.isHidden()
        assert not panel.build_card.isHidden()
        assert panel.build_slot_labels[0].text().startswith("#1\n")
        assert "(빈 슬롯)" in panel.build_slot_labels[1].text()
        assert "[리벤]" in panel.build_slot_labels[7].text()
        assert panel.build_stats_label.text()

        # Delete asks first: declining keeps the build, accepting removes it and refreshes the UI.
        monkeypatch.setattr(dc.QMessageBox, "question", staticmethod(lambda *a, **k: dc.QMessageBox.StandardButton.No))
        panel._delete_selected_build()
        assert store.get_build("TestGun") is not None
        monkeypatch.setattr(dc.QMessageBox, "question", staticmethod(lambda *a, **k: dc.QMessageBox.StandardButton.Yes))
        panel._delete_selected_build()
        assert store.get_build("TestGun") is None
        assert panel.build_combo.count() == 0
        assert not panel.build_empty_label.isHidden()
    finally:
        panel.close()
