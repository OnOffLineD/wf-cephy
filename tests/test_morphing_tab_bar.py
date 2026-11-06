import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest

try:
    from PyQt6.QtWidgets import QApplication, QWidget
except ImportError:
    from PySide6.QtWidgets import QApplication, QWidget

from scripts.morphing_tab_bar import MorphingTabBar, TRAIL_MS


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def _make_bar():
    bar = MorphingTabBar()
    bar.add_tab("채팅", icon_name="chat")
    bar.add_tab("숙제", icon_name="todo")
    return bar


def test_add_tab_with_icons(qapp):
    bar = _make_bar()
    assert len(bar.tabs) == 2
    assert [t["text"] for t in bar.tabs] == ["채팅", "숙제"]
    assert bar.tabs[0]["icon_name"] == "chat"
    assert bar.tabs[0]["pixmap"] is not None  # assets/icons/chat.png loaded
    bar.add_tab("plain")  # legacy signature still works
    assert bar.tabs[2]["icon_name"] is None
    r = bar._rects
    assert r[0].right() < r[1].left() < r[2].left()


def test_switch_tab_emits_signal(qapp):
    bar = _make_bar()
    got = []
    bar.tab_changed.connect(got.append)
    bar.switch_tab(0)
    bar.switch_tab(1)
    bar.switch_tab(5)  # out of range: ignored
    assert got == [0, 1]
    assert bar.active_index == 1


def test_indicator_settles_on_target(qapp, monkeypatch):
    calls = []
    monkeypatch.setattr(QWidget, "setStyleSheet", lambda self, s: calls.append(s))
    bar = _make_bar()
    bar.show()
    bar.switch_tab(0)
    assert bar._l == bar._r == 0.0
    widths_before = [r.width() for r in bar._rects]

    bar.switch_tab(1)
    _pump(qapp, 90)
    # Mid-flight: leading (right) edge runs ahead of the trailing (left) edge.
    assert bar._r > bar._l
    assert bar.indicator_rect().width() > bar._rects[0].width()

    _pump(qapp, TRAIL_MS + 200)
    assert bar._l == bar._r == 1.0
    ind = bar.indicator_rect()
    target = bar._rects[1]
    assert abs(ind.left() - target.left()) < 1e-6
    assert abs(ind.right() - target.right()) < 1e-6
    assert [r.width() for r in bar._rects] == widths_before
    bar.repaint()  # QPainter path runs without error
    assert calls == []
    bar.close()


def test_backward_switch_leads_with_left_edge(qapp):
    bar = _make_bar()
    bar.switch_tab(1)
    bar.switch_tab(0)
    _pump(qapp, 90)
    assert bar._l < bar._r
    _pump(qapp, TRAIL_MS + 200)
    assert bar._l == bar._r == 0.0
