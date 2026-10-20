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
from scripts.desktop_companion import DesktopPet, OrdisCompanionApp
from scripts.embedded_llm_runner import EmbeddedLLMRunner

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WF-Companion")

    # Start portable embedded LLM server with Job Object protection
    llm_runner = EmbeddedLLMRunner()
    llm_runner.start_server(wait_ready=False)
    app.aboutToQuit.connect(llm_runner.stop_server)

    # Main dashboard panel (headless popover, hidden by default)
    panel = OrdisCompanionApp()

    # Floating pet widget (shown by default)
    pet = DesktopPet(asset_dir=os.path.join(ROOT_DIR, "assets", "character"))

    def toggle_panel():
        if panel.isVisible() and panel.windowOpacity() > 0.05:
            panel.animate_hide()
        else:
            panel.animate_show(pet.geometry())

    pet.clicked.connect(toggle_panel)
    pet.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
