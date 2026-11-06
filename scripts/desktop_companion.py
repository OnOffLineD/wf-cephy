try:
    import torch
except Exception:
    pass
import sys
import os
import re
import html
import threading
import traceback
from datetime import datetime
from PIL import Image, ImageGrab

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.path_config import get_path, get_user_data_path
from scripts.update_game_data import GameDataUpdater

try:
    from PyQt6.QtCore import (
        Qt, QPoint, QRect, QTimer, pyqtSignal, QEvent, QEventLoop,
        QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
    )
    from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor, QFont, QKeySequence, QCursor
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QTextEdit, QScrollArea, QFrame,
        QCheckBox, QMenu, QSplitter, QStackedWidget, QDialog, QInputDialog, QGridLayout
    )
except ImportError:
    from PySide6.QtCore import (
        Qt, QPoint, QRect, QTimer, Signal as pyqtSignal, QEvent, QEventLoop,
        QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
    )
    from PySide6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor, QFont, QKeySequence, QCursor
    from PySide6.QtWidgets import (
        QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QTextEdit, QScrollArea, QFrame,
        QCheckBox, QMenu, QSplitter, QStackedWidget, QDialog, QInputDialog, QGridLayout
    )

from scripts.llm_orchestrator import LLMOrchestrator
from scripts.world_state_tracker import WorldStateTracker
from scripts.screen_mod_analyzer import ScreenModAnalyzer
from scripts.innate_traits import BONUS_ELEMENTS, BONUS_MAX
from scripts.embedded_llm_runner import EmbeddedLLMRunner
from scripts.damage_breakdown_dialog import DamageBreakdownDialog
from scripts.riven_quick_dialog import RivenQuickInputDialog
from scripts.riven_compare_dialog import RivenCompareDialog, RivenRollEditDialog
from scripts.build_edit_dialog import BuildEditDialog
from scripts.morphing_tab_bar import MorphingTabBar
from scripts.hud_widgets import HudButton
from scripts.persona_dialog import OrdisPersonaDialog
from scripts.layered_pet_renderer import LayeredPetRenderer


def handle_uncaught_exception(exc_type, exc, tb, panel=None, log_path=None):
    """PyQt ends the whole app on an exception in a button handler, so log it and keep running instead."""
    details = "".join(traceback.format_exception(exc_type, exc, tb))
    sys.stderr.write(details)
    log_path = log_path or get_user_data_path('logs', 'app-errors.log')
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"--- {datetime.now().isoformat(timespec='seconds')}\n{details}\n")
    except OSError:
        pass
    if panel is not None:
        panel.chat_reply_signal.emit("세팔론 오디스", f"⚠️ 오류가 발생했지만 앱은 계속 실행 중입니다: {exc}\n로그: {log_path}", False, None)


def render_chat_markup(text: str) -> str:
    """Turn the small markdown subset used by Ordis reports into Qt rich text."""
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', escaped)
    escaped = re.sub(r'`([^`]+)`', r"<span style='color: #7dd3fc;'>\1</span>", escaped)
    return escaped.replace('\n', '<br>')


def qimage_to_pil(qimg) -> Image.Image:
    rgb = qimg.convertToFormat(qimg.Format.Format_RGB888)
    ptr = rgb.bits()
    ptr.setsize(rgb.sizeInBytes())
    # Qt pads rows to 4 bytes, so widths like 1366 need the real row length.
    return Image.frombuffer('RGB', (rgb.width(), rgb.height()), bytes(ptr), 'raw', 'RGB', rgb.bytesPerLine(), 1)

# -------------------------------------------------------------------------
# 1. Desktop Pet Floating Widget
# -------------------------------------------------------------------------
class DesktopPet(QWidget):
    clicked = pyqtSignal()
    open_persona_requested = pyqtSignal()

    def __init__(self, asset_dir=None):
        super().__init__()
        self.asset_dir = asset_dir or get_path("assets", "character")
        self.drag_pos = QPoint()
        self.init_ui()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.avatar = LayeredPetRenderer(asset_dir=self.asset_dir, parent=self)
        self.avatar.set_mood("idle")
        layout.addWidget(self.avatar)
        self.setLayout(layout)

        # Initial bottom-right placement
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 180, screen.height() - 220)

    def set_mood(self, mood="idle", intensity=1, vfx=None, secondary_mood=None):
        if hasattr(self.avatar, 'set_mood'):
            self.avatar.set_mood(mood, intensity=intensity, vfx=vfx, secondary_mood=secondary_mood)

    def start_talking(self, duration_ms: int = 0):
        if hasattr(self.avatar, 'start_talking'):
            self.avatar.start_talking(duration_ms=duration_ms)

    def stop_talking(self):
        if hasattr(self.avatar, 'stop_talking'):
            self.avatar.stop_talking()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)

    def mouseDoubleClickEvent(self, event):
        self.clicked.emit()

    def show_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background: #121622; color: #fff; border: 1px solid #00d2ff; padding: 5px; } QMenu::item:selected { background: #0088cc; }")
        open_act = menu.addAction("💬 오디스 메신저 열기")
        persona_act = menu.addAction("🎭 오디스 성격 설정...")
        reset_act = menu.addAction("📍 위치 초기화")
        exit_act = menu.addAction("❌ 종료")

        act = menu.exec(pos)
        if act == open_act:
            self.clicked.emit()
        elif act == persona_act:
            self.open_persona_requested.emit()
        elif act == reset_act:
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.width() - 180, screen.height() - 220)
        elif act == exit_act:
            QApplication.quit()


# -------------------------------------------------------------------------
# 3. KakaoTalk Style Message Bubble
# -------------------------------------------------------------------------
class ChatBubble(QWidget):
    def __init__(self, sender: str, text: str, is_user: bool = False, action_todo: str = None, on_add_todo = None):
        super().__init__()
        self.sender = sender
        self.text = text
        self.is_user = is_user
        self.action_todo = action_todo
        self.on_add_todo = on_add_todo
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(10, 4, 10, 4)

        time_str = datetime.now().strftime("%H:%M")
        time_lbl = QLabel(time_str)
        time_lbl.setStyleSheet("color: #64748b; font-size: 10px;")

        msg_box = QVBoxLayout()
        msg_lbl = QLabel(self.text if self.is_user else render_chat_markup(self.text))
        msg_lbl.setTextFormat(Qt.TextFormat.PlainText if self.is_user else Qt.TextFormat.RichText)
        msg_lbl.setWordWrap(True)
        msg_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if self.is_user:
            # User bubble: Warframe Gold/Yellow
            msg_lbl.setStyleSheet("""
                background-color: #D4AF37;
                color: #0d1117;
                padding: 10px 14px;
                border-radius: 12px;
                font-size: 13px;
                font-weight: 500;
            """)
            main_layout.addStretch()
            main_layout.addWidget(time_lbl, alignment=Qt.AlignmentFlag.AlignBottom)
            main_layout.addWidget(msg_lbl, alignment=Qt.AlignmentFlag.AlignRight)
        else:
            # Ordis bubble: Dark Orokin Blue with Cyan accent
            msg_lbl.setStyleSheet("""
                background-color: #172033;
                color: #e2e8f0;
                padding: 10px 14px;
                border: 1px solid #2a3a5a;
                border-radius: 12px;
                font-size: 13px;
                line-height: 1.4;
            """)
            avatar_lbl = QLabel()
            avatar_path = get_path("assets", "character", "idle.png")
            if os.path.exists(avatar_path):
                pix = QPixmap(avatar_path).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                avatar_lbl.setPixmap(pix)
            
            sender_lbl = QLabel(self.sender)
            sender_lbl.setStyleSheet("color: #00d2ff; font-weight: bold; font-size: 11px;")
            
            bubble_col = QVBoxLayout()
            bubble_col.addWidget(sender_lbl)
            bubble_col.addWidget(msg_lbl)

            self._setup_bubble_extras(msg_lbl, bubble_col)

            main_layout.addWidget(avatar_lbl, alignment=Qt.AlignmentFlag.AlignTop)
            main_layout.addLayout(bubble_col)
            main_layout.addWidget(time_lbl, alignment=Qt.AlignmentFlag.AlignBottom)
            main_layout.addStretch()

        self.setLayout(main_layout)

    def _setup_bubble_extras(self, msg_lbl, bubble_col):
            if isinstance(self.action_todo, str) and self.action_todo and self.on_add_todo:
                btn_todo = QPushButton(f'📌 {self.action_todo} 숙제에 바로 추가')
                btn_todo.setStyleSheet('QPushButton { background: #0088cc; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 11px; margin-top: 4px; } QPushButton:hover { background: #00aaff; }')
                btn_todo.clicked.connect(lambda: self._handle_add(btn_todo))
                bubble_col.addWidget(btn_todo)
            elif isinstance(self.action_todo, dict):
                if self.action_todo.get('is_thinking'):
                    self._dot_step = 0
                    self._base_think_text = self.text
                    self._think_timer = QTimer(self)
                    self._think_timer.timeout.connect(lambda: (setattr(self, '_dot_step', (self._dot_step % 3) + 1), msg_lbl.setText(self._base_think_text + ' ' + '.' * self._dot_step)))
                    self._think_timer.start(350)
                for label, callback, once in self.action_todo.get('buttons', []):
                    self._add_action_button(bubble_col, label, callback, once)
                if self.action_todo.get('button_grid'):
                    self._add_button_grid(bubble_col, self.action_todo['button_grid'])
                if self.action_todo.get('type') == 'MOD_REVIEW' and callable(self.action_todo.get('on_confirm')):
                    btn_conf = QPushButton('✅ 인식 일치 - 데미지 계산 실행')
                    btn_conf.setStyleSheet('QPushButton { background: #059669; color: white; padding: 8px 14px; border-radius: 6px; font-weight: bold; font-size: 12px; margin-top: 6px; } QPushButton:hover { background: #10b981; }')
                    cb_fn = self.action_todo['on_confirm']
                    btn_conf.clicked.connect(lambda: (btn_conf.setText('✅ 인식 확인 완료! 데미지 계산 완료'), btn_conf.setEnabled(False), cb_fn()))
                    bubble_col.addWidget(btn_conf)
                if self.action_todo.get('calculation_breakdown') and callable(self.action_todo.get('on_show_breakdown')):
                    btn_bd = QPushButton('📐 데미지 산출 근거 및 계산식 보기 (틱딜 포함)')
                    btn_bd.setStyleSheet('QPushButton { background: #1e293b; color: #D4AF37; border: 1px solid #D4AF37; padding: 7px 14px; border-radius: 6px; font-weight: bold; font-size: 12px; margin-top: 6px; } QPushButton:hover { background: #334155; }')
                    bd_txt = self.action_todo['calculation_breakdown']
                    bd_data = self.action_todo.get('breakdown_data')
                    bd_fn = self.action_todo['on_show_breakdown']
                    btn_bd.clicked.connect(lambda: bd_fn(bd_txt, bd_data))
                    bubble_col.addWidget(btn_bd)
                if self.action_todo.get('todo') and self.on_add_todo:
                    todo_val = self.action_todo['todo']
                    self.action_todo = todo_val
                    btn_todo = QPushButton(f'📌 {todo_val} 숙제에 바로 추가')
                    btn_todo.setStyleSheet('QPushButton { background: #0088cc; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold; font-size: 11px; margin-top: 4px; } QPushButton:hover { background: #00aaff; }')
                    btn_todo.clicked.connect(lambda: self._handle_add(btn_todo))
                    bubble_col.addWidget(btn_todo)
                if self.action_todo.get('has_pending_riven') and callable(self.action_todo.get('on_open_riven_dialog')):
                    btn_riven = QPushButton('⚡ 리벤 옵션 간편 입력 (2초)')
                    btn_riven.setStyleSheet('QPushButton { background: #4c1d95; color: white; border: 1px solid #f59e0b; padding: 8px 14px; border-radius: 6px; font-weight: bold; font-size: 12px; margin-top: 6px; } QPushButton:hover { background: #6d28d9; }')
                    riven_fn = self.action_todo['on_open_riven_dialog']
                    btn_riven.clicked.connect(riven_fn)
                    bubble_col.addWidget(btn_riven)

    def _add_action_button(self, bubble_col, label, callback, once):
        button = QPushButton(label)
        button.setStyleSheet('QPushButton { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 7px 14px; border-radius: 6px; font-weight: bold; font-size: 12px; margin-top: 4px; } QPushButton:hover { background: #334155; } QPushButton:disabled { color: #64748b; }')

        def on_click():
            if once:
                button.setEnabled(False)
            callback()

        button.clicked.connect(on_click)
        bubble_col.addWidget(button)

    def _add_button_grid(self, bubble_col, grid):
        """One choice from several short options, packed into rows so it doesn't take over the chat."""
        box = QWidget()
        layout = QGridLayout(box)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setHorizontalSpacing(4)
        layout.setVerticalSpacing(4)
        columns = max(1, int(grid.get('columns', 4)))
        row = 0
        if grid.get('title'):
            title = QLabel(grid['title'])
            title.setStyleSheet('color: #94a3b8; font-size: 11px; font-weight: bold;')
            layout.addWidget(title, 0, 0, 1, columns)
            row = 1
        buttons = []

        def choose(callback):
            # A choice is made once; the other options no longer apply.
            for b in buttons:
                b.setEnabled(False)
            callback()

        for i, (label, callback) in enumerate(grid.get('buttons', [])):
            button = QPushButton(label)
            button.setStyleSheet('QPushButton { background: #1e293b; color: #e2e8f0; border: 1px solid #334155; padding: 5px 4px; border-radius: 6px; font-weight: bold; font-size: 11px; } QPushButton:hover { background: #334155; } QPushButton:disabled { color: #64748b; }')
            button.clicked.connect(lambda _=False, cb=callback: choose(cb))
            buttons.append(button)
            layout.addWidget(button, row + i // columns, i % columns)
        bubble_col.addWidget(box)

    def _handle_add(self, btn):
        if self.on_add_todo and self.action_todo:
            self.on_add_todo(self.action_todo)
            btn.setText("✅ 숙제 등록 완료!")
            btn.setEnabled(False)
            btn.setStyleSheet("background: #2b3a4a; color: #8899aa; padding: 6px 12px; border-radius: 6px; font-size: 11px;")


# -------------------------------------------------------------------------
# 4. Main Companion Window (KakaoTalk Style + Side Checklist)
# -------------------------------------------------------------------------
class OrdisCompanionApp(QWidget):
    chat_reply_signal = pyqtSignal(str, str, bool, object)
    world_events_signal = pyqtSignal(str)
    world_events_done_signal = pyqtSignal()
    pet_update_signal = pyqtSignal(str, int, object, object, int)
    checklist_changed_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.llm_runner = EmbeddedLLMRunner()
        self.orchestrator = LLMOrchestrator()
        self.orchestrator.runner = self.llm_runner
        self.diagnoser = ScreenModAnalyzer()
        self.tracker = WorldStateTracker(name_translator=self._translate_game_name)
        self.orchestrator.diagnoser = self.diagnoser
        self.orchestrator.todo_tracker = self.tracker
        self.auto_todo_enabled = True
        self.init_ui()
        self.chat_reply_signal.connect(self.add_chat_bubble)
        self.checklist_changed_signal.connect(self.refresh_checklist_ui)
        self.world_events_signal.connect(self.lbl_events.setText)
        self.pet_update_signal.connect(self._apply_pet_update)
        self.setup_global_hotkeys()

    def _translate_game_name(self, name: str) -> str:
        meta = self.diagnoser.indexer.weapons_index.get(name.lower()) or {}
        return meta.get("kr_name") or name

    def check_game_data_in_background(self):
        # Only announces: new stats change damage results, so applying them stays the user's call.
        def check():
            updater = GameDataUpdater()
            try:
                if updater.due_for_check() and updater.check()['has_update']:
                    self.chat_reply_signal.emit("세팔론 오디스", "오퍼레이터님, 새 게임 데이터가 공개되었습니다. `/데이터 갱신`이라고 입력하시면 받아 오겠습니다.", False, None)
            except Exception as e:
                print(f"[WARN] Game data check failed: {e}")

        threading.Thread(target=check, daemon=True).start()

    def start_llm_in_background(self):
        # Can download a 3GB model on first run, so it must never block the UI thread.
        def start():
            if self.llm_runner.start_server(wait_ready=True):
                self.chat_reply_signal.emit("세팔론 오디스", "✅ 대화 엔진 준비가 끝났습니다, 오퍼레이터님!", False, None)
                return
            reason = self.llm_runner.last_error or "알 수 없는 오류"
            self.chat_reply_signal.emit(
                "세팔론 오디스",
                f"⚠️ 로컬 LLM을 시작하지 못했습니다. 모딩 진단은 그대로 쓸 수 있지만 대화와 공략 답변은 제한됩니다.\n사유: {reason}",
                False,
                None
            )

        threading.Thread(target=start, daemon=True).start()

    def _apply_pet_update(self, mood, intensity, vfx, secondary_mood, talk_ms):
        pet = getattr(self, 'pet', None)
        if not pet:
            return
        pet.set_mood(mood, intensity=intensity, vfx=vfx, secondary_mood=secondary_mood)
        pet.start_talking(duration_ms=talk_ms)

    def init_ui(self):
            self.setWindowTitle("WF-Companion: Cephalon Ordis Messenger")
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setWindowOpacity(0.94)
            self.resize(440, 600)

            root_layout = QVBoxLayout(self)
            root_layout.setContentsMargins(10, 10, 10, 10)

            main_frame = QFrame()
            main_frame.setObjectName('cardFrame')
            main_frame.setStyleSheet("""
                QFrame#cardFrame {
                    background-color: rgba(12, 16, 23, 0.88);
                    border: 1.5px solid rgba(0, 210, 255, 0.35);
                    border-radius: 20px;
                }
            """)
            main_layout = QVBoxLayout(main_frame)
            main_layout.setContentsMargins(14, 12, 14, 14)
            main_layout.setSpacing(8)

            # Header
            header = QFrame()
            header.setStyleSheet("background: transparent; border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding: 8px;")
            h_layout = QHBoxLayout(header)
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(0)

            # Morphing Tab Bar
            self.tab_bar = MorphingTabBar(self)
            self.tab_bar.add_tab('채팅', icon_name='chat')
            self.tab_bar.add_tab('숙제', icon_name='todo')
            self.tab_bar.add_tab('현황', icon_name='status')
            self.tab_bar.tab_changed.connect(self.switch_tab)
            h_layout.addWidget(self.tab_bar)
            h_layout.addStretch()
            h_layout.setSpacing(6)

            # Persona Button
            self.persona_btn = persona_btn = HudButton('', icon_name='persona', icon_only=True)
            persona_btn.setToolTip("오디스 성격 및 페르소나 설정")
            persona_btn.clicked.connect(self.open_persona_dialog)
            h_layout.addWidget(persona_btn)

            # Close Button
            self.close_btn = close_btn = HudButton('', icon_name='close', icon_only=True)
            close_btn.setToolTip("닫기")
            close_btn.clicked.connect(self.animate_hide)
            h_layout.addWidget(close_btn)

            main_layout.addWidget(header)

            # Tab Stack
            self.tab_stack = QStackedWidget()
            main_layout.addWidget(self.tab_stack)

            # Chat Page (Tab 0)
            chat_page = QWidget()
            chat_layout = QVBoxLayout(chat_page)
            chat_layout.setContentsMargins(0, 0, 0, 0)
            chat_layout.setSpacing(0)

            # Chat Messages Scroll Area
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.chat_content = QWidget()
            self.chat_content.setStyleSheet("background: transparent;")
            self.chat_list_layout = QVBoxLayout(self.chat_content)
            self.chat_list_layout.addStretch()
            self.scroll_area.setWidget(self.chat_content)

            # Quick Action Toolbar
            action_bar = QHBoxLayout()
            action_bar.setContentsMargins(0, 6, 0, 6)
            action_bar.setSpacing(6)
            self.btn_full = HudButton('화면 캡처 [F9]', icon_name='capture', icon_only=True)
            self.btn_full.clicked.connect(self.capture_fullscreen_and_analyze)
            self.btn_clip = HudButton('붙여넣기 [Ctrl+V]', icon_name='clipboard', icon_only=True)
            self.btn_clip.clicked.connect(self.analyze_clipboard)
            self.btn_refresh = HudButton('실시간 갱신', icon_name='refresh', icon_only=True)
            self.btn_refresh.clicked.connect(self.refresh_world_events)
            self.world_events_done_signal.connect(lambda: self.btn_refresh.set_busy(False))

            action_bar.addWidget(self.btn_full)
            action_bar.addWidget(self.btn_clip)
            action_bar.addWidget(self.btn_refresh)
            action_bar.addStretch()

            # Input Area
            input_bar = QHBoxLayout()
            self.input_edit = QLineEdit()
            self.input_edit.setPlaceholderText("오디스에게 말을 걸거나 질문해 보세요... ('야 피곤해', '오버가드 약점')")
            self.input_edit.returnPressed.connect(self.send_user_message)
            self.input_edit.installEventFilter(self)
            self.btn_send = HudButton('전송', icon_name='send', icon_only=False)
            self.btn_send.clicked.connect(self.send_user_message)
            input_bar.addWidget(self.input_edit)
            input_bar.addWidget(self.btn_send)

            chat_layout.addWidget(self.scroll_area)
            chat_layout.addLayout(action_bar)
            chat_layout.addLayout(input_bar)

            self.tab_stack.addWidget(chat_page)

            # Todo Page (Tab 1)
            todo_page = QWidget()
            todo_layout = QVBoxLayout(todo_page)
            todo_layout.setContentsMargins(0, 0, 0, 0)
            todo_layout.setSpacing(0)

            # Auto-todo detection toggle
            self.cb_auto_detect = QCheckBox("대화 중 숙제 자동 감지")
            self.cb_auto_detect.setChecked(True)
            self.cb_auto_detect.stateChanged.connect(lambda s: setattr(self, 'auto_todo_enabled', bool(s)))
            todo_layout.addWidget(self.cb_auto_detect)

            # Checklist Scroll
            self.todo_scroll = QScrollArea()
            self.todo_scroll.setWidgetResizable(True)
            self.todo_content = QWidget()
            self.todo_content.setStyleSheet("background: transparent;")
            self.todo_layout = QVBoxLayout(self.todo_content)
            self.todo_layout.setContentsMargins(0, 0, 0, 0)
            self.todo_scroll.setWidget(self.todo_content)
            todo_layout.addWidget(self.todo_scroll)

            # Add custom task input
            add_box = QHBoxLayout()
            self.custom_todo_edit = QLineEdit()
            self.custom_todo_edit.setPlaceholderText("새 숙제 입력...")
            self.custom_todo_edit.returnPressed.connect(self.add_custom_task)
            btn_add = QPushButton("+")
            btn_add.setFixedWidth(30)
            btn_add.clicked.connect(self.add_custom_task)
            add_box.addWidget(self.custom_todo_edit)
            add_box.addWidget(btn_add)
            todo_layout.addLayout(add_box)

            self.tab_stack.addWidget(todo_page)

            # Game Status Page (Tab 2)
            status_page = QWidget()
            status_layout = QVBoxLayout(status_page)
            status_layout.setContentsMargins(4, 4, 4, 4)
            status_layout.setSpacing(6)
            status_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            # Top bar header with title and refresh button
            status_header = QWidget()
            sh_layout = QHBoxLayout(status_header)
            sh_layout.setContentsMargins(4, 4, 4, 4)
            title_lbl = QLabel("성계 실시간 현황")
            title_lbl.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 13px;")
            self.refresh_btn = refresh_btn = HudButton('새로고침', icon_name='refresh', icon_only=True)
            refresh_btn.clicked.connect(self.refresh_world_events)
            sh_layout.addWidget(title_lbl)
            sh_layout.addStretch()
            sh_layout.addWidget(refresh_btn)
            status_layout.addWidget(status_header)

            # Scroll Area with Events aligned to top
            status_scroll = QScrollArea()
            status_scroll.setWidgetResizable(True)
            status_scroll.setStyleSheet("background: transparent; border: none;")
            status_content = QWidget()
            sc_layout = QVBoxLayout(status_content)
            sc_layout.setContentsMargins(4, 4, 4, 4)
            sc_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            self.lbl_events = QLabel("실시간 이벤트 로딩 중...")
            self.lbl_events.setStyleSheet("""
                background: #111722;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 10px;
                font-size: 11px;
                color: #e2e8f0;
                line-height: 1.4;
            """)
            self.lbl_events.setWordWrap(True)
            sc_layout.addWidget(self.lbl_events)
            sc_layout.addStretch()
            status_scroll.setWidget(status_content)
            status_layout.addWidget(status_scroll)

            self.tab_stack.addWidget(status_page)

            # Set initial tab
            self.switch_tab(0)
            self.setLayout(root_layout)
            root_layout.addWidget(main_frame)

            # Initial Welcome Message
            self.add_chat_bubble(
                "세팔론 오디스",
                "오퍼레이터님! 오디스가 대기 중입니다. 공략이든 잡담이든 무엇이든 말씀해 주십시오! 모딩창을 캡처(F9 또는 Ctrl+V)해 주시면 현재 스펙의 화력과 고점/저점을 즉시 브리핑해 드립니다! 대화 엔진은 시작하는 데 1~2분 걸릴 수 있습니다.",
                is_user=False
            )

            # Refresh
            self.refresh_checklist_ui()
            QTimer.singleShot(400, self.refresh_world_events)
            self.world_timer = QTimer(self)
            self.world_timer.timeout.connect(self._refresh_world_events_if_visible)
            self.world_timer.start(60000)

    def _refresh_world_events_if_visible(self):
        if self.isVisible() and self.tab_stack.currentIndex() == 2:
            self.refresh_world_events()

    def add_chat_bubble(self, sender: str, text: str, is_user: bool = False, action_todo=None):
            is_thinking = isinstance(action_todo, dict) and bool(action_todo.get('is_thinking'))
        
            if not is_user and not is_thinking:
                prev_tb = getattr(self, '_thinking_bubble', None)
                if prev_tb is not None:
                    if hasattr(prev_tb, '_think_timer'):
                        prev_tb._think_timer.stop()
                    self.chat_list_layout.removeWidget(prev_tb)
                    prev_tb.deleteLater()
                    self._thinking_bubble = None
        
            bubble = ChatBubble(
                sender=sender,
                text=text,
                is_user=is_user,
                action_todo=action_todo,
                on_add_todo=self.on_smart_add_todo
            )
            self.chat_list_layout.addWidget(bubble)
        
            if is_thinking:
                self._thinking_bubble = bubble
        
            QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            ))

    def send_user_message(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        self.add_chat_bubble("오퍼레이터", text, is_user=True)
        QApplication.processEvents()

        if text in ('/성격', '/페르소나', '/persona', '성격 설정', '페르소나 설정'):
            self.open_persona_dialog()
            return

        # Process chat todo command
        cmd_res = self.tracker.process_chat_todo_command(text)
        if cmd_res is not None:
            self.refresh_checklist_ui()
            self.add_chat_bubble('세팔론 오디스', cmd_res['message'], is_user=False)
            return

        # Handle pending mod review confirmation
        pending_review = getattr(self, '_pending_mod_review', None)
        self._pending_mod_review = None
        if pending_review is not None and text in ('계산', '맞아', 'ㅇㅇ', '확인', '네', '응', '진행'):
            self.on_confirm_mod_review(pending_review)
            return

        # Check smart todo detection
        detected_todo = self.tracker.detect_todo_intent(text) if self.auto_todo_enabled else None

        # Trigger thinking animation on pet
        if hasattr(self, 'pet') and self.pet and hasattr(self.pet, 'set_mood'):
            self.pet.set_mood('thinking')

        # Show animated thinking bubble
        self.add_chat_bubble('세팔론 오디스', '💭 세팔론 오디스가 생각 중입니다', is_user=False, action_todo={'is_thinking': True})
        QApplication.processEvents()

        # Get response from LLMOrchestrator in a background thread
        def get_response():
            try:
                res = self.orchestrator.chat(text)
                reply_text = res.get("report", "응답을 생성하지 못했습니다.")
                mood = res.get("mood", "idle")
                intensity = res.get("intensity", 1)
                vfx = res.get("vfx")
                sec_mood = res.get("secondary_mood")

                # Widgets may only be touched on the UI thread.
                self.pet_update_signal.emit(mood, intensity, vfx, sec_mood, min(4500, max(1500, len(reply_text) * 45)))

                action_obj = detected_todo
                if res.get('type') == 'DIAGNOSIS_CLARIFIED' and res.get('data', {}).get('w_meta'):
                    # The weapon name came from chat, so this scan can now be reviewed and saved.
                    self._pending_mod_review = res['data']
                    self.chat_reply_signal.emit("세팔론 오디스", res['data'].get('review_message', reply_text), False, self._review_action(res['data']))
                    return
                if res.get('type') == 'TODO_DONE':
                    self.checklist_changed_signal.emit()
                    action_obj = None
                if res.get('type') == 'TODO_CONFIRM':
                    action_obj = self._todo_confirm_action(res)
                if res.get('type') == 'BUILD_DELETE_CONFIRM':
                    action_obj = {'buttons': [('🗑️ 삭제', lambda w=res['weapon']: self._delete_build(w), True)]}
                if res.get('type') == 'RIVEN_CLARIFIED':
                    self._pending_mod_review = None
                    bd = res.get('data', {}).get('calculation_breakdown')
                    if bd:
                        action_obj = {'calculation_breakdown': bd, 'on_show_breakdown': self.on_show_calculation_breakdown, 'breakdown_data': res.get('data', {})}
                self.chat_reply_signal.emit("세팔론 오디스", reply_text, False, action_obj)
            except Exception as e:
                self.chat_reply_signal.emit("세팔론 오디스", f"글리치 발생: {e}", False, None)

        threading.Thread(target=get_response, daemon=True).start()

    def _todo_confirm_action(self, res):
        if res.get('tool') == 'delete_todo':
            return {'buttons': [('🗑️ 삭제', lambda i=res['item_id'], t=res['task']: self._delete_todo(i, t), True)]}
        # The existing add button: one click adds it and marks itself done.
        return {'todo': res['task']}

    def _delete_todo(self, item_id: str, task: str):
        self.tracker.delete_item(item_id)
        self.refresh_checklist_ui()
        self.add_chat_bubble('세팔론 오디스', f"🗑️ [{task}] 항목을 숙제 목록에서 삭제했습니다.", is_user=False)

    def on_smart_add_todo(self, task_text: str):
        self.tracker.add_custom_item(task_text)
        self.refresh_checklist_ui()

    def add_custom_task(self):
        txt = self.custom_todo_edit.text().strip()
        if txt:
            self.tracker.add_custom_item(txt)
            self.custom_todo_edit.clear()
            self.refresh_checklist_ui()

    def analyze_clipboard(self):
        img = ImageGrab.grabclipboard()
        if img:
            self.process_screen_image(img)
        else:
            self.add_chat_bubble("세팔론 오디스", "오퍼레이터님, 클립보드에 복사된 이미지가 없습니다! Win+Shift+S로 캡처한 뒤 다시 눌러주십시오.", is_user=False)

    def process_screen_image(self, img):
            self.show()
            self.add_chat_bubble("오퍼레이터", "📷 [모딩 스크린샷 전송 완료]", is_user=True)
            self.add_chat_bubble("세팔론 오디스", "💭 오디스가 스크린샷의 무기명과 모드 슬롯을 광학 분석 중입니다", is_user=False, action_todo={'is_thinking': True})
            QApplication.processEvents()

            def diagnose_in_background():
                try:
                    res = self.diagnoser.diagnose_screenshot(img)
                    if res.get('is_riven_compare'):
                        self.chat_reply_signal.emit("세팔론 오디스", res['message'], False, self._riven_compare_action(res))
                    elif res.get('is_riven_report'):
                        bd = res.get('calculation_breakdown')
                        act = {'calculation_breakdown': bd, 'on_show_breakdown': self.on_show_calculation_breakdown, 'breakdown_data': res} if bd else None
                        self.chat_reply_signal.emit("세팔론 오디스", res.get('message', '분석 완료'), False, act)
                    elif res.get('review_message'):
                        self._pending_mod_review = res
                        self.chat_reply_signal.emit('세팔론 오디스', res['review_message'], False, self._review_action(res))
                    else:
                        self.chat_reply_signal.emit("세팔론 오디스", res.get('message', '분석 완료'), False, self._result_action(res))
                except Exception as e:
                    self.chat_reply_signal.emit("세팔론 오디스", f"오류 발생: {str(e)}", False, None)

            threading.Thread(target=diagnose_in_background, daemon=True).start()

    def _review_action(self, res):
        action = {
            'type': 'MOD_REVIEW',
            'on_confirm': lambda r=res: self.on_confirm_mod_review(r),
            'buttons': [('✏️ 슬롯 수정', lambda r=res: self.open_build_editor(r), False)],
        }
        if res.get('needs_bonus_element'):
            # Most players fuse the bonus to the 60% cap; any other value is typed in chat.
            action['button_grid'] = {
                # The question above already says other values go in chat ("자성 45").
                'title': f"🧪 보너스 속성 ({BONUS_MAX * 100:g}%)",
                'columns': 4,
                'buttons': [(kr, lambda r=res, el=el: self._set_bonus_element(r, el, BONUS_MAX)) for el, kr in BONUS_ELEMENTS.items()],
            }
        if res.get('has_pending_riven') or self.diagnoser.has_pending_riven():
            action['has_pending_riven'] = True
            action['on_open_riven_dialog'] = self.open_riven_quick_dialog
        return action

    def open_build_editor(self, res):
        w_meta = res['w_meta']
        dialog = BuildEditDialog(
            self.diagnoser.result_slots(res),
            self.diagnoser.mod_choices(w_meta),
            arcane=((res.get('metrics') or {}).get('arcane') or {}).get('name'),
            arcane_choices=self.diagnoser.arcane_choices(w_meta),
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.diagnoser.apply_slot_edits(res, dialog.get_edits())
        self._pending_mod_review = res
        self.add_chat_bubble('세팔론 오디스', res['review_message'], is_user=False, action_todo=self._review_action(res))

    def _riven_compare_action(self, res):
        if res.get('needs_slot_choice'):
            return {'buttons': [('🔧 뺄 모드 고르기', lambda r=res: self._choose_riven_slot(r), False)]}
        buttons = [
            ('📊 상세 비교', lambda r=res: RivenCompareDialog(r, parent=self).exec(), False),
            ('✏️ 옵션 수정', lambda r=res: self._edit_riven_rolls(r), False),
        ]
        if res.get('has_build'):
            buttons.append(('💾 새 옵션 사용', lambda r=res: self._use_new_riven(r), True))
        return {'buttons': buttons}

    def _show_riven_compare(self, res):
        self.add_chat_bubble('세팔론 오디스', res['message'], is_user=False, action_todo=self._riven_compare_action(res))

    def _choose_riven_slot(self, res):
        labels = [mod for _, mod in res['choices']]
        chosen, accepted = QInputDialog.getItem(self, "리벤과 바꿀 모드", "뺄 모드를 고르세요", labels, 0, False)
        if accepted:
            slot = res['choices'][labels.index(chosen)][0]
            self._show_riven_compare(self.diagnoser.compare_riven_rolls(res['w_meta'], res['old_card'], res['new_card'], removed_slot=slot))

    def _edit_riven_rolls(self, res):
        dialog = RivenRollEditDialog(res['old_card']['stats'], res['new_card']['stats'], parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        old_card = dict(res['old_card'], stats=dialog.old_stats())
        new_card = dict(res['new_card'], stats=dialog.new_stats())
        self._show_riven_compare(self.diagnoser.compare_riven_rolls(res['w_meta'], old_card, new_card, removed_slot=res.get('removed_slot')))

    def _use_new_riven(self, res):
        self.add_chat_bubble('세팔론 오디스', self.diagnoser.adopt_new_riven(res), is_user=False)

    def _save_build_message(self, res):
        build = self.diagnoser.save_scanned_build(res)
        if build:
            weapon = res['w_meta'].get('kr_name') or res['w_meta']['name']
            return f"💾 {weapon} 빌드를 저장했습니다." + (" 입력하신 리벤 옵션도 함께 저장했습니다." if build.get('riven') else "")
        return "ℹ️ 무기를 확인하지 못해 빌드를 저장하지 않았습니다. 무기 이름을 알려 주시면 저장할 수 있습니다."

    def _delete_build(self, weapon):
        deleted = self.diagnoser.build_store.delete_build(weapon)
        self.add_chat_bubble('세팔론 오디스', f"🗑️ {weapon} 빌드를 삭제했습니다." if deleted else "이미 삭제된 빌드입니다.", is_user=False)

    def _result_action(self, res):
        action = {}
        if res.get('calculation_breakdown'):
            action.update({'calculation_breakdown': res['calculation_breakdown'], 'on_show_breakdown': self.on_show_calculation_breakdown, 'breakdown_data': res})
        if res.get('has_pending_riven') or self.diagnoser.has_pending_riven():
            action.update({'has_pending_riven': True, 'on_open_riven_dialog': self.open_riven_quick_dialog})
        return action or None

    def setup_global_hotkeys(self):
            import ctypes
            user32 = ctypes.windll.user32
            VK_MENU = 0x12  # Alt
            VK_W = 0x57     # W
            VK_Q = 0x51     # Q
            VK_F9 = 0x78    # F9
            VK_SNAPSHOT = 0x2C  # PrintScreen

            self._alt_w_down = False
            self._alt_q_down = False
            self._f9_down = False
            self._prt_down = False

            def check_hotkeys():
                try:
                    alt_down = (user32.GetAsyncKeyState(VK_MENU) & 0x8000) != 0
                    w_down = (user32.GetAsyncKeyState(VK_W) & 0x8000) != 0
                    q_down = (user32.GetAsyncKeyState(VK_Q) & 0x8000) != 0
                    f9_down = (user32.GetAsyncKeyState(VK_F9) & 0x8000) != 0
                    prt_down = (user32.GetAsyncKeyState(VK_SNAPSHOT) & 0x8000) != 0

                    if alt_down:
                        if w_down and not self._alt_w_down:
                            self._alt_w_down = True
                            self.setVisible(not self.isVisible())
                        elif not w_down:
                            self._alt_w_down = False

                        if q_down and not self._alt_q_down:
                            self._alt_q_down = True
                            self.capture_fullscreen_and_analyze()
                        elif not q_down:
                            self._alt_q_down = False

                    if f9_down and not self._f9_down:
                        self._f9_down = True
                        self.capture_fullscreen_and_analyze()
                    elif not f9_down:
                        self._f9_down = False

                    if prt_down and not self._prt_down:
                        self._prt_down = True
                        # Windows fills the clipboard shortly after the key press.
                        QTimer.singleShot(400, self.analyze_clipboard)
                    elif not prt_down:
                        self._prt_down = False
                except Exception:
                    pass

            self.hotkey_timer = QTimer(self)
            self.hotkey_timer.timeout.connect(check_hotkeys)
            self.hotkey_timer.start(100)

    def refresh_world_events(self):
            def fetch_and_update():
                try:
                    events_str = WorldStateTracker.format_world_events(self.tracker.fetch_live_events())
                    self.world_events_signal.emit(events_str)
                except Exception:
                    pass
                finally:
                    try:
                        self.world_events_done_signal.emit()
                    except (RuntimeError, AttributeError):
                        pass

            if hasattr(self, 'btn_refresh'):
                self.btn_refresh.set_busy(True)
            threading.Thread(target=fetch_and_update, daemon=True).start()

    def refresh_checklist_ui(self):
            while self.todo_layout.count():
                item = self.todo_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            self.todo_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            items = self.tracker.load_checklist()
            for it in items:
                row = QHBoxLayout()
                row.setContentsMargins(6, 4, 6, 4)
                is_done = it.get('done', False)
                cb = QCheckBox(it['text'])
                cb.setChecked(is_done)
                if is_done:
                    cb.setStyleSheet('QCheckBox { color: #64748b; font-size: 12px; text-decoration: line-through; } QCheckBox::indicator { width: 16px; height: 16px; border: 1.5px solid #00d2ff; border-radius: 4px; background: #00d2ff; }')
                else:
                    cb.setStyleSheet('QCheckBox { color: #e2e8f0; font-size: 12px; } QCheckBox::indicator { width: 16px; height: 16px; border: 1.5px solid #00d2ff; border-radius: 4px; background: #161e2e; } QCheckBox:hover { color: #38bdf8; }')
                cb.stateChanged.connect(lambda _, i_id=it['id']: (self.tracker.toggle_item(i_id), self.refresh_checklist_ui()))

                btn_del = QPushButton('×')
                btn_del.setFixedSize(20, 20)
                btn_del.setStyleSheet('QPushButton { background: transparent; color: #ef4444; font-size: 14px; font-weight: bold; border: none; padding: 0; } QPushButton:hover { color: #f87171; background: #26161c; border-radius: 4px; }')
                btn_del.clicked.connect(lambda _, i_id=it['id']: self.delete_task(i_id))

                row.addWidget(cb)
                row.addStretch()
                row.addWidget(btn_del)

                row_widget = QWidget()
                row_widget.setStyleSheet('background: rgba(22, 30, 46, 0.7); border: 1px solid #1e293b; border-radius: 8px; margin-bottom: 4px;')
                row_widget.setLayout(row)
                self.todo_layout.addWidget(row_widget)

            self.todo_layout.addStretch()

    def delete_task(self, item_id):
        self.tracker.delete_item(item_id)
        self.refresh_checklist_ui()

    def _set_bonus_element(self, res, element: str, fraction: float):
        self.diagnoser.apply_bonus_element(res, element, fraction)
        self._pending_mod_review = res
        self.add_chat_bubble('세팔론 오디스', res['review_message'], is_user=False, action_todo=self._review_action(res))

    def on_confirm_mod_review(self, res):
            self._pending_mod_review = None
            # The result is out now; a later "화염 60" is chat, not an answer to this scan.
            self.diagnoser.clear_pending_bonus()
            message = f"{res.get('message', '')}\n\n{self._save_build_message(res)}"
            self.add_chat_bubble('세팔론 오디스', message, is_user=False, action_todo=self._result_action(res))

    def on_show_calculation_breakdown(self, breakdown_text: str, breakdown_data=None):
        if not breakdown_text and not breakdown_data:
            return
        data = breakdown_data or {}
        dialog = DamageBreakdownDialog(
            parent=self,
            breakdown_text=breakdown_text,
            w_meta=data.get('w_meta'),
            mod_objs=data.get('mod_objs'),
            metrics=data.get('metrics'),
            riven_stats=data.get('riven_stats')
        )
        dialog.exec()

    def capture_fullscreen_and_analyze(self):
        if getattr(self, '_is_capturing', False):
            return
        self._is_capturing = True

        try:
            self.hide()
            pet_was_visible = False
            if hasattr(self, 'pet') and self.pet and self.pet.isVisible():
                pet_was_visible = True
                self.pet.hide()

            # Keep message loop pumping while Windows DWM completes window hiding & redraw
            loop = QEventLoop()
            QTimer.singleShot(280, loop.quit)
            loop.exec()

            # Native Qt monitor capture (respects active monitor and DPI)
            screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            img = None
            if screen:
                pixmap = screen.grabWindow(0)
                if pixmap and not pixmap.isNull():
                    img = qimage_to_pil(pixmap.toImage())

            if not img:
                try:
                    img = ImageGrab.grab(all_screens=True)
                except Exception:
                    img = ImageGrab.grab()

            if img:
                try:
                    img.save('last_fullscreen_capture.png')
                except Exception:
                    pass

            if pet_was_visible and hasattr(self, 'pet') and self.pet:
                self.pet.show()

            if img:
                self.show()
                self.raise_()
                self.activateWindow()
                self.process_screen_image(img)
        finally:
            self._is_capturing = False

    def eventFilter(self, obj, event):
        if obj == getattr(self, 'input_edit', None) and event.type() == QEvent.Type.KeyPress and event.matches(QKeySequence.StandardKey.Paste):
            mime_data = QApplication.clipboard().mimeData()
            if mime_data.hasImage():
                self.analyze_clipboard()
                return True
        return super().eventFilter(obj, event)

    def reposition_above_pet(self, pet_rect):
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        pet_x = pet_rect.x()
        pet_y = pet_rect.y()
        pet_width = pet_rect.width()
        pet_height = pet_rect.height()
    
        # Calculate the position directly above the pet, centered horizontally
        x = pet_x + (pet_width - self.width()) // 2
        y = pet_y - self.height() - 12
    
        # Clamp the position within the screen boundaries
        if x < screen_geometry.left():
            x = screen_geometry.left()
        elif x + self.width() > screen_geometry.right():
            x = screen_geometry.right() - self.width()
    
        if y < screen_geometry.top():
            y = screen_geometry.top()
        elif y + self.height() > screen_geometry.bottom():
            y = screen_geometry.bottom() - self.height()
    
        self.move(x, y)

    def switch_tab(self, index: int):
            self.tab_stack.setCurrentIndex(index)
            if hasattr(self, 'tab_bar') and self.tab_bar.active_index != index:
                self.tab_bar.switch_tab(index)
            if index == 1:
                self.refresh_checklist_ui()
            if index == 2:
                self.refresh_world_events()

    def animate_show(self, pet_rect=None):
        if hasattr(self, '_anim_group') and self._anim_group:
            self._anim_group.stop()
    
        if pet_rect is not None:
            self.reposition_above_pet(pet_rect)
    
        target_geo = self.geometry()
        start_geo = QRect(target_geo.x(), target_geo.y() + 24, target_geo.width(), target_geo.height())
        self.setGeometry(start_geo)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
    
        anim_opacity = QPropertyAnimation(self, b'windowOpacity')
        anim_opacity.setDuration(240)
        anim_opacity.setStartValue(0.0)
        anim_opacity.setEndValue(0.94)
        anim_opacity.setEasingCurve(QEasingCurve.Type.InQuad)
    
        anim_geo = QPropertyAnimation(self, b'geometry')
        anim_geo.setDuration(240)
        anim_geo.setStartValue(start_geo)
        anim_geo.setEndValue(target_geo)
        anim_geo.setEasingCurve(QEasingCurve.Type.InQuad)
    
        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(anim_opacity)
        self._anim_group.addAnimation(anim_geo)
        self._anim_group.start()

    def animate_hide(self):
        if hasattr(self, '_anim_group') and self._anim_group:
            self._anim_group.stop()
    
        curr_geo = self.geometry()
        end_geo = QRect(curr_geo.x(), curr_geo.y() + 24, curr_geo.width(), curr_geo.height())
    
        anim_opacity = QPropertyAnimation(self, b'windowOpacity')
        anim_opacity.setDuration(200)
        anim_opacity.setStartValue(self.windowOpacity())
        anim_opacity.setEndValue(0.0)
        anim_opacity.setEasingCurve(QEasingCurve.Type.InQuad)
    
        anim_geo = QPropertyAnimation(self, b'geometry')
        anim_geo.setDuration(200)
        anim_geo.setStartValue(curr_geo)
        anim_geo.setEndValue(end_geo)
        anim_geo.setEasingCurve(QEasingCurve.Type.InQuad)
    
        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(anim_opacity)
        self._anim_group.addAnimation(anim_geo)
    
        self._anim_group.finished.connect(lambda: self._on_animation_finished(curr_geo))
    
        self._anim_group.start()
    
    def _on_animation_finished(self, curr_geo):
        self.hide()
        self.setGeometry(curr_geo)
        self.setWindowOpacity(0.94)

    def open_persona_dialog(self):
        dlg = OrdisPersonaDialog(self.orchestrator.persona_manager, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            persona = self.orchestrator.persona_manager.get_active_persona()
            self.add_chat_bubble(
                "세팔론 오디스",
                f"오퍼레이터님! 오디스의 성격 모드가 [{persona.get('name', '설정 완료')}] 모드로 변경되었습니다!",
                is_user=False
            )

    def open_riven_quick_dialog(self):
        dlg = RivenQuickInputDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            stats = dlg.get_stats()
            if stats:
                res = self.diagnoser.resume_pending_riven(stats)
                msg = res.get('message', '')
                bd = res.get('calculation_breakdown')
                act = {
                    'calculation_breakdown': bd,
                    'on_show_breakdown': self.on_show_calculation_breakdown,
                    'breakdown_data': res
                } if bd else None
                self.add_chat_bubble('세팔론 오디스', msg, is_user=False, action_todo=act)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = OrdisCompanionApp()
    sys.excepthook = lambda *exc_info: handle_uncaught_exception(*exc_info, panel=panel)
    app.aboutToQuit.connect(panel.llm_runner.stop_server)
    panel.start_llm_in_background()
    panel.check_game_data_in_background()
    panel.show()
    sys.exit(app.exec())
