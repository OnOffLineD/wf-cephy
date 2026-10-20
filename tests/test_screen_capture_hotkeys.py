import pytest
from unittest.mock import patch, MagicMock
from PIL import Image

def test_capture_fullscreen_methods_exist():
    from scripts.desktop_companion import OrdisCompanionApp
    assert hasattr(OrdisCompanionApp, 'capture_fullscreen_and_analyze')
    assert hasattr(OrdisCompanionApp, 'setup_global_hotkeys')
    assert hasattr(OrdisCompanionApp, 'eventFilter')

def test_capture_fullscreen_execution():
    from scripts.desktop_companion import OrdisCompanionApp
    mock_app = MagicMock(spec=OrdisCompanionApp)
    mock_app.process_screen_image = MagicMock()
    mock_app.windowState = MagicMock(return_value=0)
    mock_app.setWindowState = MagicMock()
    mock_app.show = MagicMock()
    mock_app.raise_ = MagicMock()
    mock_app.activateWindow = MagicMock()

    with patch('scripts.desktop_companion.QEventLoop'), \
         patch('PIL.ImageGrab.grab', return_value=Image.new('RGB', (100, 100))):
        OrdisCompanionApp.capture_fullscreen_and_analyze(mock_app)
        mock_app.process_screen_image.assert_called_once()