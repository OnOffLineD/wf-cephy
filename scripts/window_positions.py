"""Last on-screen spot of the desktop pet and the chat popup, so both come back where the user left them.

Kept in its own git-ignored file under the user data folder: data/persona_config.json is tracked by git,
and a position written there would show up as a local change (which blocks app updates).
"""
import json
import os

from scripts.path_config import get_user_data_path, write_json_atomic

POSITIONS_FILE = "window_positions.json"
PET = "pet"
PANEL = "panel"


def _positions_path():
    return get_user_data_path(POSITIONS_FILE)


def _load_all():
    try:
        with open(_positions_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_all(data):
    path = _positions_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_json_atomic(path, data)
    except OSError as e:
        # Losing a remembered position is harmless; crashing a drag over it is not.
        print(f"[WARN] Could not save window position: {e}")


def _is_coord(value):
    return isinstance(value, int) and not isinstance(value, bool)


def load_position(key):
    """Saved (x, y) for `key`, or None when nothing usable was saved."""
    entry = _load_all().get(key)
    if not isinstance(entry, dict):
        return None
    x, y = entry.get("x"), entry.get("y")
    if _is_coord(x) and _is_coord(y):
        return x, y
    return None


def save_position(key, x, y):
    data = _load_all()
    data[key] = {"x": int(x), "y": int(y)}
    _write_all(data)


def forget_positions(*keys):
    data = _load_all()
    if not any(key in data for key in keys):
        return
    for key in keys:
        data.pop(key, None)
    _write_all(data)
