# 🌌 WF-Companion (세팔론 오디스 데스크톱 어시스턴트)
> **최종 업데이트**: 2026-11-04
> **프로젝트 성격**: 데스크톱 오버레이 펫 + 인게임 모딩 OCR 진단기 + 로컬 LLM·위키 가이드 + 실시간 월드 상태·숙제 관리

---

## 1. 핵심 철학

1. **수식과 언어 생성의 분리**
   - 로컬 LLM은 데미지를 계산하거나 8모드 빌드를 생성하지 않습니다.
   - DPS, 치명타, 속성 합성, 방어력 계산은 파이썬 엔진이 맡고, LLM은 오디스 페르소나의 잡담과 위키 기반 공략 해설만 담당합니다.
2. **3단계 채팅 라우팅**
   - **잡담**: 인사, 피로 호소 등에는 오디스 말투로 짧게 답합니다. 숙제 의도를 감지하면 등록 버튼을 띄우고, `완료`·`삭제`·`추가` 명령을 처리합니다.
   - **공략**: 보스, 속성, 퀘스트 질문은 `rules/wiki_docs/`를 검색해 풀어서 답하고 근거 문서를 표시합니다. 드롭 위치는 `drops_all.json`에서 바로 답합니다. 자료에 없으면 없다고 말하고, 그 질문을 로컬 로그(`logs/guide-misses.jsonl`)에 남깁니다.
   - **스크린샷 진단**: `F9`, `Alt+Q`, `PrtSc`, `Ctrl+V`로 받은 모딩 화면에서 무기, 패널 수치, 장착 모드를 읽어 리포트합니다.
3. **값이 불확실하면 추측하지 않습니다**
   - 라벨이 확인된 패널 값만 쓰고, 없으면 코덱스와 모드로 계산하며 그 사실을 리포트에 표시합니다.

---

## 2. 기술 스택

| 분류 | 기술 | 역할 |
| :--- | :--- | :--- |
| **GUI** | `PyQt6` | 다크 테마 채팅창, 플로팅 펫, 탭 UI(채팅·숙제·현황) |
| **LLM** | `llama.cpp` (`bin/llama-server.exe`) | `models/google_gemma-4-E2B-it-Q4_K_M.gguf`, 포트 18080. Job Object로 앱 강제 종료 시에도 서버 종료 |
| **슬롯 탐지** | `ultralytics` YOLOv8n | `models/slot_detector.pt`. 모드·빈 슬롯, 무기 헤더, 아케인, 리벤 슬롯 탐지 |
| **OCR** | `winocr`, `Pillow` | Windows OCR. 슬롯과 패널을 여러 전처리로 읽어 결합 |
| **퍼지 매칭** | `rapidfuzz`, 자모 분해 | 한글 자모 단위 비교로 OCR 오타 복원 |
| **위키 검색** | 글자 조각(2~3자) BM25 | `rules/wiki_docs/` 재귀 인덱싱. 띄어쓰기·조사에 강하고 은어는 `data/guide_aliases.json`으로 연결. 벡터 DB는 쓰지 않습니다 |
| **월드 상태** | `api.warframestat.us` | 시터스, 두비리, 출격, 집정관, 바로 키티어, 주간 인카논. 실패 시 마지막 값과 시터스 추정치 표시 |
| **테스트** | `pytest`, `scripts/probe.py` | 사용자 데이터와 분리된 테스트, 커밋 훅의 3개 게이트 |

---

## 3. 디렉토리 구조

```text
2.7 WarframeOptimizer/
├── start_companion.bat           # 데스크톱 컴패니언 실행
├── main_companion.py             # 앱 진입점 (펫 + 채팅 패널 + LLM)
├── bin/                          # llama-server.exe와 DLL (git 제외)
├── models/                       # GGUF 모델, slot_detector.pt (GGUF는 git 제외)
├── python_embed/                 # 임베디드 Python (현재 PyQt6 등 패키지 미설치)
├── data/
│   ├── raw_wfcd/                 # WFCD 원본 (주무기, 보조무기, 근접, 워프레임, 모드, 한국어)
│   ├── arcane_effects.json       # 무기 아케인 R5 효과표
│   ├── user_builds.json          # 스캔해서 저장한 무기 빌드 (git 제외)
│   ├── user_checklist.json       # 사용자 숙제 (UTF-8)
│   └── persona_config.json       # 오디스 성격 설정
├── rules/
│   ├── 01_damage_formulas.md     # 데미지 버킷, 치명타, 속성 합성 순서
│   ├── 02_status_and_scaling.md  # 상태이상, 적 방어력, 레벨 스케일링
│   ├── 03_survivability_rules.md # EHP, 피해 감소, 실드 게이팅
│   ├── 04_synergy_matrix.md      # 헬민스, 파편, 아케인 시너지
│   └── wiki_docs/                # 위키 검색용 공략 문서
├── ocrTestImg/                   # 인식 벤치마크 샘플
├── scripts/                      # 앱과 엔진 소스
└── tests/                        # 자동 테스트, fixtures/ocr_ground_truth.json 정답 데이터
```

`start.bat`, `scripts/app_server.py`, `scripts/optimizer_engine.py`, `web/`은 이전 웹 옵티마이저의 잔재로, 데스크톱 컴패니언은 사용하지 않습니다.

---

## 4. 핵심 모듈

### 4.1. 앱과 런타임
* **`main_companion.py`**: 패널과 펫을 만들고 LLM을 백그라운드에서 시작합니다.
* **`scripts/desktop_companion.py`**
  * `OrdisCompanionApp`: 채팅, 숙제, 현황 탭. 위젯 갱신은 시그널로 UI 스레드에서만 처리합니다.
  * `DesktopPet`: 플로팅 펫. 더블클릭으로 채팅창을 토글합니다.
  * `ChatBubble`, `render_chat_markup`: 말풍선과 굵게·코드 표시.
  * 단축키: `Alt+W` 채팅창, `Alt+Q`·`F9` 화면 캡처 진단, `PrtSc` 클립보드 진단.
* **`scripts/embedded_llm_runner.py`** `EmbeddedLLMRunner`
  * `start_server()`: 이미 응답하는 서버는 재사용하고, 없으면 모델을 받아 실행합니다. 실패 사유는 `last_error`, 서버 로그는 `data/logs/llama-server.log`에 남습니다.
  * `stop_server()`: 이 앱이 띄운 프로세스만 종료합니다.
  * `bin/llama-server.exe`는 자동으로 받지 않습니다. `scripts/setup_portable_runtime.py`가 설치된 Ollama에서 복사합니다.
* **`scripts/path_config.py`**: `get_path()`는 프로젝트 기준 경로, `get_user_data_path()`는 사용자 데이터 경로입니다. 테스트는 `WF_USER_DATA_DIR`로 후자를 임시 폴더로 돌립니다.

### 4.2. 스크린샷 진단
* **`scripts/yolo_slot_detector.py`** `YOLOSlotDetector`: 슬롯을 찾아 행과 열로 정렬합니다.
* **`scripts/screen_mod_analyzer.py`** `ScreenModAnalyzer`
  * `diagnose_screenshot()`: 무기 인식 → 슬롯 OCR → 모드 매칭 → 패널 파싱 → 계산 → 리포트.
  * `extract_left_panel_stats()`: 라벨이 확인된 값만 읽습니다. `A ▸ B` 표기는 오른쪽이 실제 적용값입니다.
  * `_build_slot_candidates()`, `_match_single_slot()`: 무기에 맞는 모드 후보를 만들고 OCR 결과들의 일치도로 고릅니다.
  * `_detect_arcane()`: 화면 우상단의 아케인 이름을 읽습니다.
  * `resume_pending_diagnosis()`, `resume_pending_riven()`: 무기명과 리벤 수치를 채팅으로 받아 이어서 계산합니다.
* **`scripts/wf_data_indexer.py`** `WFDataIndexer`
  * `_classify_mod_stat()`: 모드 스탯을 직접 피해, 상태이상 피해, 처치 스택 등으로 정확히 분류합니다.
  * `fuzzy_match_weapon()`은 OCR용, `match_weapon_strict()`는 채팅용입니다.

### 4.2.1. 빌드 저장과 리벤 리롤 비교
* **`scripts/build_store.py`** `BuildStore`: 무기당 빌드 1개를 `data/user_builds.json`에 저장합니다(git 제외). 슬롯 위치, 아케인, 스캔 당시 패널 값, 리벤 옵션이 들어갑니다.
* **저장 흐름**: 모딩 화면 스캔 → 인식 검토 → 필요하면 슬롯 수정 창(`scripts/build_edit_dialog.py`) → `인식 일치` 버튼을 누르면 저장. 무기를 특정하지 못한 스캔은 저장하지 않습니다.
* **`scripts/riven_reroll_reader.py`**: 리롤 화면 판독. F9 캡처에서 `소지품/모드` 제목과 옵션 줄로 자동 판별하고, **왼쪽 카드를 이전, 오른쪽 카드를 새 옵션**으로 읽습니다. 값은 화면 그대로 씁니다.
* **`ScreenModAnalyzer.compare_riven_rolls()`**: 저장된 패널에서 이전 리벤을 빼고 두 옵션을 각각 더해 계산하며, **지속 DPS**로 판정합니다. 표시 항목은 지속·순간 DPS, 기대 단발, 최고점, 최저점, 풀스택 추정입니다.
  * 빌드가 없으면 모드 없이 계산하고 안내합니다.
  * 빌드에 리벤이 없으면 빈 슬롯에 넣고, 꽉 찼으면 뺄 모드를 고르게 합니다.
  * 상태 이상 확률, 확대율처럼 DPS 수식에 없는 옵션은 "반영되지 않는 옵션"으로 따로 표시합니다.
* **`scripts/riven_compare_dialog.py`**: 상세 비교 표와 옵션 수정 창. 비교 결과의 `새 옵션 사용` 버튼으로 빌드의 리벤을 갱신합니다. 리롤 이력은 남기지 않습니다.
* **채팅**: `쿠바 자르에 뭐 꼈어?`, `나타루크 DPS 얼마야?`, `저장한 무기 뭐 있어?`, `쿠바 자르 빌드 삭제해줘`(확인 버튼 필요). 모드 이름과 수치는 코드가 저장값으로 출력하고, LLM은 앞 문장의 말투만 맡습니다.

### 4.3. 데미지 계산
* **`scripts/damage_formulas.py`**: 위키 공식 모음. 적 방어력, 치명타, 약점, 아스널 총계, 실효 연사력, 출혈 틱, 슬롯 순서 속성 합성, 진영 배율.
* **`scripts/warframe_damage_engine.py`** `WarframeDamageEngine`
  * `compute_metrics()`: 지속·순간 DPS, 최고점, 최저점, 멀티샷 구조, 타입별 피해.
  * `compute_elements()`: 슬롯 순서 합성과 진영별 배율. 패널 속성 줄을 우선합니다.
  * `compute_full_stack()`: 아케인과 처치 스택, 연속기를 최대로 가정한 추정치.
  * `strip_riven_from_panel()`: 패널에서 리벤을 빼서 장착 전후를 비교합니다.
* **`scripts/damage_simulator.py`**: TTK와 리벤 A/B 비교. 상태이상 DoT는 TTK에 포함되지 않습니다.
* **`scripts/survival_evaluator.py`**, **`scripts/synergy_planner.py`**: EHP와 레벨캡 시너지 계산.

### 4.4. 채팅
* **`scripts/llm_orchestrator.py`** `LLMOrchestrator`: 대기 중인 진단 처리 → 의도 분류(키워드 게이트 + `INTENT_GRAMMAR` 1-Token GBNF 분류) → 도메인별 도구 필터링 및 동적 GBNF 문법 조립(`select_domain_tools()`, `build_gbnf_tool_grammar()`, `resolve_domain_tool()`) → 드롭 표, 공략 또는 잡담. 서버가 없으면 위키 원문이나 준비된 대사로 답합니다. 자료에 없는 숫자가 든 답변 줄은 지웁니다.
* **`scripts/guide_retriever.py`** `GuideRetriever`: 위키 문단 BM25 검색, 무기·워프레임 팩트 카드. 질문의 핵심 단어를 충분히 담지 못한 문단은 결과에서 뺍니다. 평가 질문은 `tests/fixtures/guide_questions.json`입니다.
* **`scripts/drop_lookup.py`** `DropIndex`: 아이템별 드롭 위치와 성유물 보상 조회. 확률만 있어 시간당 효율은 판단하지 않습니다.
* **`scripts/short_term_memory.py`**, **`scripts/persona_manager.py`**, **`scripts/emotion_parser.py`**: 대화 기억, 성격 모드, 감정 태그 파싱.
* **`scripts/layered_pet_renderer.py`**: 감정과 말하기 애니메이션 렌더링.

### 4.5. 월드 상태와 숙제
* **`scripts/world_state_tracker.py`** `WorldStateTracker`
  * `fetch_live_events()`: 5개 항목을 병렬로 받고, 실패한 항목은 마지막 값을 씁니다.
  * `format_world_events()`: 현황 탭 HTML.
  * `process_chat_todo_command()`, `execute_todo_tool()`: `출격 완료`, `집정관 삭제`, `강철의 길 순회로 할 일 추가` 및 GBNF로 추출된 정형 도구 호출(`add_todo`, `complete_todo`, `delete_todo`)을 실행합니다. 대상이 불분명한 명령은 아무것도 바꾸지 않습니다.
  * 저장은 임시 파일 교체 방식이고, 손상된 파일은 `.corrupt-날짜`로 보관합니다.

---

## 5. 검증

| 항목 | 명령 | 내용 |
| :--- | :--- | :--- |
| 빌드 | `python -m compileall -q scripts` | 문법 확인 |
| 테스트 | `python -m pytest tests/ -q` | 게임 패널 값과 대조하는 수식 테스트, 정답 비교 벤치마크 포함 |
| 게이트 | `python scripts/probe.py` | 테스트, 위키 예제 수식, 그래프 신선도. 커밋 훅에서도 실행 |

현재 인식 수준 (샘플 24장, `tests/test_ocr_benchmark.py`): 모드 88%, 무기 90%. 1280px 이상 캡처는 무기를 특정하면 모드와 패널 값을 모두 맞힙니다. 850px로 축소된 이미지는 패널 정확도가 떨어집니다.

---

## 6. 알려진 한계

- **데미지**: 모드는 최대 랭크로 가정합니다. 인카논 진화와 일부 아케인 효과는 코덱스 계산에 없고, 패널 값이 있으면 패널을 우선합니다. 점사 연사력, 근접 콤보 길이, 비질란티 강화는 미구현입니다.
- **무기 DB**: 아크건이 없고 일부 신규 무기(Ziks)가 빠져 있습니다.
- **포터블**: `python_embed`에 패키지가 없어 시스템 Python으로 실행됩니다.
