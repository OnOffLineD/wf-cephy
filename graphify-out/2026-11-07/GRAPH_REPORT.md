# Graph Report - 2.7 WarframeOptimizer  (2026-11-07)

## Corpus Check
- 181 files · ~948,217 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 24 file(s) not represented in the graph (top: .csv 8, .toml 7, (none) 3)

## Summary
- 1938 nodes · 4826 edges · 110 communities (90 shown, 20 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 441 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3392e5d8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- desktop_companion.py
- json
- OrdisCompanionApp
- LLMOrchestrator
- LocalPipelineRunner
- optimizer_engine.py
- apply_frameless_shell
- probe.mjs
- Project Specification: Warframe Build & Synergy Optimizer (WF-Optimizer)
- AGENTS.md — 다중 AI 협업 운영 규약 (Antigravity & Claude Code with orchestra-kit)
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- AGENTS.md — 다중 AI 협업 운영 규약 (Antigravity & Claude Code with orchestra-kit)
- .resolve_domain_tool
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- EmbeddedLLMRunner
- DesktopPet
- test_guide_search.py
- 1. 데미지 버킷 분류 (Damage Buckets)
- 2. 상태이상 메커니즘 (Status Effects)
- TodoPanel
- 04. Warframe External Synergy & Level-Cap Matrix
- 워프레임 성계 지도 기본 미션 유형 가이드 (Star Chart Mission Types)
- RivenRollEditDialog
- 03. Warframe Survivability & Shield Gating Rules
- /harness
- Engineering Guardrails (Global Standards)
- Global Multi-Agent Harness Directive (Universal System Prompt)
- Engineering Guardrails (Global Standards)
- Global Engineering Experience Library (Harness² Cross-Project Knowledge)
- 워프레임 실전 메타 무기 티어 및 주요 컨텐츠 추천 장비 (Update 36 이후 최신 기준)
- scripts/orchestra.py
- WorldStateTracker
- Domain Context & Architecture Memory (Warframe Companion)
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- Project Accumulated Experience Library (Harness² Recursion)
- Multi-Agent Orchestration & RBAC Guidelines
- Domain Context & Architecture Memory
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- test_riven_recovery.py
- Domain & State Architecture Guardrails (Warframe Companion)
- Domain & State Architecture Guardrails
- Project Progress & Verification Board
- Project Progress & Verification Board (Warframe Companion)
- Project Accumulated Experience Library (Harness² Recursion)
- test_build_chat_and_dialogs.py
- os
- test_companion_app.py
- test_elements.py
- ScreenModAnalyzer
- PersonaManager
- DropIndex
- pytest
- ShortTermMemory
- test_chat_routing_comprehensive.py
- test_mod_matching.py
- 🌌 WF-Companion (세팔론 오디스 데스크톱 어시스턴트)
- test_chat_intent.py
- test_ocr_benchmark.py
- GameDataUpdater
- RivenQuickInputDialog
- test_game_data.py
- game_catalog.py
- test_saved_builds.py
- WarframeDamageEngine
- orchestra.py
- test_damage_formulas.py
- FakeServer
- .add_chat_bubble
- app_server.py
- BuildEditDialog
- sys
- decompress_index
- MorphingTabBar
- orchestra-kit/orchestra.py
- HudButton
- screen_mod_analyzer.py
- test_damage_breakdown_dialog.py
- WFDataIndexer
- test_innate_traits.py
- GuideRetriever
- LayeredPetRenderer
- innate_traits.py
- generate_ui_assets.py
- AGENTS.md — 다중 AI 개발 운영 규약 (범용)
- test_emotion_animation.py
- YOLOSlotDetector
- ChatBubble
- decompose_hangul
- results
- GameCatalog
- orchestra-kit
- guide_retriever.py
- .open_build_editor
- build_character_assets.py
- 🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide)
- 🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide)
- 2. 🧠 [핵심 아키텍처] 1-Token GBNF 도메인 분류 & 동적 도구 문법 파이프라인
- review.md
- 언어·스택별 게이트 예시 (`[verify].gates`, `[project].setup`, 빌더 허용 도구)
- revise.md
- ._official_mismatches
- .orchestra/EXPERIENCE.md
- builder.md

## God Nodes (most connected - your core abstractions)
1. `ScreenModAnalyzer` - 94 edges
2. `OrdisCompanionApp` - 78 edges
3. `LLMOrchestrator` - 71 edges
4. `WarframeDamageEngine` - 50 edges
5. `WFDataIndexer` - 38 edges
6. `Project` - 35 edges
7. `Project` - 35 edges
8. `Project` - 35 edges
9. `WorldStateTracker` - 35 edges
10. `HudButton` - 34 edges

## Surprising Connections (you probably didn't know these)
- `Phase 2: 정밀 데미지 및 TTK 시뮬레이터 (`scripts/damage_simulator.py`)` --references--> `CombatState`  [INFERRED]
  warframe.md → scripts/damage_simulator.py
- `신규 도메인/도구 확장 방법 (인수인계 가이드)` --references--> `build_gbnf_tool_grammar()`  [INFERRED]
  HANDOVER.md → scripts/llm_orchestrator.py
- `4.2.1. 빌드 저장과 리벤 리롤 비교` --references--> `BuildStore`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/build_store.py
- `4.1. 앱과 런타임` --references--> `render_chat_markup()`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/desktop_companion.py
- `4.1. 앱과 런타임` --references--> `DesktopPet`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/desktop_companion.py

## Import Cycles
- None detected.

## Communities (110 total, 20 thin omitted)

### Community 1 - "json"
Cohesion: 0.15
Nodes (4): format_report(), test_update_writes_every_file_and_reports(), test_daily_reset_keeps_weekly_done(), test_old_integer_week_key_does_not_reset_same_week()

### Community 2 - "OrdisCompanionApp"
Cohesion: 0.09
Nodes (8): main(), OrdisCompanionApp, check_hotkeys(), test_companion_hud_buttons_and_icon_tabs(), test_ordis_companion_headless_and_tabs(), test_capture_fullscreen_execution(), test_capture_fullscreen_methods_exist(), test_chat_popup_draggable()

### Community 3 - "LLMOrchestrator"
Cohesion: 0.15
Nodes (10): LLMOrchestrator, test_works_with_llm_server_off(), test_chat_mood_and_intensity_prefix_gbnf(), test_guide_prompt_uses_persona_text_not_raw_dict(), test_smalltalk_prompt_has_memory_and_mood_instruction(), test_orchestrator_chat_strips_tag_and_provides_mood(), test_chat_answer_reaches_the_waiting_scan(), test_orchestrator_cancels_pending_riven() (+2 more)

### Community 4 - "LocalPipelineRunner"
Cohesion: 0.08
Nodes (7): LocalPipelineRunner, main(), class_methods(), runner(), test_insert_goes_into_class_before_module_aliases(), test_insert_goes_into_last_class_before_main_guard(), test_module_without_class_inserts_top_level_function()

### Community 5 - "optimizer_engine.py"
Cohesion: 0.12
Nodes (21): CombatState, DamageSimulator, ModConfig, WeaponStats, OptimizerEngine, OptimizerRequest, SurvivalEvaluator, WarframeModConfig (+13 more)

### Community 6 - "apply_frameless_shell"
Cohesion: 0.06
Nodes (25): test_boxes(), apply_frameless_shell(), move(), FramelessDialog, header_move(), header_press(), header_release(), _add_stat() (+17 more)

### Community 7 - "probe.mjs"
Cohesion: 0.10
Nodes (12): __filename, g1, g2, g3, ROOT_DIR, args, content, EXP_FILE (+4 more)

### Community 8 - "Project Specification: Warframe Build & Synergy Optimizer (WF-Optimizer)"
Cohesion: 0.10
Nodes (20): 1.1. 필수 달성 유스케이스 (Core Use Cases), 1. 프로젝트 개요 및 목표 (Project Overview & Goals), 2. 기술 스택 (Tech Stack), 3. 시스템 아키텍처 및 디렉토리 구조 (System Architecture), 4. 핵심 모듈별 상세 구현 방안 (Detailed Implementation Plan), 5.1. LLM -> Python 입력 JSON 스키마, 5.2. Python -> LLM 결과 반환 JSON 스키마, 5. LLM 오케스트레이션 프로토콜 (`pipeline_runner.py` 연동 규격) (+12 more)

### Community 9 - "AGENTS.md — 다중 AI 협업 운영 규약 (Antigravity & Claude Code with orchestra-kit)"
Cohesion: 0.15
Nodes (12): 0. 다중 AI 협업 대원칙, 1. 3대 역할 분담 매트릭스, 2. Tier 판정 (오케스트레이터의 작업 분기), 3. 표준 협업 흐름 (Propose → Build → Probe → Compose), 4.1 외과수술적 컨텍스트 스코핑 (Graphify-First Gate), 4.2 작업 패킷 명세 (`.orchestra/tasks/<ID>.toml`), 4. Graphify-First 맥락 절약 및 작업 패킷 규칙, 5. 최종 검수 기준표 (Fail-Closed) (+4 more)

### Community 10 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.10
Nodes (19): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+11 more)

### Community 11 - "AGENTS.md — 다중 AI 협업 운영 규약 (Antigravity & Claude Code with orchestra-kit)"
Cohesion: 0.15
Nodes (12): 0. 다중 AI 협업 대원칙, 1. 3대 역할 분담 매트릭스, 2. Tier 판정 (오케스트레이터의 작업 분기), 3. 표준 협업 흐름 (Propose → Build → Probe → Compose), 4.1 외과수술적 컨텍스트 스코핑 (Graphify-First Gate), 4.2 작업 패킷 명세 (`.orchestra/tasks/<ID>.toml`), 4. Graphify-First 맥락 절약 및 작업 패킷 규칙, 5. 최종 검수 기준표 (Fail-Closed) (+4 more)

### Community 12 - ".resolve_domain_tool"
Cohesion: 0.16
Nodes (8): 1. 📌 프로젝트 개요 (Overview), 4. 📂 주요 디렉터리 및 핵심 파일 구조, 🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide), 핵심 기능 매트릭스, 4.4. 채팅, build_gbnf_tool_grammar(), test_guide_grammar_gives_each_tool_only_its_own_argument(), test_step2_rejects_a_call_with_another_tools_arguments()

### Community 13 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.13
Nodes (14): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+6 more)

### Community 14 - "EmbeddedLLMRunner"
Cohesion: 0.07
Nodes (27): 3. 💻 개발 환경 요구사항 및 빠른 시작 (Quick Start), 실행 및 검증 명령어, 요구사항, 4.1. 앱과 런타임, CodexSheetImporter, DataIngestor, assign_kill_on_close_job(), _BasicLimitInformation (+19 more)

### Community 15 - "DesktopPet"
Cohesion: 0.19
Nodes (3): DesktopPet, test_desktop_pet_layered_renderer_integration(), test_layered_pet_renderer_headless()

### Community 16 - "test_guide_search.py"
Cohesion: 0.07
Nodes (16): add(), _parse_item(), doc_titles(), drops(), orc(), retriever(), test_covered_questions_find_their_doc(), test_drop_answers_name_the_item() (+8 more)

### Community 17 - "1. 데미지 버킷 분류 (Damage Buckets)"
Cohesion: 0.14
Nodes (13): 01. Warframe Damage Formulas & Buckets, 1. 데미지 버킷 분류 (Damage Buckets), 2. 치명타 티어 수식 (Critical Tiers), 3. 최종 기대 직격 타격 데미지 공식, Bucket 1: Base Damage ($B$), Bucket 2: Additive Base Damage Multiplier ($M_{\text{base}}$), Bucket 3: Elemental Damage Multiplier ($M_{\text{elem}}$), Bucket 4: Faction Damage Multiplier ($M_{\text{faction}}$) (+5 more)

### Community 18 - "2. 상태이상 메커니즘 (Status Effects)"
Cohesion: 0.17
Nodes (11): 02. Warframe Enemy Scaling & Status Effects (Post-Jade Shadows Spec), 1.1. 체력 및 실드 스케일링, 1.2. 방어력 개편 (Update 36: Armor Cap at 2,700), 1. 적 레벨 스케일링 공식 (Enemy Scaling), 2.1. 바이러스 (Viral), 2.2. 절단 (Slash DoT - Bleed), 2.3. 화염 (Heat DoT - Ignite), 2.4. 부식 (Corrosive) (+3 more)

### Community 20 - "04. Warframe External Synergy & Level-Cap Matrix"
Cohesion: 0.20
Nodes (9): 04. Warframe External Synergy & Level-Cap Matrix, 1.1. 방어력/실드 무력화 (Armor Strip), 1.2. 화력 증폭 버프, 1. 헬민스 주입 어빌리티 (Helminth Subsumed Abilities), 2. 합성 집정관 파편 (Archon Shards Synergy), 3.1. 동반자 상태이상 프라이머 (Companion Primer), 3.2. 갈바니즈드 앱티튜드/샷/새비 (GunCO) 수학, 3. 동반자 프라이밍 & 갈바니즈드 GunCO 연계 (+1 more)

### Community 21 - "워프레임 성계 지도 기본 미션 유형 가이드 (Star Chart Mission Types)"
Cohesion: 0.20
Nodes (9): 1. 생존 미션 (Survival), 2. 이동방어 미션 (Mobile Defense), 3. 방어 미션 (Defense), 4. 섬멸 미션 (Exterminate), 5. 포획 미션 (Capture), 6. 첩보 / 도청 미션 (Spy), 7. 구출 미션 (Rescue), 8. 감청 미션 (Interception) (+1 more)

### Community 22 - "RivenRollEditDialog"
Cohesion: 0.24
Nodes (5): RivenCompareDialog, RivenRollEditDialog, test_compare_dialog_lists_rows(), test_roll_edit_dialog(), test_all_popup_dialogs_frameless()

### Community 23 - "03. Warframe Survivability & Shield Gating Rules"
Cohesion: 0.22
Nodes (8): 03. Warframe Survivability & Shield Gating Rules, 1.1. 다중 피해 감소 중첩 공식, 1. 실효 체력 (Effective Health Points - EHP), 2.1. 적 공격력 스케일링 수식, 2. 적 공격력 스케일링과 단순 체력 모딩의 한계, 3.1. 무적 시간 스케일링, 3.2. 카탈라이징 실즈 (Catalyzing Shields) 사이클, 3. 실드 게이팅 메커니즘 (Post-Abyss of Dagath Spec)

### Community 24 - "/harness"
Cohesion: 0.25
Nodes (7): 1. When `/harness init` or "하네스 초기화/설정" is requested:, 2. When `/harness probe` or "프로브 실행/검증" is requested:, 3. When `/harness record` or "경험 기록" is requested:, Capabilities, /harness, Instructions for Agents When Invoked, Mandatory Engineering Directives

### Community 25 - "Engineering Guardrails (Global Standards)"
Cohesion: 0.29
Nodes (6): 1. Zero Conversational Filler (무소음 원칙), 2. Graphify & AST-First Mandate (토큰 예산 방어), 3. Think Before Coding & Simplicity First, 4. Surgical Changes (정밀한 외과적 수정), 5. Non-Stop Propose-Probe-Compose Lifecycle, Engineering Guardrails (Global Standards)

### Community 26 - "Global Multi-Agent Harness Directive (Universal System Prompt)"
Cohesion: 0.29
Nodes (6): 0. Global Execution Directives (무소음 & 토큰 방어), 1. Multi-Agent RBAC Matrix (권한 격리), 2. Universal 3-Tier State Architecture, 3. Harness² Recursive Engineering Lifecycle, Global Multi-Agent Harness Directive (Universal System Prompt), Inter-Agent Communication Protocol

### Community 27 - "Engineering Guardrails (Global Standards)"
Cohesion: 0.29
Nodes (6): 1. Zero Conversational Filler (무소음 원칙), 2. Graphify & AST-First Mandate (토큰 예산 방어), 3. Think Before Coding & Simplicity First, 4. Surgical Changes (정밀한 외과적 수정), 5. Non-Stop Propose-Probe-Compose Lifecycle, Engineering Guardrails (Global Standards)

### Community 28 - "Global Engineering Experience Library (Harness² Cross-Project Knowledge)"
Cohesion: 0.33
Nodes (5): G-EXP-001: Windows 환경 파일 입출력 시 한글 인코딩 깨짐 방지, G-EXP-002: SQLite 동시성 락 및 Foreign Keys PRAGMA 누락 방지, G-EXP-003: Subprocess 실행 컨텍스트와 sys.path 의존성, G-EXP-004: DOM/XML 기반 문서 조작 시 정규식 파괴 방지, Global Engineering Experience Library (Harness² Cross-Project Knowledge)

### Community 29 - "워프레임 실전 메타 무기 티어 및 주요 컨텐츠 추천 장비 (Update 36 이후 최신 기준)"
Cohesion: 0.33
Nodes (5): 근접무기 0티어 추천 (Melee Weapons - Update 36 이후 메타), 보조무기 0티어 추천 (Secondary Weapons), 워프레임 실전 메타 무기 티어 및 주요 컨텐츠 추천 장비 (Update 36 이후 최신 기준), 주무기 0티어 추천 (Primary Weapons), 컨텐츠별 추천 워프레임 및 장비 요약

### Community 30 - "scripts/orchestra.py"
Cohesion: 0.08
Nodes (49): added_lines_from_diff(), after_review(), build_round(), bullets(), cmd_check(), cmd_clean(), cmd_init(), cmd_merge() (+41 more)

### Community 31 - "WorldStateTracker"
Cohesion: 0.07
Nodes (38): 5. ⚠️ 유지보수 주의사항 (Gotchas), Step 2: 동적 도구 필터링 & GBNF 문법 조립 (`select_domain_tools`, `resolve_domain_tool`), 감정/강도 + 대화 분리 출력을 위한 프리픽스 GBNF (`CHAT_MOOD_GRAMMAR`), 4.5. 월드 상태와 숙제, fetch_and_update(), write_json_atomic(), cetus_estimate(), format_remaining() (+30 more)

### Community 32 - "Domain Context & Architecture Memory (Warframe Companion)"
Cohesion: 0.40
Nodes (4): 1. Core Architecture Overview, 2. Key Entities & Data Models, 3. Communication & Integration, Domain Context & Architecture Memory (Warframe Companion)

### Community 33 - "Propose–Probe–Compose Workflow Protocol (Harness² Standard)"
Cohesion: 0.40
Nodes (4): Phase 1. Propose (가설 및 후보안 수립), Phase 2. Probe (격리 검증 및 스모크 테스트), Phase 3. Compose (최적안 채택 및 지식 누적), Propose–Probe–Compose Workflow Protocol (Harness² Standard)

### Community 34 - "Project Accumulated Experience Library (Harness² Recursion)"
Cohesion: 0.18
Nodes (10): [2026-11-07] UI/UX 2도 HUD 글리프 및 고무줄 텐션 모핑 버튼 전면 도입 (T-UI-1 ~ T-UI-3), EXP-001: Embedded Python과 시스템 Python 간 패키지 격리 및 Pytest 탐색 충돌 방지, EXP-002: Windows 환경 한글 인코딩 및 파일 입출력 안전성, EXP-003: Harness 초기 구축 및 3대 게이트 검증 연동, EXP-004: 패널 총계와 위키 수식 대조, EXP-005: 테스트가 실제 사용자 환경을 건드림, EXP-006: 계산식 보기 버튼 클릭 시 앱 종료, EXP-007: 긴 대화에서 공략 답변이 원문 나열로 바뀜 (+2 more)

### Community 35 - "Multi-Agent Orchestration & RBAC Guidelines"
Cohesion: 0.40
Nodes (4): 1. Multi-Agent Roles (Strict RBAC), 2. Inter-Agent Communication Protocol (`@[AGENT_PACKET]`), 3. Atomic Commit Policy, Multi-Agent Orchestration & RBAC Guidelines

### Community 36 - "Domain Context & Architecture Memory"
Cohesion: 0.40
Nodes (4): 1. Core Architecture Overview, 2. Key Entities & Data Models, 3. Communication & Integration, Domain Context & Architecture Memory

### Community 37 - "Propose–Probe–Compose Workflow Protocol (Harness² Standard)"
Cohesion: 0.40
Nodes (4): Phase 1. Propose (가설 및 후보안 수립), Phase 2. Probe (격리 검증 및 스모크 테스트), Phase 3. Compose (최적안 채택 및 지식 누적), Propose–Probe–Compose Workflow Protocol (Harness² Standard)

### Community 38 - "test_riven_recovery.py"
Cohesion: 0.12
Nodes (18): is_riven_name(), slot_order(), looks_like_riven_card(), analyzer(), qapp(), scan(), shared_analyzer(), test_codex_riven_entries_are_not_mod_candidates() (+10 more)

### Community 39 - "Domain & State Architecture Guardrails (Warframe Companion)"
Cohesion: 0.50
Nodes (3): 1. 3-Tier State Management Architecture, 2. Hard Domain Verification Gates, Domain & State Architecture Guardrails (Warframe Companion)

### Community 40 - "Domain & State Architecture Guardrails"
Cohesion: 0.50
Nodes (3): 1. 3-Tier State Management Architecture, 2. Hard Domain Verification Gates, Domain & State Architecture Guardrails

### Community 41 - "Project Progress & Verification Board"
Cohesion: 0.50
Nodes (3): 1. Phase Status Overview, 2. Active Inter-Agent Packets, Project Progress & Verification Board

### Community 42 - "Project Progress & Verification Board (Warframe Companion)"
Cohesion: 0.50
Nodes (3): 1. Phase Status Overview, 2. Active Inter-Agent Packets, Project Progress & Verification Board (Warframe Companion)

### Community 48 - "test_build_chat_and_dialogs.py"
Cohesion: 0.11
Nodes (16): format_change(), last_bubble_buttons(), orc(), panel(), qapp(), scan(), shared_analyzer(), test_confirming_review_saves_build() (+8 more)

### Community 49 - "os"
Cohesion: 0.19
Nodes (3): get_path(), get_user_data_path(), PathConfig

### Community 50 - "test_companion_app.py"
Cohesion: 0.10
Nodes (12): qimage_to_pil(), render_chat_markup(), drain(), panel(), qapp(), test_failed_llm_start_is_reported_in_chat(), test_llm_ready_is_announced_in_chat(), test_markup_escapes_html() (+4 more)

### Community 51 - "test_elements.py"
Cohesion: 0.12
Nodes (23): combine_elements(), faction_multipliers(), breakdown(), idx(), test_faction_multiplier(), test_four_primaries_two_pairs(), test_game_panel_types(), test_innate_electricity_key_combines() (+15 more)

### Community 52 - "ScreenModAnalyzer"
Cohesion: 0.14
Nodes (3): ScreenModAnalyzer, test_real_riven_flow_with_element_opens_dialog(), test_screen_mod_analyzer_diagnosis()

### Community 53 - "PersonaManager"
Cohesion: 0.09
Nodes (9): OrdisPersonaDialog, PersonaManager, test_orchestrator_integration(), test_persona_dialog_headless(), test_persona_manager_defaults(), test_persona_manager_modes_and_persistence(), test_persona_manager_random_mode(), test_settings_dialog_frameless_and_assets() (+1 more)

### Community 54 - "DropIndex"
Cohesion: 0.19
Nodes (5): _chance_text(), DropIndex, _rotated(), test_catalog_names_reach_the_drop_lookup(), test_relic_availability_comes_from_current_drop_tables()

### Community 55 - "pytest"
Cohesion: 0.21
Nodes (14): damage_engine(), firearm(), test_expected_between_min_and_max(), test_faction_applies_to_all_rolls(), test_modded_multishot_scales_without_panel(), test_optional_sections_only_with_data(), test_panel_total_already_includes_multishot(), test_riven_crit_adds_to_panel() (+6 more)

### Community 56 - "ShortTermMemory"
Cohesion: 0.24
Nodes (5): 단기 대화 기억 (`ShortTermMemory`)과의 조화 및 충돌 방지 설계, ShortTermMemory, test_long_conversations_leave_room_for_the_guide_context(), test_short_term_memory_keyword_extraction(), test_short_term_memory_sliding_window_and_budget()

### Community 57 - "test_chat_routing_comprehensive.py"
Cohesion: 0.15
Nodes (6): orchestrator(), test_chat_disruption_guide(), test_chat_mobile_defense_guide(), test_chat_plan_intent_sortie(), test_chat_status_check(), test_chat_survival_mission_guide()

### Community 58 - "test_mod_matching.py"
Cohesion: 0.26
Nodes (10): analyzer(), names(), test_exclusive_mods_stay_exclusive(), test_mods_also_sold_by_conclave_are_not_pvp(), test_rifle_mods_allowed_on_snipers_and_bows(), test_thrown_melee_mods_allowed_on_glaives(), test_top_match_from_real_ocr(), test_weapon_augment_kept_when_weapon_is_only_inferred() (+2 more)

### Community 59 - "🌌 WF-Companion (세팔론 오디스 데스크톱 어시스턴트)"
Cohesion: 0.29
Nodes (6): 1. 핵심 철학, 2. 기술 스택, 3. 디렉토리 구조, 5. 검증, 6. 알려진 한계, 🌌 WF-Companion (세팔론 오디스 데스크톱 어시스턴트)

### Community 60 - "test_chat_intent.py"
Cohesion: 0.15
Nodes (15): intent(), llm_offline(), orc(), test_casual_messages_are_smalltalk(), test_chat_asks_before_adding_or_deleting(), test_chat_falls_back_to_smalltalk_when_the_todo_names_nothing(), test_chat_ticks_an_existing_item_for_a_todo_message(), test_common_words_do_not_match_weapons() (+7 more)

### Community 61 - "test_ocr_benchmark.py"
Cohesion: 0.29
Nodes (7): mod_matched(), normalize_mod(), stat_matches(), test_high_res_panel_stats(), test_mod_recall(), test_panel_stats(), test_unnameable_weapon_is_not_guessed()

### Community 62 - "GameDataUpdater"
Cohesion: 0.19
Nodes (4): check(), DataValidationError, GameDataUpdater, _load_list()

### Community 63 - "RivenQuickInputDialog"
Cohesion: 0.31
Nodes (4): RivenQuickInputDialog, test_quick_input_curse_is_negative(), test_quick_input_values_are_percents(), test_riven_quick_input_dialog_and_shorthand()

### Community 64 - "test_game_data.py"
Cohesion: 0.13
Nodes (10): orc(), retriever(), snapshot(), test_any_failure_changes_no_files(), test_catalog_joins_korean_and_english_by_unique_name(), test_clean_text_handles_game_markup(), test_everyday_words_get_no_card(), test_mods_arcanes_and_resources_have_cards() (+2 more)

### Community 65 - "game_catalog.py"
Cohesion: 0.33
Nodes (8): build_catalog(), add(), english_names(), clean_text(), _ranked_entry(), _rounded(), _warframe_entry(), _weapon_entry()

### Community 66 - "test_saved_builds.py"
Cohesion: 0.12
Nodes (23): BuildStore, analyzer(), card(), scan_result(), shared_analyzer(), test_adopt_new_roll_updates_build_and_next_compare_starts_from_it(), test_adopt_without_build_explains(), test_build_without_riven_uses_first_empty_slot() (+15 more)

### Community 67 - "WarframeDamageEngine"
Cohesion: 0.19
Nodes (13): 4.2.1. 빌드 저장과 리벤 리롤 비교, 4.3. 데미지 계산, 4. 핵심 모듈, WarframeDamageEngine, test_engine_physical_bucket(), test_full_stack_melee_blood_rush(), test_full_stack_merciless_additive(), test_elemental_and_base_damage_buckets() (+5 more)

### Community 68 - "orchestra.py"
Cohesion: 0.09
Nodes (47): added_lines_from_diff(), after_review(), build_round(), bullets(), cmd_check(), cmd_clean(), cmd_init(), cmd_merge() (+39 more)

### Community 69 - "test_damage_formulas.py"
Cohesion: 0.10
Nodes (23): arsenal_total(), average_crit_mult(), bleed_tick(), effective_fire_rate(), enemy_armor_dr(), shooting_proportion(), total_crit_chance(), total_crit_mult() (+15 more)

### Community 70 - "FakeServer"
Cohesion: 0.27
Nodes (8): fake_item(), FakeServer, test_check_only_reads_version_markers_and_sees_changes(), test_check_runs_once_a_day(), test_export_with_raw_line_breaks_is_accepted(), test_old_korean_entries_survive_and_archwing_tag_is_removed(), test_shrunken_download_is_refused(), updater_for()

### Community 71 - ".add_chat_bubble"
Cohesion: 0.18
Nodes (3): diagnose_in_background(), get_response(), test_app_shows_riven_input_after_slot_edit()

### Community 72 - "app_server.py"
Cohesion: 0.20
Nodes (3): OptimizerHTTPHandler, run_server(), start_llama_server()

### Community 73 - "BuildEditDialog"
Cohesion: 0.29
Nodes (3): BuildEditDialog, test_edit_dialog_rejects_unknown_names(), test_edit_dialog_shows_and_returns_slots()

### Community 74 - "sys"
Cohesion: 0.23
Nodes (6): main(), run_domain_sanity(), run_graph_check(), run_tests(), append_experience(), append_experience()

### Community 75 - "decompress_index"
Cohesion: 0.20
Nodes (5): decompress_index(), parse_index(), index_bytes(), test_index_decompresses_the_official_format(), test_index_maps_export_names_to_current_files()

### Community 76 - "MorphingTabBar"
Cohesion: 0.13
Nodes (8): render_glyph(), MorphingTabBar, _make_bar(), qapp(), test_add_tab_with_icons(), test_backward_switch_leads_with_left_edge(), test_indicator_settles_on_target(), test_switch_tab_emits_signal()

### Community 77 - "orchestra-kit/orchestra.py"
Cohesion: 0.10
Nodes (47): added_lines_from_diff(), after_review(), build_round(), bullets(), cmd_check(), cmd_clean(), cmd_init(), cmd_merge() (+39 more)

### Community 78 - "HudButton"
Cohesion: 0.09
Nodes (11): HudButton, _lerp(), load_icon_pixmap(), _mix(), qapp(), test_busy_starts_and_stops_timer(), test_clicked_signal(), test_compact_size_hint_is_32() (+3 more)

### Community 79 - "screen_mod_analyzer.py"
Cohesion: 0.10
Nodes (6): set_bonus(), test_finisher_damage_not_confused_with_base_damage(), analyzer(), test_fullscreen_warframe_diagnosis(), test_tight_crop_8_cards_miter(), test_tight_crop_with_chat_resumption()

### Community 80 - "test_damage_breakdown_dialog.py"
Cohesion: 0.14
Nodes (12): DamageBreakdownDialog, handle_uncaught_exception(), card(), qapp(), rows(), test_copy_button_copies_selection(), test_copy_without_selection_copies_breakdown_text(), test_riven_options_never_break_the_table() (+4 more)

### Community 81 - "WFDataIndexer"
Cohesion: 0.16
Nodes (4): 4.2. 스크린샷 진단, WFDataIndexer, test_warframe_and_tricky_weapon_indexing(), test_wfcd_korean_name_indexing()

### Community 82 - "test_innate_traits.py"
Cohesion: 0.15
Nodes (18): parse_bonus_answer(), analyzer(), ix(), mods(), motovore(), scan(), test_asks_for_the_bonus_and_applies_the_answer(), test_bonus_answers_are_read() (+10 more)

### Community 83 - "GuideRetriever"
Cohesion: 0.25
Nodes (4): _compact(), _grams(), GuideRetriever, test_docs_reload_when_a_file_appears()

### Community 85 - "innate_traits.py"
Cohesion: 0.26
Nodes (8): apply_innate_traits(), bonus_in(), describe(), is_adversary(), load_traits(), selected_wheel(), trait_for(), test_adversary_weapons_are_recognised()

### Community 86 - "generate_ui_assets.py"
Cohesion: 0.24
Nodes (6): build_all(), ensure_dirs(), generate_btn_cancel(), generate_btn_save(), generate_ordis_logo(), generate_settings_icon()

### Community 87 - "AGENTS.md — 다중 AI 개발 운영 규약 (범용)"
Cohesion: 0.15
Nodes (12): 0. 대원칙, 1. 역할, 2. Tier 판정 (오케스트레이터가 작업 시작 전에), 3. 표준 흐름 (Propose → Build → Probe → Compose), 4. 작업 패킷 작성 규칙 (`.orchestra/tasks/<ID>.toml`), 5. 최종 검수 기준표 (모든 검수자 공통), 6. 서킷 브레이커와 한도, 7. 맥락 절약 규칙 (+4 more)

### Community 88 - "test_emotion_animation.py"
Cohesion: 0.28
Nodes (7): EmotionParser, _make_renderer(), test_emotion_parser_fallback_inference(), test_emotion_parser_standard_tags(), test_glitch_jitter_offset(), test_hand_offsets_differ_left_right(), test_talking_gesture_offset_active()

### Community 91 - "decompose_hangul"
Cohesion: 0.35
Nodes (3): decompose_hangul(), match_mods_jamo(), smart_match()

### Community 93 - "results"
Cohesion: 0.20
Nodes (5): test_interactive_weapon_clarification(), test_orchestrator_interactive_chat_routing(), test_supporter_bot_upgrades(), results(), analyzer()

### Community 94 - "GameCatalog"
Cohesion: 0.27
Nodes (3): _compact(), GameCatalog, test_shipped_catalog_has_each_kind_with_korean_text()

### Community 95 - "orchestra-kit"
Cohesion: 0.22
Nodes (8): orchestra-kit, 디스패처가 강제하는 것, 사용, 설정에서 꼭 바꿀 세 곳 (`.orchestra/orchestra.toml`), 설치, 알려진 한계와 확인할 것, 역할 배치 예시, 운영 모드

### Community 98 - "build_character_assets.py"
Cohesion: 0.67
Nodes (4): build_all(), make_blank(), overlay_rgba(), save_scaled()

### Community 100 - "🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide)"
Cohesion: 0.33
Nodes (5): 1. 📐 에셋 기본 규격, 2. 📂 디렉터리 및 파일 명명 규칙, 3. 🍌 나노바나나 (NanoBanana) 생성 프롬프트 템플릿 추천, 4. 🛡️ 자동 폴백 (안전망), 🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide)

### Community 101 - "🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide)"
Cohesion: 0.33
Nodes (5): 1. 📐 에셋 기본 규격, 2. 📂 디렉터리 및 파일 명명 규칙, 3. 🍌 나노바나나 (NanoBanana) 생성 프롬프트 템플릿 추천, 4. 🛡️ 자동 폴백 (안전망), 🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide)

### Community 102 - "2. 🧠 [핵심 아키텍처] 1-Token GBNF 도메인 분류 & 동적 도구 문법 파이프라인"
Cohesion: 0.40
Nodes (4): 2. 🧠 [핵심 아키텍처] 1-Token GBNF 도메인 분류 & 동적 도구 문법 파이프라인, Step 1: 1-Token 도메인 분류 (`LLMOrchestrator.classify_intent`), 신규 도메인/도구 확장 방법 (인수인계 가이드), 파이프라인 흐름도

### Community 103 - "review.md"
Cohesion: 0.40
Nodes (4): Diff ({{DIFF_STATS}}), Gate results, Output, Rubric

## Knowledge Gaps
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ScreenModAnalyzer` connect `ScreenModAnalyzer` to `desktop_companion.py`, `OrdisCompanionApp`, `LLMOrchestrator`, `test_riven_recovery.py`, `test_build_chat_and_dialogs.py`, `test_mod_matching.py`, `test_ocr_benchmark.py`, `test_saved_builds.py`, `WarframeDamageEngine`, `.add_chat_bubble`, `screen_mod_analyzer.py`, `test_damage_breakdown_dialog.py`, `WFDataIndexer`, `test_innate_traits.py`, `YOLOSlotDetector`, `decompose_hangul`, `results`, `.open_build_editor`, `.extract_left_panel_stats`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `ScreenModAnalyzer` (e.g. with `4.2. 스크린샷 진단` and `OrdisCompanionApp`) actually correct?**
  _`ScreenModAnalyzer` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Should `OrdisCompanionApp` be split into smaller, more focused modules?**
  _Cohesion score 0.09309309309309309 - nodes in this community are weakly interconnected._
- **Why does `LLMOrchestrator` connect `LLMOrchestrator` to `desktop_companion.py`, `json`, `OrdisCompanionApp`, `.resolve_domain_tool`, `EmbeddedLLMRunner`, `test_guide_search.py`, `WorldStateTracker`, `test_build_chat_and_dialogs.py`, `os`, `PersonaManager`, `DropIndex`, `ShortTermMemory`, `test_chat_routing_comprehensive.py`, `test_chat_intent.py`, `GameDataUpdater`, `test_game_data.py`, `test_saved_builds.py`, `app_server.py`, `screen_mod_analyzer.py`, `test_innate_traits.py`, `GuideRetriever`, `test_emotion_animation.py`, `results`, `2. 🧠 [핵심 아키텍처] 1-Token GBNF 도메인 분류 & 동적 도구 문법 파이프라인`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `OrdisCompanionApp` (e.g. with `4.1. 앱과 런타임` and `BuildEditDialog`) actually correct?**
  _`OrdisCompanionApp` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Should `LocalPipelineRunner` be split into smaller, more focused modules?**
  _Cohesion score 0.08350951374207188 - nodes in this community are weakly interconnected._
- **Why does `OrdisCompanionApp` connect `OrdisCompanionApp` to `desktop_companion.py`, `LLMOrchestrator`, `EmbeddedLLMRunner`, `RivenRollEditDialog`, `WorldStateTracker`, `test_riven_recovery.py`, `test_build_chat_and_dialogs.py`, `test_companion_app.py`, `ScreenModAnalyzer`, `PersonaManager`, `GameDataUpdater`, `RivenQuickInputDialog`, `.add_chat_bubble`, `BuildEditDialog`, `MorphingTabBar`, `HudButton`, `test_damage_breakdown_dialog.py`, `ChatBubble`, `.open_build_editor`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._