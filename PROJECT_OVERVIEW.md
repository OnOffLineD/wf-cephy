# 🌌 WF-Companion & Optimizer (세팔론 오디스 스탠드얼론 AI 어시스턴트)
> **최종 업데이트**: 2026-10-16  
> **프로젝트 성격**: 무설치 포터블(Standalone) 데스크톱 오버레이 펫 + 인게임 모딩 OCR 정밀 진단기 + 로컬 LLM & RAG 위키 가이드 + 실시간 월드 이벤트/체크리스트 매니저

---

## 1. 기획 의도 및 핵심 철학 (Product Vision & Philosophy)

1. **Zero-Install 스탠드얼론 포터블 실행 (`Portable First`)**
   - 사용자가 Python, Ollama, CUDA, 환경 변수(PATH) 등을 직접 설치하거나 세팅할 필요가 없습니다.
   - 내장된 `python_embed/`와 포터블 `bin/llama/llama-server.exe` 및 `models/gemma-2-2b-it-Q4_K_M.gguf` 모델을 통해 `run_ordis.bat` 실행 한 번으로 즉시 구동됩니다.
   - 모든 파일 경로는 하드코딩 없이 [`scripts/path_config.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/path_config.py)를 통해 실행 위치 기반으로 동적 계산됩니다.

2. **수식 연산과 언어 생성의 철저한 분리 (`Math Engine vs LLM Persona`)**
   - 로컬 경량 LLM(`Gemma-2-2B-IT`)은 **절대 직접 데미지 수식을 계산하거나 8모드 빌드를 강제 생성하지 않습니다.**
   - 모든 DPS, 치명타 기댓값, 지면강타/강공격 피해, 방어력 감소(DR), EHP, 레벨캡(Lv.9999) 시너지는 파이썬 수치 시뮬레이션 엔진이 100% 정밀 연산합니다.
   - LLM은 **세팔론 오디스(Cephalon Ordis)** 페르소나를 바탕으로 일상 대화(Smalltalk)와 위키 RAG 기반 공략 해설에만 집중합니다.

3. **3-Tier 엄격한 채팅 & 기능 라우팅 (`3-Tier Strict Routing`)**
   - **Tier 1 (일상 대화 & 스마트 To-Do 감지)**: 인사, 피로 호소, 잡담 시 오디스 특유의 위트 있는 짧은 답변 제공 + 할 일 의도 감지 시 원클릭 `[+ 숙제 등록]` 버튼 생성 및 채팅 명령(`완료`, `삭제`, `추가`) 즉시 처리.
   - **Tier 2 (인게임 공략 & 메커니즘 RAG 가이드)**: 보스 약점, 속성 개편(Update 36 옥빛의 그림자 반영), 퀘스트, 파밍처 질문 시 `rules/wiki_docs/`를 검색하여 핵심 요약 제공.
   - **Tier 3 (인게임 모딩 스크린샷 OCR 정밀 진단)**: 캡처 도구(`Alt+S`) 또는 클립보드(`Ctrl+V`)로 모딩 화면 입력 시, WinOCR + 한국어 자모 분해 퍼지 매칭으로 **무기명, 좌측 스탯 패널 실측치(지면강타/강공격/슬라이드/총합 피해), 장착 모드**를 추출하여 종합 리포트 출력.

---

## 2. 기술 스택 (Tech Stack)

| 분류 | 기술 / 라이브러리 | 역할 및 상세 설명 |
| :--- | :--- | :--- |
| **GUI / Desktop Overlay** | `PyQt6` | 카카오톡 스타일 1:1 다크 테마 채팅창, 드래그 가능한 플로팅 오디스 펫(`DesktopPet`), 화면 영역 캡처기(`ScreenSnipper`), 스레드 안전한 `pyqtSignal` 비동기 UI 업데이트 |
| **Standalone LLM Server** | `llama.cpp` (`llama-server.exe`) | Ollama 의존성 완전 제거. Win32 Job Object로 좀비 프로세스 방지, `gemma-2-2b-it-Q4_K_M.gguf` 로컬 추론 (자동 다운로드/부트스트랩 지원) |
| **OCR & Vision Pipeline** | `winocr` (Windows Media OCR), `Pillow` | 다중 스케일 크롭(헤더/좌측 스탯 패널/상단 장착 슬롯), 고대비 전처리(`ImageOps.autocontrast`), 비동기 이벤트 루프 기반 고속 한글/영문 인식 |
| **Fuzzy & Korean Jamo** | `rapidfuzz`, 자체 자모 분해기 | 한글 음절을 초성/중성/종성 자모 단위로 분해(`decompose_hangul`)하여 인게임 폰트 OCR 오타(`길바나이즈드스닐` ➔ `갈바나이즈드 스틸`)를 90%+ 정확도로 복원 |
| **RAG & Knowledge Base** | `ChromaRAGRetriever`, `SQLite3`, JSON | `rules/wiki_docs/` 하위 마크다운/텍스트 전체 재귀 인덱싱, 한국어 조사 제거 토큰 매칭, WFCD(`@wfcd/items`) 한/영 무기·모드 통합 DB |
| **System & Hotkeys** | `ctypes` (`user32`, `kernel32`) | 글로벌 핫키(`Alt+S` 캡처, `Alt+C` 클립보드 진단) 비동기 감지(`GetAsyncKeyState`), Windows 프로세스 생명주기 관리 |
| **Testing & Dev Harness** | `pytest`, `graphify`, `pipeline_runner` | 단위/통합 헤드리스 테스트(14개 스위트), AST 심볼 그래프 분석 및 로컬 워커 패치 자동화 |

---

## 3. 시스템 아키텍처 및 디렉토리 구조 (Directory Structure)

```text
2.7 WarframeOptimizer/
├── run_ordis.bat                 # 원클릭 스탠드얼론 실행 배치 스크립트
├── PROJECT_OVERVIEW.md           # 프로젝트 종합 문서 (현재 파일)
├── AGENTS.md / GEMINI.md         # 에이전트 오케스트레이션 및 제품 규칙 정의서
├── bin/llama/                    # 포터블 llama-server.exe 및 실행 바이너리
├── models/                       # gemma-2-2b-it-Q4_K_M.gguf 로컬 LLM 모델 저장소
├── python_embed/                 # 무설치 배포용 임베디드 Python 런타임
├── data/
│   ├── raw_wfcd/                 # WFCD 원본 JSON (Weapons.json, Mods.json, Korean translation)
│   ├── incarnon_trees.json       # 인카논 무기 진화 트리 및 고유 특성 데이터
│   ├── user_checklist.json       # 사용자 일일/주간 숙제 및 커스텀 할 일 영구 저장소 (UTF-8)
│   └── wf_database.sqlite        # 정규화된 무기/모드/워프레임 SQLite DB
├── rules/
│   ├── 01_damage_formulas.md     # 데미지 버킷, 치명타 티어, 양자화 제외 실전 수식
│   ├── 02_status_and_scaling.md  # 상태이상 DoT 및 적 방어력/레벨 스케일링 규칙
│   ├── 03_survivability_rules.md # EHP, 다중 피해 감소(DR), 실드 게이팅 수식
│   ├── 04_synergy_matrix.md      # 헬민스, 집정관 파편, 아케인, 동반자 시너지 매트릭스
│   └── wiki_docs/                # RAG 검색용 한국어 큐레이션 공략집 (보스, 팩션, 게임모드, 퀘스트, 기믹)
├── ocrTestImg/                   # 인게임 모딩 스크린샷 벤치마크 테스트셋 (14종)
├── scripts/                      # 핵심 애플리케이션 및 엔진 소스 코드
└── tests/                        # Pytest 자동화 검증 테스트 스위트
```

---

## 4. 핵심 모듈 및 주요 함수 명세 (Core Modules & Functions)

### 4.1. 데스크톱 GUI 및 런타임 관리
* **[`scripts/path_config.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/path_config.py)**
  * `PathConfig` / `get_path(*parts)`: 실행 위치(`__file__` 및 `sys.executable`)를 기준으로 프로젝트 루트(`ROOT_DIR`)와 하위 경로를 동적 반환하여 폴더 이동 시에도 경로 깨짐 방지.
* **[`scripts/desktop_companion.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/desktop_companion.py)**
  * `OrdisCompanionApp(QWidget)`: 메인 카카오톡 스타일 채팅 UI 및 우측 실시간 이벤트/체크리스트 사이드바 통합 윈도우.
    * `send_user_message()`: 사용자 입력 전송, 채팅 기반 할 일 명령(`완료`/`삭제`/`추가`) 즉시 처리 및 백그라운드 LLM 응답 요청.
    * `process_screen_image(img)` / `analyze_clipboard()`: 캡처 또는 클립보드 이미지를 백그라운드 스레드에서 OCR 진단 후 `chat_reply_signal`로 안전하게 UI 렌더링.
    * `check_hotkeys()`: `user32.GetAsyncKeyState`를 통해 충돌 없이 `Alt+S`(영역 캡처), `Alt+C`(클립보드 분석) 글로벌 단축키 감지.
  * `DesktopPet(QWidget)`: 화면 위를 떠다니는 세팔론 오디스 미니 펫. 감정 상태(`IDLE`, `THINKING`, `HAPPY`, `ALERT`) 애니메이션 및 더블클릭 채팅창 토글 지원.
  * `ScreenSnipper(QWidget)`: 다중 모니터 지원 전체 화면 드래그 캡처 오버레이.
  * `ChatBubble(QWidget)`: 마크다운 볼드/코드 하이라이팅 및 스마트 할 일 `[+ 숙제 등록]` 인라인 버튼을 포함한 말풍선 위젯.
* **[`scripts/embedded_llm_runner.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/embedded_llm_runner.py)**
  * `EmbeddedLLMRunner`: 포터블 `llama-server.exe` 프로세스 라이프사이클 관리자.
    * `ensure_binaries_exist()` / `ensure_model_exists()`: 바이너리나 GGUF 모델 누락 시 공식 릴리즈에서 자동 다운로드 및 압축 해제.
    * `start_server()` / `stop_server()`: Win32 Job Object(`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) 바인딩으로 메인 앱 종료 시 자식 프로세스 즉시 종료 보장.

### 4.2. 인게임 모딩 OCR 및 한국어 퍼지 매칭 파이프라인
* **[`scripts/screen_mod_analyzer.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/screen_mod_analyzer.py)**
  * `ScreenModAnalyzer`: 인게임 모딩 스크린샷 종합 진단 엔진.
    * `ocr_image(image_input)`: 원본 및 `ImageOps.autocontrast` 고대비 변환 이미지를 `winocr`(`lang="ko"`)로 이중 스캔하여 텍스트 라인 병합.
    * `extract_left_panel_stats(img, full_text)`: 좌측 스탯 패널(`x: 0~0.33, y: 0.10~0.65`)에서 인게임 재화(크레딧/엔도 `>= 150,000`)를 필터링하고 **지면강타(`slam_damage`), 강공격(`heavy_damage`), 슬라이드(`slide_damage`), 총계(`total_damage`), 치명타 확률/배수(`crit_chance`, `crit_mult`), 공격 속도(`speed`)**를 정확히 매핑.
    * `crop_and_ocr_mod_slots(img, category)`: 상단 장착 모드 슬롯 영역(`x: 0.30~0.98, y: 0.05~0.52`) 및 2행 4열 개별 슬롯을 크롭하여 장착 모드 및 리벤 여부 추출.
    * `calculate_comprehensive_metrics(w_meta, left_stats, mod_objs, riven_stats)`: 추출된 좌측 패널 실측치(`slam_damage`, `heavy_damage`, `total_damage`)를 최우선 반영하여 **지속/순간 DPS, 최고점(치명타 최고 롤), 최저점(비크리 보장), 인카논 폼, 12배수 연속기 풀스택 포텐셜** 산출.
    * `format_ordis_briefing(w_meta, detected_mods, metrics)`: 세팔론 오디스 스타일의 마크다운 종합 진단 리포트 생성.
    * `resume_pending_diagnosis(user_weapon_text)`: 무기명이 리치/자매단 이름 등으로 가려져 인식되지 않았을 때, 사용자가 채팅으로 무기명을 알려주면 즉시 이어서 진단을 완료하는 대화형 복구 함수.
* **[`scripts/jamo_matcher.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/jamo_matcher.py)**
  * `decompose_hangul(text)`: 완성형 한글(`가`~`힣`)을 초성/중성/종성 호환 자모로 분해.
  * `match_mods_jamo(ocr_text, mods_index, category, threshold=72.0)`: 무기 카테고리(`Primary`, `Secondary`, `Melee`)에 맞는 모드 후보군을 필터링하고, 자모 분해 문자열 기준 `rapidfuzz.fuzz.ratio`를 계산하여 심한 OCR 오타에서도 장착 모드를 정확히 식별.
* **[`scripts/wf_data_indexer.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/wf_data_indexer.py)**
  * `WFDataIndexer`: WFCD 영문/국문 무기 및 모드 데이터를 로드하여 정규화 인덱스 구축.
    * `fuzzy_match_weapon(query)`: 리치/자매단/코다 접두어 제거 및 한/영 퍼지 매칭으로 무기 메타데이터 검색.
    * `match_mod(text, category)` / `extract_all_mods(ocr_text, weapon_category)`: 텍스트 내 장착 모드 탐색.

### 4.3. 로컬 LLM 오케스트레이션 & 위키 RAG
* **[`scripts/llm_orchestrator.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/llm_orchestrator.py)**
  * `LLMOrchestrator`: 사용자 채팅 입력을 분석하여 3-Tier로 라우팅.
    * `chat(user_message)`: 대기 중인 스크린샷 무기 확인 ➔ 일상 대화 패턴 감지(`chat_smalltalk`) ➔ 위키 키워드/공략 검색(`chat_guide`) 순으로 분기.
    * `_call_llm(prompt, system_prompt, max_tokens)`: `http://127.0.0.1:8080/v1/chat/completions` (`llama-server`) 호출 및 오프라인 시 즉각적인 폴백 안내 제공.
* **[`scripts/chroma_rag_retriever.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/chroma_rag_retriever.py)**
  * `ChromaRAGRetriever`: `rules/wiki_docs/` 하위 모든 디렉토리(`bosses`, `factions_and_enemies`, `game_modes`, `mechanics`, `quests_and_story`)를 `os.walk`로 재귀 스캔하여 청크 인덱싱.
    * `retrieve(query, top_k=3)`: 한국어 조사(`은/는/이/가/을/를/에/의/로/와/과`) 자동 제거 및 헤더/파일명 가중치 스코어링으로 가장 관련성 높은 공략 문단 반환.

### 4.4. 실시간 월드 상태 & 스마트 체크리스트
* **[`scripts/world_state_tracker.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/world_state_tracker.py)**
  * `WorldStateTracker`: 실시간 인게임 주기와 숙제 체크리스트 관리.
    * `fetch_live_events()`: Warframe 공식 WorldState API 및 결정론적 폴백 타이머를 통해 **지구/시터스 낮·밤 주기, 두비리 감정 나선(기쁨/분노/부러움/슬픔/공포), 출격(Sortie) 보스, 보이드 상인(바로 키티어)** 상태 반환.
    * `detect_todo_intent(message)`: 채팅 메시지에서 숙제/파밍 등록 의도를 감지하고, 단순 공략 질문(`어떻게`, `공략`, `약점`)과 구별하여 할 일 제목 추출.
    * `process_chat_todo_command(message)`: 채팅창에서 바로 `"출격 완료"`, `"집정관 삭제"`, `"강철의 길 순회로 할일 추가"` 등을 실행.

### 4.5. 수학적 시뮬레이션 코어 엔진
* **[`scripts/damage_simulator.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/damage_simulator.py)**: `DamageSimulator.calculate_damage_metrics()`, `simulate_ttk()`, `compare_rivens()` — 합연산/곱연산 버킷, 치명타 티어, 상태이상 DoT 적분 TTK 및 리벤 A/B 비교 연산.
* **[`scripts/survival_evaluator.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/survival_evaluator.py)**: `SurvivalEvaluator.calculate_ehp()`, `evaluate_survival_time()`, `evaluate_shield_gating()` — 방어력/어빌리티/적응(Adaptation) 다중 DR 및 실드 게이팅 생존력 평가.
* **[`scripts/synergy_planner.py`](file:///g:/내%20드라이브/2.%20Personal/2.7%20WarframeOptimizer/scripts/synergy_planner.py)**: `SynergyPlanner.plan_levelcap_synergy()` — Lv.9999 강철의 길 대상 TTK 단축을 위한 헬민스 방어력 삭감, 외부 고정 치명타, 동반자 프라이밍 조합 역산.

---

## 5. 진행 현황 및 마일스톤 (Progress & Milestones)

| 마일스톤 | 핵심 목표 | 세부 달성 내역 | 상태 |
| :--- | :--- | :--- | :---: |
| **Milestone 1** | **데이터 파이프라인 & 코어 수식 엔진** | • WFCD 무기/모드 한·영 데이터 인덱싱 (`WFDataIndexer`)<br>• 데미지/TTK 시뮬레이터 (`DamageSimulator`), 생존 평가기 (`SurvivalEvaluator`), 레벨캡 시너지 플래너 (`SynergyPlanner`) 구현 및 단위 테스트 통과 | ✅ **완료** |
| **Milestone 2** | **위키 지식 베이스 구축 & RAG 검색** | • Update 36 (옥빛의 그림자) 방어력 상한(2700=90% DR) 및 팩션 약점 개편 반영<br>• 하위 폴더 전체 재귀 인덱싱 및 한국어 조사 제거 스코어링 (`ChromaRAGRetriever`) | ✅ **완료** |
| **Milestone 3** | **스탠드얼론 포터블 아키텍처 전환** | • Ollama 의존성 완전 제거 ➔ 포터블 `llama-server.exe` + `gemma-2-2b-it` 내장 (`EmbeddedLLMRunner`)<br>• 하드코딩 경로 전수 제거 및 동적 루트 경로(`path_config.py`) 적용 | ✅ **완료** |
| **Milestone 4** | **세팔론 오디스 데스크톱 컴패니언 GUI** | • 카카오톡 스타일 1:1 채팅 UI, 플로팅 오디스 펫, 화면 스니퍼(`Alt+S`) 구현<br>• 스레드 안전한 `pyqtSignal` 통신 및 `GetAsyncKeyState` 핫키 안정화<br>• 실시간 월드 이벤트 트래커 & 스마트 To-Do 체크리스트 연동 | ✅ **완료** |
| **Milestone 5** | **인게임 모딩 스크린샷 OCR 정밀화** | • `winocr` 객체 직렬화 버그 수정 및 좌측 스탯 패널 실측치(지면강타, 강공격, 슬라이드, 총합 피해) 1:1 매핑<br>• 한국어 자모 분해 퍼지 매처(`jamo_matcher.py`) 도입으로 오타 복원<br>• `ocrTestImg/` 14종 인게임 스크린샷 벤치마크 **14/14 (100%) 통과**<br>• 전체 헤드리스 테스트 스위트 **14/14 (100%) 통과** | ✅ **완료** |
| **Milestone 6** | **향후 고도화 (Next Steps)** | • 리치/자매단/코다 무기 이름 잘림(`...`) 발생 시 무기 스탯 역추적 자동 식별 고도화<br>• 인게임 오버레이 투명도/항상 위(Always on Top) 사용자 설정 UI 추가<br>• 리벤 모드 단독 캡처 시 옵션 수치 자동 추출 및 A/B 비교 UI 직결 | 🔜 **예정** |
