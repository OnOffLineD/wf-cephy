import os
import tempfile
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QPoint, QPointF
    from PyQt6.QtGui import QMouseEvent
except ImportError:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QPoint, QPointF
    from PySide6.QtGui import QMouseEvent

from scripts.frameless_dialog import FramelessDialog
from scripts.persona_manager import PersonaManager, SettingsManager
from scripts.persona_dialog import OrdisPersonaDialog, SettingsDialog
from scripts.damage_breakdown_dialog import DamageBreakdownDialog
from scripts.riven_quick_dialog import RivenQuickInputDialog
from scripts.build_edit_dialog import BuildEditDialog
from scripts.riven_compare_dialog import RivenCompareDialog, RivenRollEditDialog
from scripts.desktop_companion import OrdisCompanionApp

@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])

def test_settings_model_and_context_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_settings.json")
        sm = SettingsManager(config_path=cfg_path)
        
        # Test defaults
        assert sm.get_context_size() == 4096
        assert sm.get_gpu_layers() == 99
        assert "gguf" in sm.get_model_path().lower()

        # Update values
        sm.set_model_path("models/custom_test_v2.gguf")
        sm.set_context_size(8192)
        sm.set_gpu_layers(45)

        assert sm.get_model_path() == "models/custom_test_v2.gguf"
        assert sm.get_context_size() == 8192
        assert sm.get_gpu_layers() == 45

        # Re-load from disk to verify persistence
        sm2 = SettingsManager(config_path=cfg_path)
        assert sm2.get_model_path() == "models/custom_test_v2.gguf"
        assert sm2.get_context_size() == 8192
        assert sm2.get_gpu_layers() == 45

def test_settings_dialog_frameless_and_assets(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = os.path.join(tmpdir, "test_settings.json")
        sm = SettingsManager(config_path=cfg_path)
        
        dlg = SettingsDialog(persona_manager=sm)
        
        # 1. Headless / Frameless check & FramelessDialog inheritance
        assert isinstance(dlg, FramelessDialog)
        assert bool(dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

        # 2. Assets presence check
        assert not dlg.btn_save.icon().isNull()
        assert not dlg.btn_cancel.icon().isNull()

        # 3. Model settings controls check
        assert hasattr(dlg, "model_path_edit")
        assert hasattr(dlg, "context_size_spin")
        assert hasattr(dlg, "gpu_layers_spin")

        # 4. Modify settings through dialog
        dlg.model_path_edit.setText("models/my_custom_model.gguf")
        dlg.context_size_spin.setValue(16384)
        dlg.gpu_layers_spin.setValue(33)
        dlg.radio_caretaker.setChecked(True)
        dlg.save()

        # Check saved values
        assert sm.get_mode() == "caretaker"
        assert sm.get_model_path() == "models/my_custom_model.gguf"
        assert sm.get_context_size() == 16384
        assert sm.get_gpu_layers() == 33

def test_all_popup_dialogs_frameless(qapp):
    # Damage breakdown dialog
    dmg_dlg = DamageBreakdownDialog()
    assert isinstance(dmg_dlg, FramelessDialog)
    assert bool(dmg_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    # Riven quick input dialog
    riven_dlg = RivenQuickInputDialog()
    assert isinstance(riven_dlg, FramelessDialog)
    assert bool(riven_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    # Build edit dialog
    slots = {"slot1": "Serration"}
    mod_choices = [("Serration", "Serration")]
    edit_dlg = BuildEditDialog(slots=slots, mod_choices=mod_choices)
    assert isinstance(edit_dlg, FramelessDialog)
    assert bool(edit_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    # Riven compare & roll edit dialogs
    res = {
        "verdict": "오른쪽 유지",
        "rows": [("피해", 100.0, 150.0)],
        "old_card": {"name": "Old", "stats": {"피해": 100.0}},
        "new_card": {"name": "New", "stats": {"피해": 150.0}}
    }
    comp_dlg = RivenCompareDialog(res)
    assert isinstance(comp_dlg, FramelessDialog)
    assert bool(comp_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    roll_dlg = RivenRollEditDialog({"피해": 100.0}, {"피해": 150.0})
    assert isinstance(roll_dlg, FramelessDialog)
    assert bool(roll_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

def test_chat_popup_draggable(qapp):
    panel = OrdisCompanionApp()
    initial_pos = QPoint(200, 300)
    panel.move(initial_pos)
    panel.show()
    assert panel._user_moved is False

    # Simulate mouse press at local pos (50, 10) inside header
    press_global = QPointF(250.0, 310.0)
    press_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(50.0, 10.0),
        press_global,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    panel.mousePressEvent(press_event)

    # Simulate mouse drag by (+80, +120)
    move_global = QPointF(330.0, 430.0)
    move_event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(130.0, 130.0),
        move_global,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier
    )
    panel.mouseMoveEvent(move_event)

    # Verify panel position moved and _user_moved is flagged
    assert panel.pos() == QPoint(280, 420)
    assert panel._user_moved is True

    # Release
    release_event = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(130.0, 130.0),
        move_global,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier
    )
    panel.mouseReleaseEvent(release_event)
    panel.close()


def _drag(target, start_global, delta):
    """Simulate press -> move -> release on `target` using global coordinates."""
    btn, nob, mod = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier
    end_global = start_global + delta
    target.mousePressEvent(QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(5.0, 5.0), start_global, btn, btn, mod))
    target.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(5.0, 5.0) + delta, end_global, btn, btn, mod))
    release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(5.0, 5.0) + delta, end_global, btn, nob, mod)
    target.mouseReleaseEvent(release)
    return release


def test_frameless_dialog_stays_on_top(qapp):
    dlg = SettingsDialog(persona_manager=SettingsManager(config_path=os.path.join(tempfile.gettempdir(), "t_ui5_top.json")))
    assert bool(dlg.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) is True
    assert bool(dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True
    assert bool(DamageBreakdownDialog().windowFlags() & Qt.WindowType.WindowStaysOnTopHint) is True


@pytest.mark.parametrize("drag_source", ["header", "card"])
def test_settings_buttons_clickable_after_drag(qapp, drag_source):
    try:
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QFrame, QDialog
    except ImportError:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QFrame, QDialog

    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SettingsManager(config_path=os.path.join(tmpdir, "s.json"))
        for which in ("cancel", "save"):
            dlg = SettingsDialog(persona_manager=sm)
            dlg.move(QPoint(100, 100))
            dlg.show()
            qapp.processEvents()
            start = dlg.frameGeometry().topLeft()

            source = dlg.findChild(QFrame, "framelessHeader") if drag_source == "header" else dlg.main_card
            assert source is not None
            release = _drag(source, QPointF(float(start.x() + 20), float(start.y() + 20)), QPointF(60.0, 40.0))
            qapp.processEvents()

            # Dialog moved, drag state cleared, release accepted
            assert dlg.frameGeometry().topLeft() == start + QPoint(60, 40)
            assert dlg._drag_pos.isNull()
            assert release.isAccepted()

            # A stray move after release must not drag the dialog anymore
            moved_pos = dlg.pos()
            dlg.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(1.0, 1.0), QPointF(900.0, 900.0),
                                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
            assert dlg.pos() == moved_pos

            fired = []
            if which == "cancel":
                dlg.btn_cancel.clicked.connect(lambda: fired.append("cancel"))
                QTest.mouseClick(dlg.btn_cancel, Qt.MouseButton.LeftButton)
                assert fired == ["cancel"]
                assert dlg.result() == QDialog.DialogCode.Rejected
            else:
                dlg.radio_tactical.setChecked(True)
                dlg.context_size_spin.setValue(8192)
                dlg.btn_save.clicked.connect(lambda: fired.append("save"))
                QTest.mouseClick(dlg.btn_save, Qt.MouseButton.LeftButton)
                assert fired == ["save"]
                assert dlg.result() == QDialog.DialogCode.Accepted
                assert sm.get_mode() == "tactical"
                assert sm.get_context_size() == 8192
            assert not dlg.isVisible()


def test_settings_dialog_hud_icons_and_no_emojis(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SettingsManager(config_path=os.path.join(tmpdir, "test_settings.json"))
        dlg = SettingsDialog(persona_manager=sm)

        # Section headers carry HUD glyph pixmaps (model / context / gpu)
        for icon_lbl in (dlg.sec1_icon, dlg.sec2_icon, dlg.sec3_icon):
            pix = icon_lbl.pixmap()
            assert pix is not None and not pix.isNull()
        assert dlg.sec1_title.text() == "로컬 GGUF 모델 파일 지정"
        assert dlg.sec2_title.text() == "컨텍스트 길이 (Context Size / Token Window)"
        assert dlg.sec3_title.text() == "GPU 가속 레이어 수 (n_gpu_layers)"

        # Browse button uses the browse icon
        assert not dlg.btn_browse.icon().isNull()
        assert dlg.btn_browse.text() == " 찾아보기"

        emojis = ("🧠", "📏", "⚡", "📁", "📦", "🎲", "🛡", "🎯", "✏")
        texts = [dlg.sec1_title.text(), dlg.sec2_title.text(), dlg.sec3_title.text(),
                 dlg.btn_browse.text(), dlg.lbl_custom_title.text()]
        texts += [b.text() for b in (dlg.radio_random, dlg.radio_caretaker, dlg.radio_glitch,
                                     dlg.radio_tactical, dlg.radio_custom)]
        texts += [dlg.model_combo.itemText(i) for i in range(dlg.model_combo.count())]
        for t in texts:
            assert not any(e in t for e in emojis), t

        # Context preset chips highlight the matching value
        dlg.context_size_spin.setValue(8192)
        assert dlg.ctx_preset_buttons[8192].isChecked()
        assert not dlg.ctx_preset_buttons[4096].isChecked()
        dlg.ctx_preset_buttons[2048].click()
        assert dlg.context_size_spin.value() == 2048
        assert dlg.ctx_preset_buttons[2048].isChecked()
        assert not dlg.ctx_preset_buttons[8192].isChecked()
        dlg.context_size_spin.setValue(3000)
        assert not any(b.isChecked() for b in dlg.ctx_preset_buttons.values())
