import json
import os

import pytest

try:
    from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtWidgets import QApplication
except ImportError:
    from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

from scripts import window_positions
from scripts.desktop_companion import DesktopPet, OrdisCompanionApp

LEFT = Qt.MouseButton.LeftButton
NO_BUTTON = Qt.MouseButton.NoButton


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def clean_positions():
    # The test session shares one user data folder: a position left behind would move other tests' windows.
    path = window_positions._positions_path()
    if os.path.exists(path):
        os.remove(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def panel(qapp, monkeypatch):
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    app = OrdisCompanionApp()
    yield app
    app.close()


def mouse(kind, global_pos, button, buttons):
    point = QPointF(global_pos)
    return QMouseEvent(kind, point, point, button, buttons, Qt.KeyboardModifier.NoModifier)


def drag(widget, start, end):
    widget.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, start, LEFT, LEFT))
    widget.mouseMoveEvent(mouse(QEvent.Type.MouseMove, end, NO_BUTTON, LEFT))
    widget.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, end, LEFT, NO_BUTTON))


def screen_rect():
    return QApplication.primaryScreen().geometry()


# --- store -------------------------------------------------------------------------------------------

def test_saved_position_round_trips_and_keys_are_independent(clean_positions):
    window_positions.save_position(window_positions.PET, 120, 340)
    window_positions.save_position(window_positions.PANEL, -1500, 20)

    assert window_positions.load_position(window_positions.PET) == (120, 340)
    assert window_positions.load_position(window_positions.PANEL) == (-1500, 20)
    with open(clean_positions, encoding="utf-8") as f:
        assert json.load(f) == {"pet": {"x": 120, "y": 340}, "panel": {"x": -1500, "y": 20}}

    window_positions.forget_positions(window_positions.PANEL)
    assert window_positions.load_position(window_positions.PANEL) is None
    assert window_positions.load_position(window_positions.PET) == (120, 340)


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"pet": {"x": "10", "y": 5}}', '{"pet": {"x": true, "y": 5}}', '{"pet": 3}'])
def test_unusable_saved_data_reads_as_no_position(clean_positions, content):
    with open(clean_positions, "w", encoding="utf-8") as f:
        f.write(content)
    assert window_positions.load_position(window_positions.PET) is None


def test_saving_over_a_corrupt_file_starts_fresh(clean_positions):
    with open(clean_positions, "w", encoding="utf-8") as f:
        f.write("{broken")
    window_positions.save_position(window_positions.PET, 1, 2)
    assert window_positions.load_position(window_positions.PET) == (1, 2)


def test_forgetting_without_a_file_does_not_create_one(clean_positions):
    window_positions.forget_positions(window_positions.PET, window_positions.PANEL)
    assert not os.path.exists(clean_positions)


# --- pet ---------------------------------------------------------------------------------------------

def test_pet_starts_at_home_without_a_saved_position(qapp):
    pet = DesktopPet()
    home = DesktopPet()
    home.move_to_home()
    assert pet.pos() == home.pos()


def test_pet_starts_where_it_was_left(qapp):
    window_positions.save_position(window_positions.PET, 100, 90)
    pet = DesktopPet()
    assert pet.pos() == QPoint(100, 90)


def test_pet_saved_off_every_screen_falls_back_to_home(qapp):
    # e.g. it was left on a second monitor that is now unplugged
    r = screen_rect()
    window_positions.save_position(window_positions.PET, r.right() + 5000, r.bottom() + 5000)
    pet = DesktopPet()
    home = DesktopPet()
    home.move_to_home()
    assert pet.pos() == home.pos()


def test_dragging_the_pet_saves_where_it_was_dropped(qapp):
    pet = DesktopPet()
    pet.move(200, 150)
    drag(pet, QPoint(210, 160), QPoint(260, 200))

    assert pet.pos() == QPoint(250, 190)
    assert window_positions.load_position(window_positions.PET) == (250, 190)


def test_clicking_the_pet_without_moving_saves_nothing(qapp, clean_positions):
    pet = DesktopPet()
    pet.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, QPoint(5, 5), LEFT, LEFT))
    pet.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, QPoint(5, 5), LEFT, NO_BUTTON))
    assert not os.path.exists(clean_positions)


def test_pet_position_reset_goes_home_forgets_it_and_tells_the_popup(qapp):
    window_positions.save_position(window_positions.PET, 100, 90)
    pet = DesktopPet()
    emitted = []
    pet.position_reset.connect(lambda: emitted.append(True))

    pet.reset_position()

    home = DesktopPet()
    assert pet.pos() == home.pos()
    assert window_positions.load_position(window_positions.PET) is None
    assert emitted == [True]


# --- chat popup --------------------------------------------------------------------------------------

def test_popup_opens_above_the_pet_without_a_saved_position(panel):
    assert panel._user_moved is False


def test_popup_starts_where_it_was_left_and_stays_there_when_shown(qapp, monkeypatch):
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    window_positions.save_position(window_positions.PANEL, 40, 0)
    app = OrdisCompanionApp()
    try:
        assert app.pos() == QPoint(40, 0)
        assert app._user_moved is True
        app.animate_show(QRect(600, 400, 160, 180))
        app._on_show_finished()
        assert app.pos() == QPoint(40, 0)
    finally:
        app.close()


def test_popup_saved_off_every_screen_is_ignored(qapp, monkeypatch):
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    r = screen_rect()
    window_positions.save_position(window_positions.PANEL, r.left() - 9000, r.top())
    app = OrdisCompanionApp()
    try:
        assert app._user_moved is False
    finally:
        app.close()


def test_dragging_the_popup_saves_where_it_was_dropped(panel):
    panel.move(30, 20)
    drag(panel, QPoint(40, 30), QPoint(90, 60))

    assert panel.pos() == QPoint(80, 50)
    assert window_positions.load_position(window_positions.PANEL) == (80, 50)


def test_clicking_the_popup_without_moving_saves_nothing(panel, clean_positions):
    panel.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, QPoint(5, 5), LEFT, LEFT))
    panel.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, QPoint(5, 5), LEFT, NO_BUTTON))
    assert not os.path.exists(clean_positions)


def test_popup_position_reset_forgets_it_and_follows_the_pet_again(panel):
    window_positions.save_position(window_positions.PANEL, 40, 0)
    window_positions.save_position(window_positions.PET, 100, 90)
    panel._user_moved = True

    panel.reset_position()

    assert panel._user_moved is False
    assert window_positions.load_position(window_positions.PANEL) is None
    # The pet's own spot is the pet's business.
    assert window_positions.load_position(window_positions.PET) == (100, 90)
