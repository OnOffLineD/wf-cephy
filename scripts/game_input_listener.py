"""Zero-touch Warframe input listener: polls user32.GetAsyncKeyState only (no OpenProcess,
SendInput or hooks), and only while a window titled 'Warframe' is in the foreground."""
import ctypes

try:
    from PyQt6.QtCore import QObject, QTimer, pyqtSignal
except ImportError:
    from PySide6.QtCore import QObject, QTimer, Signal as pyqtSignal

VK_LBUTTON, VK_SPACE, VK_KEY_A, VK_KEY_D, VK_KEY_E, VK_KEY_S, VK_KEY_W = 0x01, 0x20, 0x41, 0x44, 0x45, 0x53, 0x57

# action_name -> virtual key
ACTION_KEYS = {"w": VK_KEY_W, "a": VK_KEY_A, "s": VK_KEY_S, "d": VK_KEY_D,
               "jump": VK_SPACE, "melee": VK_KEY_E, "shoot": VK_LBUTTON}


def _user32():
    return getattr(getattr(ctypes, "windll", None), "user32", None)  # None off Windows


def _get_async_key_state(vk: int) -> int:
    user32 = _user32()
    return user32.GetAsyncKeyState(vk) if user32 is not None else 0


def _get_foreground_title() -> str:
    user32 = _user32()
    if user32 is None:
        return ""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


class GameInputListener(QObject):
    motion_event_signal = pyqtSignal(str, bool)  # (action_name, is_down)

    def __init__(self, parent=None, interval_ms: int = 50, force_active_for_test: bool = False):
        super().__init__(parent)
        self.force_active_for_test = force_active_for_test
        self.paused = False
        self._held = {action: False for action in ACTION_KEYS}
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.poll)

    def start(self):
        self.timer.start()

    def pause(self):
        self.paused = True
        self._release_all()

    def resume(self):
        self.paused = False

    def is_game_active(self) -> bool:
        return self.force_active_for_test or "warframe" in _get_foreground_title().lower()

    def _release_all(self):
        # Let the pet settle back to rest instead of freezing mid-motion.
        for action, down in self._held.items():
            if down:
                self._held[action] = False
                self.motion_event_signal.emit(action, False)

    def poll(self):
        if self.paused:
            return
        if not self.is_game_active():
            self._release_all()
            return
        for action, vk in ACTION_KEYS.items():
            try:
                down = bool(_get_async_key_state(vk) & 0x8000)
            except Exception:
                down = False
            if down != self._held[action]:
                self._held[action] = down
                self.motion_event_signal.emit(action, down)
