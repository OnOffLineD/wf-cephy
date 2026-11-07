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
        
        # 1. Headless / Frameless check
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
    assert bool(dmg_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    # Riven quick input dialog
    riven_dlg = RivenQuickInputDialog()
    assert bool(riven_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    # Build edit dialog
    slots = {"slot1": "Serration"}
    mod_choices = [("Serration", "Serration")]
    edit_dlg = BuildEditDialog(slots=slots, mod_choices=mod_choices)
    assert bool(edit_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    # Riven compare & roll edit dialogs
    res = {
        "verdict": "오른쪽 유지",
        "rows": [("피해", 100.0, 150.0)],
        "old_card": {"name": "Old", "stats": {"피해": 100.0}},
        "new_card": {"name": "New", "stats": {"피해": 150.0}}
    }
    comp_dlg = RivenCompareDialog(res)
    assert bool(comp_dlg.windowFlags() & Qt.WindowType.FramelessWindowHint) is True

    roll_dlg = RivenRollEditDialog({"피해": 100.0}, {"피해": 150.0})
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
