import pytest   # conftest.py forces QT_QPA_PLATFORM=offscreen
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect, QPointF, Qt, QEvent
from PyQt6.QtGui import QMouseEvent, QEnterEvent
from scripts.desktop_pet import compute_bubble_anchor
from scripts.notification_coordinator import NotificationCoordinator, NotificationPriority as P, SpeechBubblePayload
from scripts.pet_speech_bubble import PetSpeechBubbleWidget, TAIL_H

APP = QApplication.instance() or QApplication([])   # keep a reference: a GC'd QApplication crashes Qt


@pytest.fixture
def coord():
    NotificationCoordinator.reset_instance()
    NotificationCoordinator._instance = c = NotificationCoordinator(clock=lambda: c.now)
    c.now = 100.0
    yield c
    NotificationCoordinator.reset_instance()


def left_click(w):
    w.mousePressEvent(QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(9, 9), QPointF(9, 9), Qt.MouseButton.LeftButton,
                                  Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))


def test_notify_shows_bubble_and_queue_order(coord):
    assert NotificationCoordinator.get_instance() is coord and coord.notify("first", P.HIGH)
    w = coord.current_widget
    assert isinstance(w, PetSpeechBubbleWidget) and w.isVisible() and w.label.text() == "first"
    assert w.dismiss_timer.isActive() and w.dismiss_timer.interval() == 5000
    for text, prio in [("low", P.LOW), ("na", P.NORMAL), ("nb", P.NORMAL), ("crit", P.CRITICAL)]:
        coord.notify(text, prio)
    assert [p.text for p in coord.pending()] == ["crit", "na", "nb", "low"]   # CRITICAL waits behind HIGH
    shown = []
    while coord.current_widget is not None:
        shown.append(coord.current_payload.text)
        coord.current_widget.dismiss(animate=False)
    assert shown == ["first", "crit", "na", "nb", "low"] and coord.pending() == []


def test_high_preempts_low_but_normal_does_not(coord):
    coord.notify("잡담", P.LOW)
    coord.notify("보통", P.NORMAL)
    low_widget = coord.current_widget
    assert coord.current_payload.text == "잡담"
    coord.notify("긴급: 출격 경보", P.HIGH)
    assert coord.current_payload.text == "긴급: 출격 경보" and coord.current_widget is not low_widget
    assert not low_widget.isVisible() and [p.text for p in coord.pending()] == ["보통"]


def test_debounce_and_queue_limit(coord):
    assert coord.notify("시터스 밤", key="cetus") is True
    assert coord.notify("시터스 밤 (중복)", key="cetus") is False and coord.pending() == []
    coord.now += 2.0
    assert coord.notify("시터스 밤", key="cetus") is True and len(coord.pending()) == 1
    for i in range(NotificationCoordinator.MAX_QUEUE - 1):
        assert coord.notify(f"q{i}", P.LOW)
    assert coord.notify("overflow", P.LOW) is False


def test_click_runs_callback_once_and_advances_queue(coord):
    calls = []
    coord.notify(SpeechBubblePayload("클릭", on_click_action=lambda: calls.append(1)))
    coord.notify("다음")
    w = coord.current_widget
    left_click(w)
    left_click(w)   # a closing bubble must not fire twice
    assert calls == [1] and coord.current_payload.text == "클릭"
    w._fade.setCurrentTime(w._fade.duration())   # finish fade-out deterministically
    assert coord.current_payload.text == "다음"


def test_timer_lifecycle_hover_pause_and_sticky(coord):
    closed = []
    w = PetSpeechBubbleWidget("hover", duration_ms=3000)
    w.closed.connect(closed.append)
    w.show_bubble()
    w.enterEvent(QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    assert not w.dismiss_timer.isActive()
    w.leaveEvent(QEvent(QEvent.Type.Leave))
    assert w.dismiss_timer.isActive() and 0 < w.dismiss_timer.interval() <= 3000
    w.dismiss_timer.timeout.emit()   # expiry starts the fade-out
    assert closed == []
    w._fade.setCurrentTime(w._fade.duration())
    assert closed == [w] and not w.isVisible()
    sticky = PetSpeechBubbleWidget("sticky", duration_ms=0)
    sticky.show_bubble()
    assert not sticky.dismiss_timer.isActive()


def test_tail_paint_and_anchor_geometry(coord):
    w = PetSpeechBubbleWidget("tail")
    w.set_tail("bottom", 40)
    assert w.bubble_path().contains(QPointF(40, w.height() - TAIL_H / 2))
    w.set_tail("top", 200)
    assert w.bubble_path().contains(QPointF(200, TAIL_H / 2)) and not w.grab().isNull()
    screen, pet = QRect(0, 0, 1920, 1080), QRect(800, 600, 160, 180)
    pos, side, tail_x = compute_bubble_anchor(pet, 260, 60, screen)
    assert side == "bottom" and pos.y() + 60 <= 600 and pos.x() + tail_x == pet.center().x()
    pos, side, tail_x = compute_bubble_anchor(QRect(1840, 20, 160, 180), 260, 60, screen)
    assert side == "top" and pos.y() >= 200 and pos.x() + 260 <= 1920 and tail_x <= 242
    pet = type("FakePet", (), {"frameGeometry": lambda self: QRect(500, 500, 160, 180), "screen": lambda self: None})()
    coord.attach_pet(pet)
    coord.notify("펫 위")
    w = coord.current_widget
    assert w.y() + w.height() <= 500 and w.tail_side == "bottom" and w.x() + w.tail_x == 579
