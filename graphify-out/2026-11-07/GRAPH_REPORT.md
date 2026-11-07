# Graph Report - 2.7 WarframeOptimizer  (2026-11-06)

## Corpus Check
- 159 files · ~854,796 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: .csv 8, (none) 3, .bat 2)

## Summary
- 1475 nodes · 3438 edges · 80 communities (67 shown, 13 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 360 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e0e8c3c7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- desktop_companion.py
- os
- OrdisCompanionApp
- LLMOrchestrator
- LocalPipelineRunner
- optimizer_engine.py
- screen_mod_analyzer.py
- probe.mjs
- Project Specification: Warframe Build & Synergy Optimizer (WF-Optimizer)
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- build_gbnf_tool_grammar
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- EmbeddedLLMRunner
- LayeredPetRenderer
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
- DataIngestor
- WorldStateTracker
- Domain Context & Architecture Memory (Warframe Companion)
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- Project Accumulated Experience Library (Harness² Recursion)
- Multi-Agent Orchestration & RBAC Guidelines
- Domain Context & Architecture Memory
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- BuildStore
- Domain & State Architecture Guardrails (Warframe Companion)
- Domain & State Architecture Guardrails
- Project Progress & Verification Board
- Project Progress & Verification Board (Warframe Companion)
- Project Accumulated Experience Library (Harness² Recursion)
- test_build_chat_and_dialogs.py
- llm_orchestrator.py
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
- test_riven_diagnosis_workflow.py
- test_game_data.py
- game_catalog.py
- test_saved_builds.py
- WarframeDamageEngine
- scripts/probe.py
- test_damage_formulas.py
- FakeServer
- .add_chat_bubble
- app_server.py
- BuildEditDialog
- re
- decompress_index
- MorphingTabBar
- main
- CodexSheetImporter
- test_formula_vs_game.py

## God Nodes (most connected - your core abstractions)
1. `ScreenModAnalyzer` - 86 edges
2. `OrdisCompanionApp` - 68 edges
3. `LLMOrchestrator` - 63 edges
4. `WarframeDamageEngine` - 39 edges
5. `WFDataIndexer` - 36 edges
6. `WorldStateTracker` - 33 edges
7. `BuildStore` - 32 edges
8. `EmbeddedLLMRunner` - 31 edges
9. `GuideRetriever` - 26 edges
10. `get_path()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `Phase 2: 정밀 데미지 및 TTK 시뮬레이터 (`scripts/damage_simulator.py`)` --references--> `CombatState`  [INFERRED]
  warframe.md → scripts/damage_simulator.py
- `4.2.1. 빌드 저장과 리벤 리롤 비교` --references--> `BuildStore`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/build_store.py
- `4.1. 앱과 런타임` --references--> `render_chat_markup()`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/desktop_companion.py
- `4.1. 앱과 런타임` --references--> `DesktopPet`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/desktop_companion.py
- `4.1. 앱과 런타임` --references--> `ChatBubble`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/desktop_companion.py

## Import Cycles
- None detected.

## Communities (80 total, 13 thin omitted)

### Community 1 - "os"
Cohesion: 0.13
Nodes (4): write_json_atomic(), _http_get(), test_daily_reset_keeps_weekly_done(), test_old_integer_week_key_does_not_reset_same_week()

### Community 2 - "OrdisCompanionApp"
Cohesion: 0.14
Nodes (6): OrdisCompanionApp, fetch_and_update(), check_hotkeys(), test_ordis_companion_headless_and_tabs(), test_capture_fullscreen_execution(), test_capture_fullscreen_methods_exist()

### Community 3 - "LLMOrchestrator"
Cohesion: 0.14
Nodes (9): OptimizerHTTPHandler, LLMOrchestrator, test_works_with_llm_server_off(), test_guide_prompt_uses_persona_text_not_raw_dict(), test_smalltalk_prompt_has_memory_and_mood_instruction(), test_orchestrator_chat_strips_tag_and_provides_mood(), test_orchestrator_cancels_pending_riven(), test_orchestrator_memory_mode_commands() (+1 more)

### Community 4 - "LocalPipelineRunner"
Cohesion: 0.08
Nodes (7): LocalPipelineRunner, main(), class_methods(), runner(), test_insert_goes_into_class_before_module_aliases(), test_insert_goes_into_last_class_before_main_guard(), test_module_without_class_inserts_top_level_function()

### Community 5 - "optimizer_engine.py"
Cohesion: 0.11
Nodes (21): CombatState, DamageSimulator, ModConfig, WeaponStats, OptimizerEngine, OptimizerRequest, SurvivalEvaluator, WarframeModConfig (+13 more)

### Community 6 - "screen_mod_analyzer.py"
Cohesion: 0.08
Nodes (22): test_boxes(), decompose_hangul(), match_mods_jamo(), _add_stat(), _bright_inverted(), format_riven_stats(), _gray(), looks_like_reroll_screen() (+14 more)

### Community 7 - "probe.mjs"
Cohesion: 0.10
Nodes (12): __filename, g1, g2, g3, ROOT_DIR, args, content, EXP_FILE (+4 more)

### Community 8 - "Project Specification: Warframe Build & Synergy Optimizer (WF-Optimizer)"
Cohesion: 0.10
Nodes (20): 1.1. 필수 달성 유스케이스 (Core Use Cases), 1. 프로젝트 개요 및 목표 (Project Overview & Goals), 2. 기술 스택 (Tech Stack), 3. 시스템 아키텍처 및 디렉토리 구조 (System Architecture), 4. 핵심 모듈별 상세 구현 방안 (Detailed Implementation Plan), 5.1. LLM -> Python 입력 JSON 스키마, 5.2. Python -> LLM 결과 반환 JSON 스키마, 5. LLM 오케스트레이션 프로토콜 (`pipeline_runner.py` 연동 규격) (+12 more)

### Community 9 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.10
Nodes (19): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Risk-Based Workload Partitioning, 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Test-First Verification & Circuit Breaker Protocol (+11 more)

### Community 10 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.10
Nodes (19): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+11 more)

### Community 11 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.10
Nodes (19): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Risk-Based Workload Partitioning, 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Test-First Verification & Circuit Breaker Protocol (+11 more)

### Community 12 - "build_gbnf_tool_grammar"
Cohesion: 0.13
Nodes (11): 1. 📌 프로젝트 개요 (Overview), 2. 🧠 [핵심 아키텍처] 1-Token GBNF 도메인 분류 & 동적 도구 문법 파이프라인, 4. 📂 주요 디렉터리 및 핵심 파일 구조, 5. ⚠️ 유지보수 주의사항 (Gotchas), Step 1: 1-Token 도메인 분류 (`LLMOrchestrator.classify_intent`), 🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide), 신규 도메인/도구 확장 방법 (인수인계 가이드), 파이프라인 흐름도 (+3 more)

### Community 13 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.13
Nodes (14): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+6 more)

### Community 14 - "EmbeddedLLMRunner"
Cohesion: 0.13
Nodes (22): 3. 💻 개발 환경 요구사항 및 빠른 시작 (Quick Start), 실행 및 검증 명령어, 요구사항, 4.1. 앱과 런타임, assign_kill_on_close_job(), close_job(), EmbeddedLLMRunner, _ExtendedLimitInformation (+14 more)

### Community 15 - "LayeredPetRenderer"
Cohesion: 0.07
Nodes (12): 1. 📐 에셋 기본 규격, 2. 📂 디렉터리 및 파일 명명 규칙, 3. 🍌 나노바나나 (NanoBanana) 생성 프롬프트 템플릿 추천, 4. 🛡️ 자동 폴백 (안전망), 🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide), DesktopPet, EmotionParser, LayeredPetRenderer (+4 more)

### Community 16 - "test_guide_search.py"
Cohesion: 0.06
Nodes (22): add(), _parse_item(), _compact(), _grams(), GuideRetriever, _split_long_section(), _strip_particle(), doc_titles() (+14 more)

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
Cohesion: 0.19
Nodes (4): RivenCompareDialog, RivenRollEditDialog, test_compare_dialog_lists_rows(), test_roll_edit_dialog()

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

### Community 31 - "WorldStateTracker"
Cohesion: 0.08
Nodes (35): Step 2: 동적 도구 필터링 & GBNF 문법 조립 (`select_domain_tools`, `resolve_domain_tool`), 4.5. 월드 상태와 숙제, cetus_estimate(), format_remaining(), format_seconds(), _parse_cetus(), _parse_duviri(), _parse_mission() (+27 more)

### Community 32 - "Domain Context & Architecture Memory (Warframe Companion)"
Cohesion: 0.40
Nodes (4): 1. Core Architecture Overview, 2. Key Entities & Data Models, 3. Communication & Integration, Domain Context & Architecture Memory (Warframe Companion)

### Community 33 - "Propose–Probe–Compose Workflow Protocol (Harness² Standard)"
Cohesion: 0.40
Nodes (4): Phase 1. Propose (가설 및 후보안 수립), Phase 2. Probe (격리 검증 및 스모크 테스트), Phase 3. Compose (최적안 채택 및 지식 누적), Propose–Probe–Compose Workflow Protocol (Harness² Standard)

### Community 34 - "Project Accumulated Experience Library (Harness² Recursion)"
Cohesion: 0.20
Nodes (9): EXP-001: Embedded Python과 시스템 Python 간 패키지 격리 및 Pytest 탐색 충돌 방지, EXP-002: Windows 환경 한글 인코딩 및 파일 입출력 안전성, EXP-003: Harness 초기 구축 및 3대 게이트 검증 연동, EXP-004: 패널 총계와 위키 수식 대조, EXP-005: 테스트가 실제 사용자 환경을 건드림, EXP-006: 계산식 보기 버튼 클릭 시 앱 종료, EXP-007: 긴 대화에서 공략 답변이 원문 나열로 바뀜, EXP-008: 자유 문장을 맡기면 모델이 근거 없는 조언을 지어냄 (+1 more)

### Community 35 - "Multi-Agent Orchestration & RBAC Guidelines"
Cohesion: 0.40
Nodes (4): 1. Multi-Agent Roles (Strict RBAC), 2. Inter-Agent Communication Protocol (`@[AGENT_PACKET]`), 3. Atomic Commit Policy, Multi-Agent Orchestration & RBAC Guidelines

### Community 36 - "Domain Context & Architecture Memory"
Cohesion: 0.40
Nodes (4): 1. Core Architecture Overview, 2. Key Entities & Data Models, 3. Communication & Integration, Domain Context & Architecture Memory

### Community 37 - "Propose–Probe–Compose Workflow Protocol (Harness² Standard)"
Cohesion: 0.40
Nodes (4): Phase 1. Propose (가설 및 후보안 수립), Phase 2. Probe (격리 검증 및 스모크 테스트), Phase 3. Compose (최적안 채택 및 지식 누적), Propose–Probe–Compose Workflow Protocol (Harness² Standard)

### Community 38 - "BuildStore"
Cohesion: 0.06
Nodes (35): BuildStore, canonical_slot(), is_riven_name(), slot_order(), DamageBreakdownDialog, looks_like_riven_card(), qapp(), rows() (+27 more)

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

### Community 49 - "llm_orchestrator.py"
Cohesion: 0.13
Nodes (5): _BasicLimitInformation, _IoCounters, get_path(), get_user_data_path(), PathConfig

### Community 50 - "test_companion_app.py"
Cohesion: 0.08
Nodes (14): ChatBubble, qimage_to_pil(), render_chat_markup(), drain(), panel(), qapp(), test_failed_llm_start_is_reported_in_chat(), test_llm_ready_is_announced_in_chat() (+6 more)

### Community 51 - "test_elements.py"
Cohesion: 0.10
Nodes (25): combine_elements(), effective_fire_rate(), faction_multipliers(), shooting_proportion(), test_effective_rate(), breakdown(), idx(), test_faction_multiplier() (+17 more)

### Community 52 - "ScreenModAnalyzer"
Cohesion: 0.05
Nodes (13): 4.2.1. 빌드 저장과 리벤 리롤 비교, 4.2. 스크린샷 진단, 4. 핵심 모듈, ScreenModAnalyzer, WFDataIndexer, YOLOSlotDetector, test_interactive_weapon_clarification(), test_orchestrator_interactive_chat_routing() (+5 more)

### Community 53 - "PersonaManager"
Cohesion: 0.21
Nodes (7): OrdisPersonaDialog, PersonaManager, test_orchestrator_integration(), test_persona_dialog_headless(), test_persona_manager_defaults(), test_persona_manager_modes_and_persistence(), test_persona_manager_random_mode()

### Community 54 - "DropIndex"
Cohesion: 0.23
Nodes (4): _chance_text(), DropIndex, _rotated(), test_relic_availability_comes_from_current_drop_tables()

### Community 55 - "pytest"
Cohesion: 0.17
Nodes (18): damage_engine(), firearm(), test_expected_between_min_and_max(), test_faction_applies_to_all_rolls(), test_modded_multishot_scales_without_panel(), test_optional_sections_only_with_data(), test_panel_total_already_includes_multishot(), test_riven_crit_adds_to_panel() (+10 more)

### Community 56 - "ShortTermMemory"
Cohesion: 0.28
Nodes (4): ShortTermMemory, test_long_conversations_leave_room_for_the_guide_context(), test_short_term_memory_keyword_extraction(), test_short_term_memory_sliding_window_and_budget()

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
Cohesion: 0.22
Nodes (9): intent(), llm_offline(), orc(), test_casual_messages_are_smalltalk(), test_common_words_do_not_match_weapons(), test_game_questions_are_guide(), test_player_slang_finds_archon_docs(), test_step1_gbnf_one_token_intent_classification() (+1 more)

### Community 61 - "test_ocr_benchmark.py"
Cohesion: 0.29
Nodes (7): mod_matched(), normalize_mod(), stat_matches(), test_high_res_panel_stats(), test_mod_recall(), test_panel_stats(), test_unnameable_weapon_is_not_guessed()

### Community 62 - "GameDataUpdater"
Cohesion: 0.16
Nodes (5): check(), DataValidationError, GameDataUpdater, _load_list(), test_wfcd_numbers_are_compared_with_the_official_ones()

### Community 63 - "test_riven_diagnosis_workflow.py"
Cohesion: 0.19
Nodes (5): RivenQuickInputDialog, test_quick_input_curse_is_negative(), test_quick_input_values_are_percents(), test_finisher_damage_not_confused_with_base_damage(), test_riven_quick_input_dialog_and_shorthand()

### Community 64 - "test_game_data.py"
Cohesion: 0.11
Nodes (13): parse_index(), orc(), retriever(), snapshot(), test_any_failure_changes_no_files(), test_catalog_joins_korean_and_english_by_unique_name(), test_catalog_names_reach_the_drop_lookup(), test_clean_text_handles_game_markup() (+5 more)

### Community 65 - "game_catalog.py"
Cohesion: 0.17
Nodes (11): build_catalog(), add(), english_names(), clean_text(), _compact(), GameCatalog, _ranked_entry(), _rounded() (+3 more)

### Community 66 - "test_saved_builds.py"
Cohesion: 0.16
Nodes (19): analyzer(), card(), scan_result(), shared_analyzer(), test_adopt_new_roll_updates_build_and_next_compare_starts_from_it(), test_adopt_without_build_explains(), test_build_without_riven_uses_first_empty_slot(), test_compare_verdict_uses_sustained_dps_with_magazine_roll() (+11 more)

### Community 67 - "WarframeDamageEngine"
Cohesion: 0.27
Nodes (11): 4.3. 데미지 계산, WarframeDamageEngine, test_engine_physical_bucket(), test_full_stack_melee_blood_rush(), test_full_stack_merciless_additive(), test_elemental_and_base_damage_buckets(), test_firearm_duty_cycle_sustained(), test_in_game_crit_tiers_and_rolls() (+3 more)

### Community 68 - "scripts/probe.py"
Cohesion: 0.18
Nodes (12): main(), run_domain_sanity(), run_graph_check(), run_tests(), average_crit_mult(), enemy_armor_dr(), main(), run_domain_sanity() (+4 more)

### Community 69 - "test_damage_formulas.py"
Cohesion: 0.14
Nodes (12): arsenal_total(), bleed_tick(), total_crit_chance(), total_crit_mult(), weak_point_multiplier(), idx(), _mod(), test_arsenal_total() (+4 more)

### Community 70 - "FakeServer"
Cohesion: 0.21
Nodes (10): format_report(), fake_item(), FakeServer, test_check_only_reads_version_markers_and_sees_changes(), test_check_runs_once_a_day(), test_export_with_raw_line_breaks_is_accepted(), test_old_korean_entries_survive_and_archwing_tag_is_removed(), test_shrunken_download_is_refused() (+2 more)

### Community 71 - ".add_chat_bubble"
Cohesion: 0.24
Nodes (3): diagnose_in_background(), get_response(), test_app_shows_riven_input_after_slot_edit()

### Community 72 - "app_server.py"
Cohesion: 0.19
Nodes (4): run_server(), start_llama_server(), setup_runtime(), pytest_sessionfinish()

### Community 73 - "BuildEditDialog"
Cohesion: 0.29
Nodes (3): BuildEditDialog, test_edit_dialog_rejects_unknown_names(), test_edit_dialog_shows_and_returns_slots()

### Community 75 - "decompress_index"
Cohesion: 0.33
Nodes (3): decompress_index(), index_bytes(), test_index_decompresses_the_official_format()

## Knowledge Gaps
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OrdisCompanionApp` connect `OrdisCompanionApp` to `desktop_companion.py`, `LLMOrchestrator`, `BuildStore`, `.add_chat_bubble`, `BuildEditDialog`, `MorphingTabBar`, `main`, `EmbeddedLLMRunner`, `LayeredPetRenderer`, `test_build_chat_and_dialogs.py`, `test_companion_app.py`, `ScreenModAnalyzer`, `PersonaManager`, `RivenRollEditDialog`, `WorldStateTracker`, `GameDataUpdater`, `test_riven_diagnosis_workflow.py`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `ScreenModAnalyzer` (e.g. with `4.2. 스크린샷 진단` and `OrdisCompanionApp`) actually correct?**
  _`ScreenModAnalyzer` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `os` be split into smaller, more focused modules?**
  _Cohesion score 0.12648221343873517 - nodes in this community are weakly interconnected._
- **Why does `ScreenModAnalyzer` connect `ScreenModAnalyzer` to `desktop_companion.py`, `OrdisCompanionApp`, `WarframeDamageEngine`, `LLMOrchestrator`, `test_saved_builds.py`, `BuildStore`, `screen_mod_analyzer.py`, `test_build_chat_and_dialogs.py`, `pytest`, `test_mod_matching.py`, `test_ocr_benchmark.py`, `test_riven_diagnosis_workflow.py`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `OrdisCompanionApp` (e.g. with `4.1. 앱과 런타임` and `BuildEditDialog`) actually correct?**
  _`OrdisCompanionApp` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Should `OrdisCompanionApp` be split into smaller, more focused modules?**
  _Cohesion score 0.14333333333333334 - nodes in this community are weakly interconnected._
- **Why does `LLMOrchestrator` connect `LLMOrchestrator` to `desktop_companion.py`, `OrdisCompanionApp`, `build_gbnf_tool_grammar`, `EmbeddedLLMRunner`, `LayeredPetRenderer`, `test_guide_search.py`, `BuildStore`, `test_build_chat_and_dialogs.py`, `llm_orchestrator.py`, `ScreenModAnalyzer`, `PersonaManager`, `DropIndex`, `ShortTermMemory`, `test_chat_routing_comprehensive.py`, `test_chat_intent.py`, `GameDataUpdater`, `test_riven_diagnosis_workflow.py`, `test_game_data.py`, `app_server.py`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._