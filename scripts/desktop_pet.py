"""Speech-bubble anchor geometry for the Ordis DesktopPet (scripts/desktop_companion.py)."""
try:
    from PyQt6.QtCore import QPoint, QRect
except ImportError:
    from PySide6.QtCore import QPoint, QRect

BUBBLE_GAP = 4
TAIL_INSET = 18


def compute_bubble_anchor(pet_rect, bubble_w, bubble_h, screen_rect=None):
    """Bubble above the pet's head (below if no room) -> (top_left, 'bottom'|'top' tail side, tail_x)."""
    target_x = pet_rect.center().x()
    x, y, side = target_x - bubble_w // 2, pet_rect.top() - bubble_h - BUBBLE_GAP, "bottom"
    if screen_rect is not None:
        if y < screen_rect.top():
            y, side = pet_rect.bottom() + BUBBLE_GAP, "top"
        x = max(screen_rect.left(), min(x, screen_rect.right() - bubble_w + 1))
    return QPoint(x, y), side, max(TAIL_INSET, min(target_x - x, bubble_w - TAIL_INSET))


def pet_bubble_anchor(pet, bubble_w, bubble_h):
    screen = pet.screen() if hasattr(pet, "screen") else None
    screen_rect = screen.availableGeometry() if screen is not None else None
    return compute_bubble_anchor(QRect(pet.frameGeometry()), bubble_w, bubble_h, screen_rect)
