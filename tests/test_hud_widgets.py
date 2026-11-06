import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PySide6.QtWidgets import QApplication

from scripts.hud_widgets import HudButton, COMPACT_WIDTH, load_icon_pixmap


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_compact_size_hint_is_32(qapp):
    btn = HudButton("화면 캡처 [F9]", icon_name="capture", icon_only=True)
    assert btn.hover_t == 0.0
    assert btn.sizeHint().width() == 32
    assert COMPACT_WIDTH == 32
    assert 28 <= btn.sizeHint().height() <= 32


def test_hover_unfolds_width(qapp):
    btn = HudButton("화면 캡처 [F9]", icon_name="capture", icon_only=True)
    btn.hover_t = 0.5
    half = btn.sizeHint().width()
    btn.hover_t = 1.0
    full = btn.sizeHint().width()
    assert 32 < half < full
    btn.hover_t = 0.0
    assert btn.sizeHint().width() == 32


def test_non_icon_only_always_shows_label(qapp):
    btn = HudButton("붙여넣기", icon_name="clipboard", icon_only=False)
    assert btn.sizeHint().width() > 32


def test_clicked_signal(qapp):
    btn = HudButton("실시간 갱신", icon_name="refresh")
    hits = []
    btn.clicked.connect(lambda *a: hits.append(True))
    btn.click()
    assert hits == [True]


def test_busy_starts_and_stops_timer(qapp):
    btn = HudButton("화면 캡처 [F9]", icon_name="capture")
    assert btn.is_busy is False
    btn.set_busy(True)
    assert btn.is_busy is True
    assert btn._busy_timer.isActive()
    btn.set_busy(False)
    assert btn.is_busy is False
    assert not btn._busy_timer.isActive()


def test_icon_loading_and_fallback_paint(qapp):
    assert load_icon_pixmap("capture") is not None
    assert load_icon_pixmap("close") is None
    for name in ("capture", "close"):
        btn = HudButton("닫기", icon_name=name)
        btn.hover_t = 1.0
        btn.set_busy(True)
        btn.resize(btn.sizeHint())
        img = btn.grab()  # exercises paintEvent incl. brackets, arc, label, glyph fallback
        assert not img.isNull()
        btn.set_busy(False)
