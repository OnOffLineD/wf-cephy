import pytest

try:
    from PyQt6.QtCore import QThread
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication

import scripts.game_input_listener as gil
from scripts.game_input_listener import GameInputListener
from scripts.layered_pet_renderer import LayeredPetRenderer


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def pressed(monkeypatch):
    keys = set()
    # GetAsyncKeyState returns a SHORT; the high bit (negative value) means "down".
    monkeypatch.setattr(gil, "_get_async_key_state", lambda vk: -32768 if vk in keys else 0)
    return keys


def make_listener(**kw):
    lst = GameInputListener(**kw)
    lst.events = []
    lst.motion_event_signal.connect(lambda a, d: lst.events.append((a, d)))
    return lst


@pytest.mark.parametrize("vk,action", [
    (0x57, "w"), (0x41, "a"), (0x53, "s"), (0x44, "d"),
    (0x20, "jump"), (0x45, "melee"), (0x01, "shoot"),
])
def test_each_key_emits_down_then_up(qapp, pressed, vk, action):
    lst = make_listener(force_active_for_test=True)
    pressed.add(vk)
    lst.poll()
    lst.poll()  # still held: no repeat
    assert lst.events == [(action, True)]
    pressed.clear()
    lst.poll()
    assert lst.events == [(action, True), (action, False)]


def test_no_polling_when_warframe_not_foreground(qapp, pressed, monkeypatch):
    monkeypatch.setattr(gil, "_get_foreground_title", lambda: "Notepad")
    lst = make_listener()
    pressed.add(0x57)
    lst.poll()
    assert lst.events == []
    monkeypatch.setattr(gil, "_get_foreground_title", lambda: "Warframe")
    lst.poll()
    assert lst.events == [("w", True)]


def test_pause_releases_held_and_blocks_detection(qapp, pressed):
    lst = make_listener(force_active_for_test=True)
    pressed.add(0x44)
    lst.poll()
    lst.pause()
    pressed.add(0x20)
    lst.poll()
    assert lst.events == [("d", True), ("d", False)]
    lst.resume()
    lst.poll()
    assert set(lst.events[2:]) == {("d", True), ("jump", True)}


def test_chat_panel_show_pauses_and_hide_resumes(qapp, monkeypatch):
    from scripts.desktop_companion import OrdisCompanionApp
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    panel = OrdisCompanionApp()
    listener = GameInputListener(force_active_for_test=True)
    panel.pet = type("FakePet", (), {"input_listener": listener})()
    try:
        panel.animate_show()
        assert listener.paused is True
        panel.animate_hide()
        assert listener.paused is False
    finally:
        # Let the hide animation and show fail-safe timer finish so nothing leaks into later tests.
        for _ in range(60):
            qapp.processEvents()
            QThread.msleep(10)
        panel.close()


@pytest.mark.parametrize("action,attr,sign", [
    ("jump", "motion_offset_y", -1), ("melee", "motion_offset_rot", 1), ("shoot", "motion_offset_x", -1),
])
def test_impulse_kicks_then_settles_to_zero(qapp, action, attr, sign):
    r = LayeredPetRenderer()
    r.apply_motion_action(action, True)
    assert getattr(r, attr) * sign > 0
    for _ in range(60):
        r._on_bounce_tick()
    assert (r.motion_offset_x, r.motion_offset_y, r.motion_offset_rot) == (0, 0, 0)


def test_wasd_lean_holds_then_returns(qapp):
    r = LayeredPetRenderer()
    r.apply_motion_action("d", True)
    for _ in range(60):
        r._on_bounce_tick()
    assert r.motion_offset_x > 0
    r.apply_motion_action("d", False)
    for _ in range(60):
        r._on_bounce_tick()
    assert r.motion_offset_x == 0 and r.motion_offset_rot == 0
