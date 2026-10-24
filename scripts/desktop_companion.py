try:
    import torch
except Exception:
    pass
import sys
import os
import re
import threading
from datetime import datetime
from PIL import Image, ImageGrab

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.path_config import get_path

try:
    from PyQt6.QtCore import (
        Qt, QPoint, QRect, QTimer, pyqtSignal, QEvent, QEventLoop,
        QPropertyAnimation, QEasingCurve, QParallelAnimationGroup
    )
    from PyQt6.QtGui import QPixmap, QIcon, QPainter, QPen, QColor, QFont, QKeySequence, QCursor
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QTextEdit, QScrollArea, QFrame,
        QCheckBox, QMenu, QSplitter, QStackedWidget, QDialog
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
        QCheckBox, QMenu, QSplitter, QStackedWidget, QDialog
    )

from scripts.llm_orchestrator import LLMOrchestrator
from scripts.world_state_tracker import WorldStateTracker
from scripts.screen_mod_analyzer import ScreenModAnalyzer
from scripts.embedded_llm_runner import EmbeddedLLMRunner
from scripts.damage_breakdown_dialog import DamageBreakdownDialog
from scripts.riven_quick_dialog import RivenQuickInputDialog
from scripts.morphing_tab_bar import MorphingTabBar
from scripts.persona_dialog import OrdisPersonaDialog

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
        self.avatar = QLabel()
        self.set_mood("idle")
        layout.addWidget(self.avatar)
        self.setLayout(layout)

        # Initial bottom-right placement
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 180, screen.height() - 220)

    def set_mood(self, mood="idle"):
        fpath = os.path.join(self.asset_dir, f"{mood}.png")
        if os.path.exists(fpath):
            pix = QPixmap(fpath).scaled(130, 130, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.avatar.setPixmap(pix)

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
        msg_lbl = QLabel(self.text)
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

    def __init__(self):
        super().__init__()
        self.llm_runner = EmbeddedLLMRunner()
        if not self.llm_runner.is_healthy():
            threading.Thread(target=self.llm_runner.start_server, kwargs={"wait_ready": False}, daemon=True).start()
        self.orchestrator = LLMOrchestrator()
        self.orchestrator.runner = self.llm_runner
        self.tracker = WorldStateTracker()
        self.diagnoser = ScreenModAnalyzer()
        self.orchestrator.diagnoser = self.diagnoser
        self.auto_todo_enabled = True
        self.init_ui()
        self.chat_reply_signal.connect(self.add_chat_bubble)
        self.world_events_signal.connect(self.lbl_events.setText)
        self.setup_global_hotkeys()

    def closeEvent(self, event):
        try:
            if hasattr(self, 'llm_runner') and self.llm_runner:
                self.llm_runner.stop_server()
        except Exception:
            pass
        super().closeEvent(event)

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
            self.tab_bar.add_tab("💬 채팅")
            self.tab_bar.add_tab("📋 숙제")
            self.tab_bar.add_tab("🌍 현황")
            self.tab_bar.tab_changed.connect(self.switch_tab)
            h_layout.addWidget(self.tab_bar)
            h_layout.addStretch()

            # Persona Button
            persona_btn = QPushButton("🎭")
            persona_btn.setFixedSize(30, 30)
            persona_btn.setToolTip("오디스 성격 및 페르소나 설정")
            persona_btn.setStyleSheet("background: #111722; color: #38bdf8; border: 1px solid #1e293b; font-size: 13px; border-radius: 15px;")
            persona_btn.clicked.connect(self.open_persona_dialog)
            h_layout.addWidget(persona_btn)

            # Close Button
            close_btn = QPushButton("X")
            close_btn.setFixedSize(30, 30)
            close_btn.setStyleSheet("background: #111722; color: #e2e8f0; border: none; font-size: 12px; border-radius: 15px;")
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
            btn_full = QPushButton("🖥️ 화면 캡처 [F9]")
            btn_full.clicked.connect(self.capture_fullscreen_and_analyze)
            btn_clip = QPushButton("📋 붙여넣기 [Ctrl+V]")
            btn_clip.clicked.connect(self.analyze_clipboard)
            btn_refresh = QPushButton("🔄 실시간 갱신")
            btn_refresh.clicked.connect(self.refresh_world_events)

            action_bar.addWidget(btn_full)
            action_bar.addWidget(btn_clip)
            action_bar.addWidget(btn_refresh)
            action_bar.addStretch()

            # Input Area
            input_bar = QHBoxLayout()
            self.input_edit = QLineEdit()
            self.input_edit.setPlaceholderText("오디스에게 말을 걸거나 질문해 보세요... ('야 피곤해', '오버가드 약점')")
            self.input_edit.returnPressed.connect(self.send_user_message)
            self.input_edit.installEventFilter(self)
            btn_send = QPushButton("전송")
            btn_send.clicked.connect(self.send_user_message)
            input_bar.addWidget(self.input_edit)
            input_bar.addWidget(btn_send)

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
            title_lbl = QLabel("🌍 성계 실시간 현황")
            title_lbl.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 13px;")
            refresh_btn = QPushButton("🔄 새로고침")
            refresh_btn.setFixedHeight(28)
            refresh_btn.setStyleSheet("""
                QPushButton {
                    background: #1e293b; color: #38bdf8; border: 1px solid #334155;
                    border-radius: 6px; padding: 4px 10px; font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background: #334155; color: #ffffff; }
            """)
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
                "오퍼레이터님! 오디스가 대기 중입니다. 공략이든 잡담이든 무엇이든 말씀해 주십시오! 모딩창을 캡처(F9 또는 Ctrl+V)해 주시면 현재 스펙의 화력과 고점/저점을 즉시 브리핑해 드립니다!",
                is_user=False
            )

            # Refresh
            self.refresh_checklist_ui()
            QTimer.singleShot(400, self.refresh_world_events)

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
        if getattr(self, '_pending_mod_review', None) is not None and text in ('계산', '맞아', 'ㅇㅇ', '확인', '네', '응', '진행'):
            self.on_confirm_mod_review(self._pending_mod_review)
            return

        # Check smart todo detection
        detected_todo = self.tracker.detect_todo_intent(text) if self.auto_todo_enabled else None

        # Show animated thinking bubble
        self.add_chat_bubble('세팔론 오디스', '💭 세팔론 오디스가 생각 중입니다', is_user=False, action_todo={'is_thinking': True})
        QApplication.processEvents()

        # Get response from LLMOrchestrator in a background thread
        def get_response():
            try:
                res = self.orchestrator.chat(text)
                reply_text = res.get("report", "응답을 생성하지 못했습니다.")
                action_obj = detected_todo
                if res.get('type') == 'RIVEN_CLARIFIED':
                    self._pending_mod_review = None
                    bd = res.get('data', {}).get('calculation_breakdown')
                    if bd:
                        action_obj = {'calculation_breakdown': bd, 'on_show_breakdown': self.on_show_calculation_breakdown, 'breakdown_data': res.get('data', {})}
                self.chat_reply_signal.emit("세팔론 오디스", reply_text, False, action_obj)
            except Exception as e:
                self.chat_reply_signal.emit("세팔론 오디스", f"글리치 발생: {e}", False, None)

        threading.Thread(target=get_response, daemon=True).start()

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
                    if res.get('is_riven_report'):
                        bd = res.get('calculation_breakdown')
                        act = {'calculation_breakdown': bd, 'on_show_breakdown': self.on_show_calculation_breakdown, 'breakdown_data': res} if bd else None
                        self.chat_reply_signal.emit("세팔론 오디스", res.get('message', '분석 완료'), False, act)
                    elif res.get('review_message'):
                        action = {'type': 'MOD_REVIEW', 'on_confirm': lambda r=res: self.on_confirm_mod_review(r)}
                        if res.get('has_pending_riven') or self.diagnoser.has_pending_riven():
                            action['has_pending_riven'] = True
                            action['on_open_riven_dialog'] = self.open_riven_quick_dialog
                        self.chat_reply_signal.emit('세팔론 오디스', res['review_message'], False, action)
                    else:
                        bd = res.get('calculation_breakdown')
                        action = {'calculation_breakdown': bd, 'on_show_breakdown': self.on_show_calculation_breakdown, 'breakdown_data': res} if bd else None
                        if res.get('has_pending_riven') or self.diagnoser.has_pending_riven():
                            action['has_pending_riven'] = True
                            action['on_open_riven_dialog'] = self.open_riven_quick_dialog
                        self.chat_reply_signal.emit("세팔론 오디스", res.get('message', '분석 완료'), False, action)
                except Exception as e:
                    self.chat_reply_signal.emit("세팔론 오디스", f"오류 발생: {str(e)}", False, None)

            threading.Thread(target=diagnose_in_background, daemon=True).start()

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
                        self.analyze_clipboard()
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
                    ev = self.tracker.fetch_live_events()
                    if not ev:
                        raise ValueError("No data received from tracker")

                    cetus = ev.get("cetus", {})
                    duviri = ev.get("duviri", {})
                    sortie = ev.get("sortie", {})
                    archon = ev.get("archon", {})
                    incarnon = ev.get("incarnon", {})
                    void_trader = ev.get("void_trader", {})

                    txt = (
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"🌕 <b>아이돌론</b>: {cetus.get('state', 'N/A')} ({cetus.get('timeLeft', 'N/A')})<br>"
                        f"💡 팁: {cetus.get('huntingTip', 'N/A')}"
                        f"</div>"
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"🌀 <b>두비리</b>: {duviri.get('state', 'N/A')} 나선"
                        f"</div>"
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"⚔️ <b>출격</b>: {sortie.get('boss', 'N/A')} ({sortie.get('faction', 'N/A')})<br>"
                        f"👑 <b>집정관</b>: {archon.get('boss', 'N/A')}"
                        f"</div>"
                    )

                    if incarnon:
                        txt += (
                            f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                            f"🔮 <b>인카르논</b>: {incarnon.get('boss', 'N/A')} ({incarnon.get('location', 'N/A')})"
                            f"</div>"
                        )

                    if void_trader:
                        txt += (
                            f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                            f"📦 <b>바로 키티어</b>: {void_trader.get('status', 'N/A')}<br>"
                            f"📍 위치: {void_trader.get('location', 'N/A')}<br>"
                            f"⏰ ETA: {void_trader.get('eta', 'N/A')}"
                            f"</div>"
                        )

                except Exception as e:
                    txt = (
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"🌕 <b>아이돌론</b>: Day/Night estimated<br>"
                        f"💡 팁: N/A"
                        f"</div>"
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"🌀 <b>두비리</b>: N/A"
                        f"</div>"
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"⚔️ <b>출격</b>: Check sortie<br>"
                        f"👑 <b>집정관</b>: N/A"
                        f"</div>"
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"🔮 <b>인카르논</b>: N/A"
                        f"</div>"
                        f"<div style='background-color: #141c2b; border: 1px solid #233147; padding: 10px; margin-bottom: 10px;'>"
                        f"📦 <b>바로 키티어</b>: N/A<br>"
                        f"📍 위치: N/A<br>"
                        f"⏰ ETA: N/A"
                        f"</div>"
                    )

                self.world_events_signal.emit(txt)

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

    def on_confirm_mod_review(self, res):
            self._pending_mod_review = None
            msg = res.get('message', '')
            bd = res.get('calculation_breakdown', '')
            action_obj = {'calculation_breakdown': bd, 'on_show_breakdown': self.on_show_calculation_breakdown, 'breakdown_data': res} if bd else None
        
            if res.get('has_pending_riven') or self.diagnoser.has_pending_riven():
                action_obj['has_pending_riven'] = True
                action_obj['on_open_riven_dialog'] = self.open_riven_quick_dialog
        
            self.add_chat_bubble('세팔론 오디스', msg, is_user=False, action_todo=action_obj or None)

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
                    qimg = pixmap.toImage().convertToFormat(pixmap.toImage().Format.Format_RGB888)
                    ptr = qimg.bits()
                    ptr.setsize(qimg.sizeInBytes())
                    img = Image.frombuffer('RGB', (qimg.width(), qimg.height()), bytes(ptr), 'raw', 'RGB', 0, 1)

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
    app.aboutToQuit.connect(panel.llm_runner.stop_server)
    panel.show()
    sys.exit(app.exec())
