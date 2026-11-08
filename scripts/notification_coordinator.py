"""Global bubble queue: NotificationCoordinator.get_instance().notify("출격!", NotificationPriority.HIGH)
One bubble at a time, queued by priority then FIFO; HIGH/CRITICAL preempts (drops) LOW/NORMAL chatter."""
import heapq
import itertools
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Optional
from scripts.pet_speech_bubble import PetSpeechBubbleWidget

NotificationPriority = IntEnum("NotificationPriority", "LOW NORMAL HIGH CRITICAL", start=0)


@dataclass
class SpeechBubblePayload:
    text: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    duration_ms: int = 5000
    on_click_action: Optional[Callable[[], None]] = None
    key: Optional[str] = None   # debounce identity; defaults to text


class NotificationCoordinator:
    _instance = None
    MAX_QUEUE = 20

    def __init__(self, debounce_ms=1500, clock=time.monotonic):
        self.debounce_ms, self._clock = debounce_ms, clock
        self._queue, self._seq, self._last_accepted = [], itertools.count(), {}
        self.current_payload = self.current_widget = None
        self.anchor_provider = None   # (bubble_w, bubble_h) -> (QPoint, tail_side, tail_x)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        if cls._instance is not None:
            cls._instance.clear()
        cls._instance = None

    def attach_pet(self, pet):
        from scripts.desktop_pet import pet_bubble_anchor
        self.anchor_provider = lambda w, h: pet_bubble_anchor(pet, w, h)

    def pending(self):
        return [entry[2] for entry in sorted(self._queue)]

    def notify(self, text_or_payload, priority=NotificationPriority.NORMAL,
               duration_ms=5000, on_click_action=None, key=None):
        """Show or queue a bubble. Returns False when debounced or the queue is full."""
        payload = text_or_payload if isinstance(text_or_payload, SpeechBubblePayload) else \
            SpeechBubblePayload(str(text_or_payload), NotificationPriority(priority), duration_ms, on_click_action, key)
        dedupe, now = (payload.key if payload.key is not None else payload.text), self._clock()
        last = self._last_accepted.get(dedupe)
        if last is not None and (now - last) * 1000 < self.debounce_ms:
            return False
        current = self.current_payload
        preempt = current is not None and payload.priority >= NotificationPriority.HIGH > current.priority
        if current is not None and not preempt and len(self._queue) >= self.MAX_QUEUE:
            return False
        self._last_accepted[dedupe] = now
        if current is None or preempt:
            self._close_current()
            self._show(payload)
        else:
            heapq.heappush(self._queue, (-int(payload.priority), next(self._seq), payload))
        return True

    def clear(self):
        self._queue.clear()
        self._close_current()

    def _close_current(self):
        widget, self.current_widget, self.current_payload = self.current_widget, None, None
        if widget is not None:
            widget.dismiss(animate=False)

    def _show(self, payload):
        widget = PetSpeechBubbleWidget(payload.text, payload.duration_ms, payload.on_click_action)
        self.current_payload, self.current_widget = payload, widget
        widget.closed.connect(self._on_bubble_closed)
        if self.anchor_provider is not None:
            try:
                pos, side, tail_x = self.anchor_provider(widget.width(), widget.height())
                widget.set_tail(side, tail_x)
                widget.move(pos)
            except Exception:
                pass   # a missing/destroyed pet must not block the notice
        widget.show_bubble()

    def _on_bubble_closed(self, widget):
        if widget is not self.current_widget:
            return   # preempted/cleared bubble finishing its close
        self.current_widget = self.current_payload = None
        if self._queue:
            self._show(heapq.heappop(self._queue)[2])
