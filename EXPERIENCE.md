# Project Accumulated Experience Library (Harness² Recursion)

> 이 문서는 본 프로젝트의 개발, 디버깅, 검증 과정에서 도출된 에러와 검증된 해결책(Pattern & Lessons)을 누적하는 로컬 하네스 메모리입니다.  
> 기술 스택 공통 교훈은 `~/.gemini/config/skills/harness/GLOBAL_EXPERIENCE.md`를 상속합니다.

---

### EXP-001: Embedded Python과 시스템 Python 간 패키지 격리 및 Pytest 탐색 충돌 방지
- **기록일자**: 2026-10-22
- **현상**: 시스템 환경에서 pytest 구동 시 `python_embed/site-packages` 하위의 컴파일 바이너리(C-extension)를 재귀 탐색하여 `ImportError: cannot import name 'ArgsKwargs' from 'pydantic_core._pydantic_core'` 발생.
- **해결책**:
  - `pytest.ini`에 `testpaths = tests` 및 `norecursedirs = python_embed harness .git runs crops labeling weights debug_crops` 명시.
  - `scripts/probe.py`의 테스트 러너 인자에 `tests` 디렉토리를 명시적으로 바인딩하여 안전한 스모크/회귀 테스트 환경 구축.
- **교훈**: 휴대용(Embedded) 파이썬 런타임과 호스트 파이썬 환경이 공존하는 프로젝트에서는 테스트 도구의 재귀 경로 격리 설정이 필수적임.

---

### EXP-002: Windows 환경 한글 인코딩 및 파일 입출력 안전성
- **기록일자**: 2026-10-22
- **현상**: 모드 데이터 JSON 입출력 및 사용자 체크리스트 저장 시 CP949 인코딩으로 인한 문자 깨짐 발생 가능성.
- **해결책**:
  - 모든 파일 읽기/쓰기에 `encoding="utf-8"` 명시 선언.
  - JSON 덤프 시 `ensure_ascii=False` 설정.
- **교훈**: 다국어/한국어 지원 데스크톱 앱에서는 모든 파일 I/O 계층에 UTF-8을 일관되게 강제해야 함.

---

### EXP-003: Harness 초기 구축 및 3대 게이트 검증 연동
- **기록일자**: 2026-10-22
- **현상**: 새 프로젝트 환경에서 하네스 스캐폴딩 부재
- **해결책**:
  - 8대 하네스 컴포넌트 배포 및 probe.py 3대 게이트 러너 구성
- **교훈**: 자가 치유 및 지식 누적 시스템을 초기 단계에 정착시켜 회귀 결함 원천 차단

---

### EXP-004: 패널 총계와 위키 수식 대조
- **기록일자**: 2026-11-03
- **현상**: 모드 데이터가 상태이상·지면 강타 피해를 직접 피해로 합산하고 적 방어력에 Tenno 공식을 사용
- **해결책**:
  - 모드 스탯 정확 분류, 위키 수식 모듈 추가, 게임 패널 대조 테스트 고정
- **교훈**: 수식 검증은 단위 예제만이 아니라 실제 인게임 패널 값과 대조해야 한다

---

### EXP-005: 테스트가 실제 사용자 환경을 건드림
- **기록일자**: 2026-11-04
- **현상**: 테스트가 체크리스트 메타를 바꾸고, 실제 창을 띄우고, llama-server를 시작·강제 종료함
- **해결책**:
  - WF_USER_DATA_DIR와 offscreen을 conftest에서 고정하고, 앱 생성 시 서버를 자동 시작하지 않으며 이름 기반 강제 종료를 제거
- **교훈**: 앱 부작용은 생성자가 아니라 진입점에 두어야 테스트가 격리된다

---

### EXP-006: 계산식 보기 버튼 클릭 시 앱 종료
- **기록일자**: 2026-11-04
- **현상**: 리벤에 속성 옵션이 있으면 계산식 산출 보기에서 앱이 꺼짐. 리벤 행에 float를 그대로 넣어 QTableWidgetItem TypeError 발생, PyQt6는 슬롯의 미처리 예외로 프로세스를 종료함
- **해결책**:
  - 표 값은 모두 문자열로 포맷하고 리벤 값을 총합에 포함, 복사 버튼의 int 순회 수정, sys.excepthook으로 로그와 채팅 안내만 남기고 앱 유지
- **교훈**: PyQt6 앱은 excepthook을 직접 설치해야 슬롯 예외에 살아남는다. 재현 데이터는 옵션 종류별로 파라미터화해야 하며, 속성 없는 리벤만 시험하면 이 버그를 놓친다

---

### EXP-007: 긴 대화에서 공략 답변이 원문 나열로 바뀜
- **기록일자**: 2026-11-05
- **현상**: 대화가 몇 턴 쌓이면 프롬프트가 4096 토큰을 넘어 LLM 호출이 실패하고 위키 원문이 그대로 출력됨. 메모리가 공백 단어 수로 토큰을 세어 한국어를 크게 과소평가함
- **해결책**:
  - 메모리 토큰을 글자 수 x 0.6으로 계산하고, 프롬프트에 넣는 이전 답변을 240자로 제한하며 근거 줄을 제외
- **교훈**: 목 테스트로는 컨텍스트 초과가 드러나지 않는다. LLM 답변 변경은 실제 서버로 여러 턴을 이어서 확인해야 한다

---

### EXP-008: 자유 문장을 맡기면 모델이 근거 없는 조언을 지어냄
- **기록일자**: 2026-11-05
- **현상**: 드롭 표 답변의 도입부를 LLM에 맡기자 표에 없는 파밍 조언을 생성함
- **해결책**:
  - 드롭 답변은 고정 문장과 표로만 구성하고, 공략 답변은 자료에 없는 숫자가 든 줄을 제거하며 근거 문서를 표시
- **교훈**: 사실을 표로 답할 수 있으면 모델을 거치지 않는다. 다만 숫자 외의 잘못된 문장은 걸러내지 못하므로 소형 모델의 오독 위험은 남는다

### [2026-11-07] UI/UX 2도 HUD 글리프 및 고무줄 텐션 모핑 버튼 전면 도입 (T-UI-1 ~ T-UI-3)
- **발견/문제**:
  1. 기존 MorphingTabBar가 탭 전환 시 setStyleSheet로 볼드 폰트를 토글하면서 레이아웃 재계산 전에 geometry()를 읽어 인디케이터가 어긋나는 버그가 있었음.
  2. 버튼 텍스트에 유니코드 이모지('💬', '🖥️', '🎭' 등)가 직접 박혀 있어 디자인 품질이 낮고 시각적 통일성이 결여됨.
  3. Windows Frameless + WA_TranslucentBackground 환경에서는 무거운 QGraphicsEffect 대신 QPainter 직접 렌더링이 60fps를 유지하는 정석임.
  4. Worktree 디스패처 게이트에 3분 이상 걸리는 OCR 정확도 벤치마크(	est_ocr_benchmark.py)가 포함되어 있으면 빌더의 신속한 단위 검증을 방해하므로, 신속 게이트(probe.py)와 성능/데이터셋 벤치마크는 분리해야 함.
- **해결/규칙**:
  1. 나노 바나나(Gemini 2.5 Flash Image)로 2도(Neon Cyan #00e5ff + White) 텐노 글리프 8종을 생성하여 ssets/icons/에 128x128 투명 PNG로 배치.
  2. scripts/hud_widgets.py에 HudButton 구현: 기본 32px 콤팩트 알약 -> 호버 시 부드러운 너비 언폴딩 + 텐노 조준 브래킷('⌐ ¬') 페이드인 + 클릭 리플 + 비지 회전 호 연출.
  3. scripts/morphing_tab_bar.py에 고무줄 텐션 모핑(앞 테두리 190ms OutCubic, 뒤 테두리 310ms OutQuint) 도입 및 폰트 메트릭 사전 캐싱으로 지오메트리 불변화 달성.
  4. 컴패니언 앱(desktop_companion.py)의 7개 버튼 및 탭 바를 전면 교체하여 이모지 100% 제거 완료.


---

### EXP-009: 통합 설정창, GGUF/컨텍스트 동적 제어 및 전 팝업 프레임리스(헤드리스) 드래그 아키텍처
- **기록일자**: 2026-11-07
- **현상**:
  1. 기존 성격 설정창(OrdisPersonaDialog)이 성격 선택에 국한되어 있었고, 기본 OS 타이틀바가 노출되어 워프레임 다크 테마의 몰입감을 저해함.
  2. 사용자가 다른 GGUF 모델을 적용하거나 토큰 컨텍스트 길이(n_ctx)를 유동적으로 제어할 수 있는 GUI 인터페이스 부재.
  3. 메인 채팅 팝업 및 모든 서브 팝업 다이얼로그(계산식, 리벤 입력, 모드 수정, 전후 비교)를 마우스로 자유롭게 이동시킬 수 없었음.
- **해결책**:
  1. **설정창 통합 및 GGUF 모델/컨텍스트 동적 제어**: PersonaManager를 SettingsManager로 확장하여 모델 경로, 컨텍스트 길이(n_ctx), GPU 오프로드 레이어를 저장/관리. 설정 저장 시 모델/컨텍스트 변경을 감지하여 llama-server 백그라운드 핫 리로드 실행.
  2. **전 팝업 프레임리스(헤드리스) 드래그 모듈화**: scripts/frameless_dialog.py를 신설하여 FramelessWindowHint + WA_TranslucentBackground + 드래그 가능한 커스텀 타이틀바(헤더) 및 닫기 버튼을 모든 팝업에 일관되게 적용.
  3. **메인 채팅창 마우스 드래그 이동**: OrdisCompanionApp에 마우스 드래그 좌표 추적(_drag_pos) 및 사용자 이동 플래그(_user_moved)를 도입하여 헤더 및 여백 클릭 드래그로 자유롭게 이동 가능하도록 개선.
  4. **프로젝트 전용 고품질 UI 에셋 생성/적용**: scripts/generate_ui_assets.py로 2도 HUD 테마에 맞춘 ordis_logo.png(오디스 글리치 코어 로고), btn_save.png(저장 및 적용 아이콘), btn_cancel.png(취소 아이콘), settings.png(설정 아이콘)을 생성하여 적용.
- **교훈**:
  - 프레임리스 윈도우 환경에서는 마우스 이벤트를 자식 프레임(헤더, 카드 본체)에서도 윈도우로 전달해야 클릭 미스가 발생하지 않고 쾌적한 드래그 UX가 보장된다.
  - 모델/컨텍스트 설정 변경은 단순히 JSON을 쓰는 것에 그치지 않고 구동 중인 로컬 추론 프로세스의 graceful shutdown 및 자동 재기동 파이프라인과 긴밀하게 연동되어야 한다.


---

### EXP-010: 다이얼로그 계층의 FramelessDialog 정규 상속 일원화 및 레거시 뷰 청산
- **기록일자**: 2026-11-07
- **현상**:
  1. 여러 팝업 다이얼로그(DamageBreakdownDialog, RivenQuickInputDialog, BuildEditDialog, RivenCompareDialog, OrdisPersonaDialog)가 `apply_frameless_shell` 래핑 함수나 인라인 마우스 이벤트 보일러플레이트를 중복 정의하고 있어 유지보수성이 저하됨.
  2. `DamageBreakdownDialog`가 PyQt6 단독 임포트로 고정되어 있어 PySide6 환경과의 크로스 런타임 호환성이 취약했음.
  3. 미사용 레거시 파일(`scripts/companion_views.py`)이 잔존하여 지식 그래프 및 의존성 분석에 노이즈를 유발함.
- **해결책**:
  1. **정규 클래스 상속 일원화**: 모든 다이얼로그가 `FramelessDialog`를 직접 상속받고 `self.create_title_bar(...)`를 호출하도록 리팩토링.
  2. **테마 스타일 SSOT 정립**: `scripts/frameless_dialog.py` 내에 `FRAMELESS_DIALOG_STYLE`을 중앙 집중화하고 `setWindowTitle` 호출 시 헤더 라벨 자동 동기화 기능 추가.
  3. **PySide6 / PyQt6 크로스 임포트 통일**: `try...except ImportError` 패턴을 전 다이얼로그 모듈에 일관되게 적용.
  4. **레거시 코드 제거**: 참조되지 않는 `companion_views.py`를 영구 삭제하여 코드베이스를 슬림화함.
- **교훈**:
  - 몽키 패칭 형태의 데코레이터/래퍼 함수보다 명확한 베이스 클래스(`FramelessDialog`) 상속 패턴이 타입 힌팅, 이벤트 전달 계층, 테스트 작성(`isinstance` 검증) 면에서 훨씬 안정적이고 확장에 용이하다.


---

### EXP-011: Frameless 다이얼로그 드래그 후 자식 위젯 클릭 불능 버그 및 WindowStaysOnTopHint / Mouse Release 동기화
- **기록일자**: 2026-11-07
- **현상**:
  - 메인 컴패니언 창(`OrdisCompanionApp`)은 `WindowStaysOnTopHint` 속성을 가지는 반면, 자식 다이얼로그(`FramelessDialog`)에는 이 플래그가 누락되어 있었음.
  - 결과적으로 다이얼로그를 마우스로 잡고 드래그하여 이동시키는 순간 Windows DWM에서 Z-Order 역전 및 윈도우 비활성화가 발생하여, 다이얼로그 내부의 버튼(취소, 저장, 탭, 라디오 버튼 등)이 클릭되지 않는 먹통 현상 발생.
- **해결책**:
  1. **WindowStaysOnTopHint 동기화**: `FramelessDialog.__init__`에서 `Qt.WindowType.WindowStaysOnTopHint` 플래그를 기본 추가하여 창 이동 후에도 최상단 Z-Order와 활성 상태를 유지하도록 보장.
  2. **마우스 릴리즈 및 윈도우 활성화 파이프라인 정비**: `mouseReleaseEvent`에서 `_drag_pos` 리셋 및 `event.accept()`를 호출하고, 다이얼로그가 가시 상태일 때 `self.activateWindow()`와 `self.raise_()`를 즉시 실행하여 자식 위젯의 클릭 입력을 활성화.
  3. **드래그 라우팅 일원화**: `bind_drag_events(widget)` 유틸리티를 통해 헤더(`framelessHeader`) 및 메인 카드(`mainCard`)의 마우스 이벤트를 다이얼로그 자체 핸들러로 깔끔하게 위임하여 마우스 그래빙 유실 원천 차단.
- **교훈**:
  - Always-On-Top 플래그를 사용하는 애플리케이션 위에서 구동되는 모든 프레임리스 서브 윈도우/다이얼로그는 반드시 동일한 Top-most 속성과 릴리즈 후 재활성화(`activateWindow`) 로직을 일관되게 갖추어야 DWM 상의 입력 유실을 방지할 수 있다.


---

### EXP-012: Qt6 startSystemMove 네이티브 DWM 드래그 도입 및 대형 컨테이너 위젯 드래그 간섭 제거
- **기록일자**: 2026-11-07
- **현상**:
  - 소프트웨어 기반 `move()` 드래그는 마우스 빠른 이동 시 `mouseReleaseEvent` 유실로 `_drag_pos`가 고착되는 현상이 발생.
  - 더 심각한 원인: 대형 프레임 위젯(`main_card`) 전체에 마우스 드래그 핸들러를 바인딩해 두어, 사용자가 버튼, 탭, 라디오 버튼, 콤보박스 주변을 클릭할 때 손가락의 1~2픽셀 미세 떨림(micro-jitter)만으로도 `main_card`의 드래그 핸들러가 가로채어 자식 위젯의 `clicked` 시그널이 취소(cancel)됨.
- **해결책**:
  1. **Qt6 네이티브 `startSystemMove` 전면 도입**: `FramelessDialog.mousePressEvent()`에서 `wh = self.windowHandle(); if wh and hasattr(wh, "startSystemMove"): wh.startSystemMove()`를 호출하여 Windows OS DWM이 마우스 그랩과 릴리즈를 100% 직접 관리하도록 위임.
  2. **컨테이너 위젯 드래그 간섭 완전 제거**: `main_card` 전체에 걸려 있던 무분별한 `bind_drag_events`를 완전히 제거하고, 창 이동은 상단 전용 타이틀바(`framelessHeader`)를 통해서만 명확하게 수행되도록 역할을 분리.
- **교훈**:
  - 프레임리스 윈도우의 드래그 구현 시 대형 컨테이너(`mainCard` 등)에 마우스 이벤트를 덮어씌우는 것은 자식 위젯의 클릭을 캔슬시키는 안티패턴이다.
  - 창 이동은 상단 전용 헤더 바로 국한하고, Qt6에서는 OS 네이티브 창 이동(`startSystemMove`)을 사용하는 것이 가장 견고하다.


---

### EXP-013: 인게임 키 입력 연동 펫 모션의 완벽 차단(Zero-Trace) 3중 방어선 및 동적 핫 토글 연동
- **기록일자**: 2026-11-07
- **현상**:
  - 데스크톱 펫의 WASD/스페이스/E키 인게임 입력 연동 모션은 게임 플레이의 몰입감을 주지만, 보안/안티치트 오인식에 민감하거나 정적인 인터페이스를 선호하는 사용자를 위해 완벽한 차단 기능이 요구됨.
  - 단순 UI 비표시나 무시 처리가 아닌, 백그라운드 키 폴링 타이머 정지, Windows API(`GetAsyncKeyState`) 호출 0회, 잔류 가상 키 릴리즈 플러시 등 완벽한 리소스 및 시스템 콜 차단이 필요함.
  - 동시에, 오디스의 본래 감정표현(표정, 립싱크 입모양, 제스처, 부유 모션, 눈 깜빡임)은 자체 내부 렌더러 루프로 구동되므로 인게임 키 모션을 끄더라도 100% 온전하게 보존되어야 함.
- **해결책**:
  1. **3중 방어선(Zero-Trace) 차단 아키텍처**:
     - `GameInputListener.set_enabled(False)` 호출 시 즉시 50ms 폴링 타이머 정지(`self.timer.stop()`).
     - 타이머 콜백 `poll()` 진입부에 `if not self.enabled: return` 가드를 배치하여 `GetAsyncKeyState` / `GetForegroundWindow` 등 Windows API 호출 0회 강제.
     - 비활성화 시 즉시 `_release_all()`을 실행하여 키보드 상태를 초기화하고 펫을 중립 Idle 상태로 복귀.
  2. **설정창 GUI 및 영속성 연동**:
     - `SettingsManager`(`PersonaManager`)에 `get_motion_enabled` / `set_motion_enabled` 메서드 및 `user_settings.json` 저장 필드 추가.
     - `OrdisPersonaDialog` Tab 2(오디스 설정)에 전용 체크박스("인게임 키 입력 모션 연동 활성화") 및 안티치트 안전 안내 문구 배치.
  3. **동적 핫 토글(Zero-Restart)**:
     - 설정창에서 체크박스 변경 후 저장 시 메인 앱의 `DesktopPet.set_motion_enabled(enabled)`를 직접 호출하여 앱 재시작 없이 즉시 활성화/비활성화가 반영되도록 구현.
- **교훈**:
  - 키 입력 감지와 같은 OS 레벨 API 훅/폴링 기능은 "무시(ignore)"가 아니라 "완전 정지(Zero-Trace)" 방식으로 구현해야 사용자 신뢰성과 시스템 리소스 효율을 극대화할 수 있다.
  - 펫의 자체 UI 감정표현 레이어와 인게임 물리 오프셋 레이어를 명확히 분리함으로써 개별 토글이 서로 간섭하지 않는 안전한 아키텍처를 유지할 수 있다.

