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

        # 2. Verify tab stack exists and has 3 tabs (Chat, Todo, Status)
        assert hasattr(panel, "tab_stack"), "OrdisCompanionApp must have tab_stack"
        assert panel.tab_stack.count() == 3, f"Expected 3 tabs, got {panel.tab_stack.count()}"

        # 3. Verify default tab is Chat (index 0)
        assert panel.tab_stack.currentIndex() == 0, f"Expected default tab index 0 (Chat), got {panel.tab_stack.currentIndex()}"

        # 4. Verify tab switching
        panel.switch_tab(1)
        assert panel.tab_stack.currentIndex() == 1, "Switching to tab 1 (Todo) failed"

        panel.switch_tab(2)
        assert panel.tab_stack.currentIndex() == 2, "Switching to tab 2 (Status) failed"

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
