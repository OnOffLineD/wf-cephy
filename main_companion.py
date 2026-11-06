try:
    import torch
except Exception:
    pass
import sys
import os

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PySide6.QtWidgets import QApplication
from scripts.desktop_companion import DesktopPet, OrdisCompanionApp, handle_uncaught_exception

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WF-Companion")
    # Closing the chat panel leaves the pet running; the app quits from the pet's menu.
    app.setQuitOnLastWindowClosed(False)

    # Main dashboard panel (headless popover, hidden by default)
    panel = OrdisCompanionApp()
    sys.excepthook = lambda *exc_info: handle_uncaught_exception(*exc_info, panel=panel)
    app.aboutToQuit.connect(panel.llm_runner.stop_server)
    panel.start_llm_in_background()
    panel.check_game_data_in_background()

    # Floating pet widget (shown by default)
    pet = DesktopPet(asset_dir=os.path.join(ROOT_DIR, "assets", "character"))
    panel.pet = pet

    def toggle_panel():
        if panel.isVisible() and panel.windowOpacity() > 0.05:
            panel.animate_hide()
        else:
            panel.animate_show(pet.geometry())

    pet.clicked.connect(toggle_panel)
    pet.open_persona_requested.connect(lambda: (panel.show(), panel.open_persona_dialog()))
    pet.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
