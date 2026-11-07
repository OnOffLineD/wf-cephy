# Graph Report - 2.7 WarframeOptimizer  (2026-11-05)

## Corpus Check
- 155 files · ~1,314,889 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: .csv 8, (none) 3, .bat 2)

## Summary
- 1371 nodes · 3117 edges · 65 communities (55 shown, 10 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 317 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `57e15794`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- desktop_companion.py
- WFDataIndexer
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
- 🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide)
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- EmbeddedLLMRunner
- LayeredPetRenderer
- test_guide_search.py
- 1. 데미지 버킷 분류 (Damage Buckets)
- 2. 상태이상 메커니즘 (Status Effects)
- TodoPanel
- 04. Warframe External Synergy & Level-Cap Matrix
- 워프레임 성계 지도 기본 미션 유형 가이드 (Star Chart Mission Types)
- test_riven_reroll_reader.py
- 03. Warframe Survivability & Shield Gating Rules
- /harness
- Engineering Guardrails (Global Standards)
- Global Multi-Agent Harness Directive (Universal System Prompt)
- Engineering Guardrails (Global Standards)
- Global Engineering Experience Library (Harness² Cross-Project Knowledge)
- 워프레임 실전 메타 무기 티어 및 주요 컨텐츠 추천 장비 (Update 36 이후 최신 기준)
- DataIngestor
- test_world_state.py
- Domain Context & Architecture Memory (Warframe Companion)
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- Project Accumulated Experience Library (Harness² Recursion)
- Multi-Agent Orchestration & RBAC Guidelines
- Domain Context & Architecture Memory
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- test_saved_builds.py
- Domain & State Architecture Guardrails (Warframe Companion)
- Domain & State Architecture Guardrails
- Project Progress & Verification Board
- Project Progress & Verification Board (Warframe Companion)
- Project Accumulated Experience Library (Harness² Recursion)
- test_build_chat_and_dialogs.py
- riven_reroll_reader.py
- test_companion_app.py
- pytest
- ScreenModAnalyzer
- PersonaManager
- DropIndex
- test_screen_recognition_overhaul.py
- ShortTermMemory
- test_chat_routing_comprehensive.py
- test_mod_matching.py
- 4. 핵심 모듈
- test_chat_intent.py
- re
- decompose_hangul
- test_riven_diagnosis_workflow.py
- OptimizerHTTPHandler

## God Nodes (most connected - your core abstractions)
1. `ScreenModAnalyzer` - 86 edges
2. `OrdisCompanionApp` - 66 edges
3. `LLMOrchestrator` - 56 edges
4. `WarframeDamageEngine` - 39 edges
5. `WFDataIndexer` - 36 edges
6. `BuildStore` - 32 edges
7. `EmbeddedLLMRunner` - 30 edges
8. `WorldStateTracker` - 30 edges
9. `GuideRetriever` - 23 edges
10. `PersonaManager` - 22 edges

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

## Communities (65 total, 10 thin omitted)

### Community 0 - "desktop_companion.py"
Cohesion: 0.05
Nodes (27): main(), run_domain_sanity(), run_graph_check(), run_tests(), append_experience(), run_server(), start_llama_server(), DamageBreakdownDialog (+19 more)

### Community 1 - "WFDataIndexer"
Cohesion: 0.13
Nodes (5): WFDataIndexer, idx(), idx(), idx(), test_wfcd_korean_name_indexing()

### Community 2 - "OrdisCompanionApp"
Cohesion: 0.07
Nodes (11): main(), OrdisCompanionApp, diagnose_in_background(), fetch_and_update(), get_response(), check_hotkeys(), MorphingTabBar, test_ordis_companion_headless_and_tabs() (+3 more)

### Community 3 - "LLMOrchestrator"
Cohesion: 0.17
Nodes (6): LLMOrchestrator, test_works_with_llm_server_off(), test_guide_prompt_uses_persona_text_not_raw_dict(), test_smalltalk_prompt_has_memory_and_mood_instruction(), test_orchestrator_chat_strips_tag_and_provides_mood(), test_orchestrator_turn_memory_and_pronoun_enrichment()

### Community 4 - "LocalPipelineRunner"
Cohesion: 0.08
Nodes (7): LocalPipelineRunner, main(), class_methods(), runner(), test_insert_goes_into_class_before_module_aliases(), test_insert_goes_into_last_class_before_main_guard(), test_module_without_class_inserts_top_level_function()

### Community 5 - "optimizer_engine.py"
Cohesion: 0.12
Nodes (21): CombatState, DamageSimulator, ModConfig, WeaponStats, OptimizerEngine, OptimizerRequest, SurvivalEvaluator, WarframeModConfig (+13 more)

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

### Community 12 - "🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide)"
Cohesion: 0.11
Nodes (17): 1) Windows PowerShell 콘솔 한글 깨짐 방지, 1. 📌 프로젝트 개요 (Overview), 1단계: 가상환경 생성 및 의존성 설치, 2) Ollama 포트 충돌 (11434 포트), 2. 💻 새 PC 개발 환경 요구사항 (Prerequisites), 2단계: 로컬 LLM 확인, 3. 🚀 3단계 빠른 시작 (Quick Start), 3) 스탠드얼론 실행 시 GGUF 모델 다운로드 (+9 more)

### Community 13 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.13
Nodes (14): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+6 more)

### Community 14 - "EmbeddedLLMRunner"
Cohesion: 0.09
Nodes (23): 4.1. 앱과 런타임, CodexSheetImporter, assign_kill_on_close_job(), _BasicLimitInformation, close_job(), EmbeddedLLMRunner, _ExtendedLimitInformation, _IoCounters (+15 more)

### Community 15 - "LayeredPetRenderer"
Cohesion: 0.07
Nodes (12): 1. 📐 에셋 기본 규격, 2. 📂 디렉터리 및 파일 명명 규칙, 3. 🍌 나노바나나 (NanoBanana) 생성 프롬프트 템플릿 추천, 4. 🛡️ 자동 폴백 (안전망), 🎨 세팔론 오디스 의인화 레이어 에셋 제작 가이드 (NanoBanana / AI Image Guide), DesktopPet, EmotionParser, LayeredPetRenderer (+4 more)

### Community 16 - "test_guide_search.py"
Cohesion: 0.06
Nodes (21): add(), _parse_item(), _compact(), _grams(), GuideRetriever, _split_long_section(), _strip_particle(), doc_titles() (+13 more)

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

### Community 22 - "test_riven_reroll_reader.py"
Cohesion: 0.17
Nodes (10): RivenRollEditDialog, format_riven_stats(), looks_like_reroll_screen(), parse_riven_input(), test_roll_edit_dialog(), test_element_stat_also_counts_as_elemental_damage(), test_input_text_round_trips(), test_parse_stat_line_handles_ocr_noise() (+2 more)

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

### Community 31 - "test_world_state.py"
Cohesion: 0.07
Nodes (36): 4.5. 월드 상태와 숙제, write_json_atomic(), cetus_estimate(), format_remaining(), format_seconds(), _parse_cetus(), _parse_duviri(), _parse_mission() (+28 more)

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

### Community 38 - "test_saved_builds.py"
Cohesion: 0.07
Nodes (43): BuildStore, canonical_slot(), is_riven_name(), slot_order(), looks_like_riven_card(), analyzer(), qapp(), scan() (+35 more)

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
Cohesion: 0.06
Nodes (25): BuildEditDialog, format_change(), RivenCompareDialog, RivenQuickInputDialog, last_bubble_buttons(), orc(), panel(), qapp() (+17 more)

### Community 49 - "riven_reroll_reader.py"
Cohesion: 0.30
Nodes (9): _add_stat(), _bright_inverted(), _gray(), _match_label(), _ocr_lines(), parse_stat_line(), _read_card(), read_reroll_screen() (+1 more)

### Community 50 - "test_companion_app.py"
Cohesion: 0.08
Nodes (14): ChatBubble, qimage_to_pil(), render_chat_markup(), drain(), panel(), qapp(), test_failed_llm_start_is_reported_in_chat(), test_llm_ready_is_announced_in_chat() (+6 more)

### Community 51 - "pytest"
Cohesion: 0.05
Nodes (68): 4.3. 데미지 계산, arsenal_total(), average_crit_mult(), bleed_tick(), combine_elements(), effective_fire_rate(), enemy_armor_dr(), faction_multipliers() (+60 more)

### Community 52 - "ScreenModAnalyzer"
Cohesion: 0.07
Nodes (9): 4.2. 스크린샷 진단, ScreenModAnalyzer, YOLOSlotDetector, test_interactive_weapon_clarification(), test_orchestrator_interactive_chat_routing(), test_supporter_bot_upgrades(), results(), analyzer() (+1 more)

### Community 53 - "PersonaManager"
Cohesion: 0.21
Nodes (7): OrdisPersonaDialog, PersonaManager, test_orchestrator_integration(), test_persona_dialog_headless(), test_persona_manager_defaults(), test_persona_manager_modes_and_persistence(), test_persona_manager_random_mode()

### Community 54 - "DropIndex"
Cohesion: 0.20
Nodes (3): _chance_text(), DropIndex, _rotated()

### Community 55 - "test_screen_recognition_overhaul.py"
Cohesion: 0.29
Nodes (5): analyzer(), test_fullscreen_warframe_diagnosis(), test_tight_crop_8_cards_miter(), test_tight_crop_with_chat_resumption(), test_warframe_and_tricky_weapon_indexing()

### Community 56 - "ShortTermMemory"
Cohesion: 0.24
Nodes (5): ShortTermMemory, test_long_conversations_leave_room_for_the_guide_context(), test_orchestrator_memory_mode_commands(), test_short_term_memory_keyword_extraction(), test_short_term_memory_sliding_window_and_budget()

### Community 57 - "test_chat_routing_comprehensive.py"
Cohesion: 0.15
Nodes (6): orchestrator(), test_chat_disruption_guide(), test_chat_mobile_defense_guide(), test_chat_plan_intent_sortie(), test_chat_status_check(), test_chat_survival_mission_guide()

### Community 58 - "test_mod_matching.py"
Cohesion: 0.26
Nodes (10): analyzer(), names(), test_exclusive_mods_stay_exclusive(), test_mods_also_sold_by_conclave_are_not_pvp(), test_rifle_mods_allowed_on_snipers_and_bows(), test_thrown_melee_mods_allowed_on_glaives(), test_top_match_from_real_ocr(), test_weapon_augment_kept_when_weapon_is_only_inferred() (+2 more)

### Community 59 - "4. 핵심 모듈"
Cohesion: 0.20
Nodes (9): 1. 핵심 철학, 2. 기술 스택, 3. 디렉토리 구조, 4.2.1. 빌드 저장과 리벤 리롤 비교, 4.4. 채팅, 4. 핵심 모듈, 5. 검증, 6. 알려진 한계 (+1 more)

### Community 60 - "test_chat_intent.py"
Cohesion: 0.27
Nodes (8): intent(), llm_offline(), orc(), test_casual_messages_are_smalltalk(), test_common_words_do_not_match_weapons(), test_game_questions_are_guide(), test_player_slang_finds_archon_docs(), test_weapon_names_get_a_fact_card()

### Community 61 - "re"
Cohesion: 0.27
Nodes (7): mod_matched(), normalize_mod(), stat_matches(), test_high_res_panel_stats(), test_mod_recall(), test_panel_stats(), test_unnameable_weapon_is_not_guessed()

### Community 62 - "decompose_hangul"
Cohesion: 0.47
Nodes (3): decompose_hangul(), match_mods_jamo(), smart_match()

## Knowledge Gaps
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OrdisCompanionApp` connect `OrdisCompanionApp` to `desktop_companion.py`, `LLMOrchestrator`, `test_saved_builds.py`, `EmbeddedLLMRunner`, `test_build_chat_and_dialogs.py`, `test_companion_app.py`, `ScreenModAnalyzer`, `PersonaManager`, `test_riven_reroll_reader.py`, `test_world_state.py`?**
  _High betweenness centrality (0.094) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `ScreenModAnalyzer` (e.g. with `4.2. 스크린샷 진단` and `OrdisCompanionApp`) actually correct?**
  _`ScreenModAnalyzer` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `desktop_companion.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05216197666437886 - nodes in this community are weakly interconnected._
- **Why does `LLMOrchestrator` connect `LLMOrchestrator` to `desktop_companion.py`, `OptimizerHTTPHandler`, `OrdisCompanionApp`, `test_saved_builds.py`, `EmbeddedLLMRunner`, `LayeredPetRenderer`, `test_guide_search.py`, `test_build_chat_and_dialogs.py`, `ScreenModAnalyzer`, `PersonaManager`, `DropIndex`, `ShortTermMemory`, `test_chat_routing_comprehensive.py`, `4. 핵심 모듈`, `test_chat_intent.py`, `test_riven_diagnosis_workflow.py`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `OrdisCompanionApp` (e.g. with `4.1. 앱과 런타임` and `BuildEditDialog`) actually correct?**
  _`OrdisCompanionApp` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Should `WFDataIndexer` be split into smaller, more focused modules?**
  _Cohesion score 0.13105413105413105 - nodes in this community are weakly interconnected._
- **Why does `ScreenModAnalyzer` connect `ScreenModAnalyzer` to `desktop_companion.py`, `WFDataIndexer`, `OrdisCompanionApp`, `screen_mod_analyzer.py`, `test_saved_builds.py`, `test_build_chat_and_dialogs.py`, `pytest`, `test_screen_recognition_overhaul.py`, `test_mod_matching.py`, `re`, `decompose_hangul`, `test_riven_diagnosis_workflow.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._