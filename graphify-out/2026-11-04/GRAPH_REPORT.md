# Graph Report - 2.7 WarframeOptimizer  (2026-10-22)

## Corpus Check
- 118 files · ~1,246,902 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 17 file(s) not represented in the graph (top: .csv 8, (none) 3, .bat 2)

## Summary
- 745 nodes · 1425 edges · 48 communities (36 shown, 12 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 160 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `efceee9a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- desktop_companion.py
- WFDataIndexer
- OrdisCompanionApp
- LLMOrchestrator
- LocalPipelineRunner
- optimizer_engine.py
- ScreenModAnalyzer
- probe.mjs
- Project Specification: Warframe Build & Synergy Optimizer (WF-Optimizer)
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- 🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide)
- Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol
- EmbeddedLLMRunner
- DesktopPet
- WarframeDamageEngine
- 1. 데미지 버킷 분류 (Damage Buckets)
- 2. 상태이상 메커니즘 (Status Effects)
- TodoPanel
- 04. Warframe External Synergy & Level-Cap Matrix
- 워프레임 성계 지도 기본 미션 유형 가이드 (Star Chart Mission Types)
- DamageBreakdownDialog
- 03. Warframe Survivability & Shield Gating Rules
- /harness
- Engineering Guardrails (Global Standards)
- Global Multi-Agent Harness Directive (Universal System Prompt)
- Engineering Guardrails (Global Standards)
- Global Engineering Experience Library (Harness² Cross-Project Knowledge)
- 워프레임 실전 메타 무기 티어 및 주요 컨텐츠 추천 장비 (Update 36 이후 최신 기준)
- DataIngestor
- WikiIngestor
- Domain Context & Architecture Memory (Warframe Companion)
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- Project Accumulated Experience Library (Harness² Recursion)
- Multi-Agent Orchestration & RBAC Guidelines
- Domain Context & Architecture Memory
- Propose–Probe–Compose Workflow Protocol (Harness² Standard)
- CodexSheetImporter
- Domain & State Architecture Guardrails (Warframe Companion)
- Domain & State Architecture Guardrails
- Project Progress & Verification Board
- Project Progress & Verification Board (Warframe Companion)
- Project Accumulated Experience Library (Harness² Recursion)

## God Nodes (most connected - your core abstractions)
1. `ScreenModAnalyzer` - 48 edges
2. `OrdisCompanionApp` - 38 edges
3. `WFDataIndexer` - 29 edges
4. `LLMOrchestrator` - 27 edges
5. `EmbeddedLLMRunner` - 20 edges
6. `OptimizerEngine` - 20 edges
7. `LocalPipelineRunner` - 19 edges
8. `WeaponStats` - 17 edges
9. `ShortTermMemory` - 17 edges
10. `WorldStateTracker` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Phase 2: 정밀 데미지 및 TTK 시뮬레이터 (`scripts/damage_simulator.py`)` --references--> `CombatState`  [INFERRED]
  warframe.md → scripts/damage_simulator.py
- `4.3. 로컬 LLM 오케스트레이션 & 위키 RAG` --references--> `ChromaRAGRetriever`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/chroma_rag_retriever.py
- `5. 진행 현황 및 마일스톤 (Progress & Milestones)` --references--> `DamageSimulator`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/damage_simulator.py
- `2. 기술 스택 (Tech Stack)` --references--> `DesktopPet`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/desktop_companion.py
- `4.1. 데스크톱 GUI 및 런타임 관리` --references--> `check_hotkeys()`  [INFERRED]
  PROJECT_OVERVIEW.md → scripts/desktop_companion.py

## Import Cycles
- None detected.

## Communities (48 total, 12 thin omitted)

### Community 0 - "desktop_companion.py"
Cohesion: 0.06
Nodes (15): main(), run_domain_sanity(), run_graph_check(), run_tests(), append_experience(), run_server(), start_llama_server(), PathConfig (+7 more)

### Community 1 - "WFDataIndexer"
Cohesion: 0.06
Nodes (17): 1. 기획 의도 및 핵심 철학 (Product Vision & Philosophy), 2. 기술 스택 (Tech Stack), 3. 시스템 아키텍처 및 디렉토리 구조 (Directory Structure), 4.2. 인게임 모딩 OCR 및 한국어 퍼지 매칭 파이프라인, 4. 핵심 모듈 및 주요 함수 명세 (Core Modules & Functions), 5. 진행 현황 및 마일스톤 (Progress & Milestones), 🌌 WF-Companion & Optimizer (세팔론 오디스 스탠드얼론 AI 어시스턴트), ChromaRAGRetriever (+9 more)

### Community 2 - "OrdisCompanionApp"
Cohesion: 0.08
Nodes (11): 4.4. 실시간 월드 상태 & 스마트 체크리스트, OrdisCompanionApp, diagnose_in_background(), check_hotkeys(), RivenQuickInputDialog, WorldStateTracker, test_ordis_companion_headless_and_tabs(), test_finisher_damage_not_confused_with_base_damage() (+3 more)

### Community 3 - "LLMOrchestrator"
Cohesion: 0.09
Nodes (15): 4.3. 로컬 LLM 오케스트레이션 & 위키 RAG, OptimizerHTTPHandler, LLMOrchestrator, ShortTermMemory, orchestrator(), test_chat_disruption_guide(), test_chat_mobile_defense_guide(), test_chat_plan_intent_sortie() (+7 more)

### Community 5 - "optimizer_engine.py"
Cohesion: 0.11
Nodes (22): 4.5. 수학적 시뮬레이션 코어 엔진, CombatState, DamageSimulator, ModConfig, WeaponStats, OptimizerEngine, OptimizerRequest, SurvivalEvaluator (+14 more)

### Community 6 - "ScreenModAnalyzer"
Cohesion: 0.08
Nodes (12): test_boxes(), decompose_hangul(), match_mods_jamo(), ScreenModAnalyzer, YOLOSlotDetector, test_enhance(), smart_match(), test_interactive_weapon_clarification() (+4 more)

### Community 7 - "probe.mjs"
Cohesion: 0.10
Nodes (12): __filename, g1, g2, g3, ROOT_DIR, args, content, EXP_FILE (+4 more)

### Community 8 - "Project Specification: Warframe Build & Synergy Optimizer (WF-Optimizer)"
Cohesion: 0.10
Nodes (20): 1.1. 필수 달성 유스케이스 (Core Use Cases), 1. 프로젝트 개요 및 목표 (Project Overview & Goals), 2. 기술 스택 (Tech Stack), 3. 시스템 아키텍처 및 디렉토리 구조 (System Architecture), 4. 핵심 모듈별 상세 구현 방안 (Detailed Implementation Plan), 5.1. LLM -> Python 입력 JSON 스키마, 5.2. Python -> LLM 결과 반환 JSON 스키마, 5. LLM 오케스트레이션 프로토콜 (`pipeline_runner.py` 연동 규격) (+12 more)

### Community 9 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.10
Nodes (19): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+11 more)

### Community 10 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.10
Nodes (19): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+11 more)

### Community 11 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.10
Nodes (19): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+11 more)

### Community 12 - "🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide)"
Cohesion: 0.11
Nodes (17): 1) Windows PowerShell 콘솔 한글 깨짐 방지, 1. 📌 프로젝트 개요 (Overview), 1단계: 가상환경 생성 및 의존성 설치, 2) Ollama 포트 충돌 (11434 포트), 2. 💻 새 PC 개발 환경 요구사항 (Prerequisites), 2단계: 로컬 LLM 확인, 3. 🚀 3단계 빠른 시작 (Quick Start), 3) 스탠드얼론 실행 시 GGUF 모델 다운로드 (+9 more)

### Community 13 - "Antigravity Universal Orchestration Rules (v2.0): Graphify & Local Worker Protocol"
Cohesion: 0.13
Nodes (14): 0. Autonomous Environment Bootstrap (Run Once Per Project), 1. Role & Structural Workload Partitioning (No Line-Count Guessing), 2. Dependency & Context Discovery (Graphify-First Hard Gate), 3.1 Mode A: Tier 2 Surgical Method Patch & Upsert (`--mode patch`), 3.2 Mode B: Tier 3 New Component Generation (`--mode create`), 3.3 Windows Shell Safety (`[T]` Generic Notation) & 8k Budget Guardrails, 3. Local Worker CLI Dispatch Protocol (v2.0 Enhancements), 4. Zero Post-Inspection & Circuit Breaker Protocol (+6 more)

### Community 14 - "EmbeddedLLMRunner"
Cohesion: 0.32
Nodes (4): main(), 4.1. 데스크톱 GUI 및 런타임 관리, EmbeddedLLMRunner, test_embedded_llm_runner_default_4k_and_restart()

### Community 16 - "WarframeDamageEngine"
Cohesion: 0.35
Nodes (7): WarframeDamageEngine, test_elemental_and_base_damage_buckets(), test_firearm_duty_cycle_sustained(), test_in_game_crit_tiers_and_rolls(), test_melee_duty_cycle_no_reload(), test_sanitize_left_stats_comma_dot_fix(), test_sanitize_left_stats_small_noise_rejection()

### Community 17 - "1. 데미지 버킷 분류 (Damage Buckets)"
Cohesion: 0.17
Nodes (11): 01. Warframe Damage Formulas & Buckets, 1. 데미지 버킷 분류 (Damage Buckets), 2. 치명타 티어 수식 (Critical Tiers), 3. 최종 기대 직격 타격 데미지 공식, Bucket 1: Base Damage ($B$), Bucket 2: Additive Base Damage Multiplier ($M_{\text{base}}$), Bucket 3: Elemental Damage Multiplier ($M_{\text{elem}}$), Bucket 4: Faction Damage Multiplier ($M_{\text{faction}}$) (+3 more)

### Community 18 - "2. 상태이상 메커니즘 (Status Effects)"
Cohesion: 0.17
Nodes (11): 02. Warframe Enemy Scaling & Status Effects (Post-Jade Shadows Spec), 1.1. 체력 및 실드 스케일링, 1.2. 방어력 개편 (Update 36: Armor Cap at 2,700), 1. 적 레벨 스케일링 공식 (Enemy Scaling), 2.1. 바이러스 (Viral), 2.2. 절단 (Slash DoT - Bleed), 2.3. 화염 (Heat DoT - Ignite), 2.4. 부식 (Corrosive) (+3 more)

### Community 20 - "04. Warframe External Synergy & Level-Cap Matrix"
Cohesion: 0.20
Nodes (9): 04. Warframe External Synergy & Level-Cap Matrix, 1.1. 방어력/실드 무력화 (Armor Strip), 1.2. 화력 증폭 버프, 1. 헬민스 주입 어빌리티 (Helminth Subsumed Abilities), 2. 합성 집정관 파편 (Archon Shards Synergy), 3.1. 동반자 상태이상 프라이머 (Companion Primer), 3.2. 갈바니즈드 앱티튜드/샷/새비 (GunCO) 수학, 3. 동반자 프라이밍 & 갈바니즈드 GunCO 연계 (+1 more)

### Community 21 - "워프레임 성계 지도 기본 미션 유형 가이드 (Star Chart Mission Types)"
Cohesion: 0.20
Nodes (9): 1. 생존 미션 (Survival), 2. 이동방어 미션 (Mobile Defense), 3. 방어 미션 (Defense), 4. 섬멸 미션 (Exterminate), 5. 포획 미션 (Capture), 6. 첩보 / 도청 미션 (Spy), 7. 구출 미션 (Rescue), 8. 감청 미션 (Interception) (+1 more)

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

### Community 32 - "Domain Context & Architecture Memory (Warframe Companion)"
Cohesion: 0.40
Nodes (4): 1. Core Architecture Overview, 2. Key Entities & Data Models, 3. Communication & Integration, Domain Context & Architecture Memory (Warframe Companion)

### Community 33 - "Propose–Probe–Compose Workflow Protocol (Harness² Standard)"
Cohesion: 0.40
Nodes (4): Phase 1. Propose (가설 및 후보안 수립), Phase 2. Probe (격리 검증 및 스모크 테스트), Phase 3. Compose (최적안 채택 및 지식 누적), Propose–Probe–Compose Workflow Protocol (Harness² Standard)

### Community 34 - "Project Accumulated Experience Library (Harness² Recursion)"
Cohesion: 0.40
Nodes (4): EXP-001: Embedded Python과 시스템 Python 간 패키지 격리 및 Pytest 탐색 충돌 방지, EXP-002: Windows 환경 한글 인코딩 및 파일 입출력 안전성, EXP-003: Harness 초기 구축 및 3대 게이트 검증 연동, Project Accumulated Experience Library (Harness² Recursion)

### Community 35 - "Multi-Agent Orchestration & RBAC Guidelines"
Cohesion: 0.40
Nodes (4): 1. Multi-Agent Roles (Strict RBAC), 2. Inter-Agent Communication Protocol (`@[AGENT_PACKET]`), 3. Atomic Commit Policy, Multi-Agent Orchestration & RBAC Guidelines

### Community 36 - "Domain Context & Architecture Memory"
Cohesion: 0.40
Nodes (4): 1. Core Architecture Overview, 2. Key Entities & Data Models, 3. Communication & Integration, Domain Context & Architecture Memory

### Community 37 - "Propose–Probe–Compose Workflow Protocol (Harness² Standard)"
Cohesion: 0.40
Nodes (4): Phase 1. Propose (가설 및 후보안 수립), Phase 2. Probe (격리 검증 및 스모크 테스트), Phase 3. Compose (최적안 채택 및 지식 누적), Propose–Probe–Compose Workflow Protocol (Harness² Standard)

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

## Knowledge Gaps
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OrdisCompanionApp` connect `OrdisCompanionApp` to `desktop_companion.py`, `LLMOrchestrator`, `ScreenModAnalyzer`, `🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide)`, `EmbeddedLLMRunner`, `DesktopPet`, `DamageBreakdownDialog`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `ScreenModAnalyzer` (e.g. with `4.2. 인게임 모딩 OCR 및 한국어 퍼지 매칭 파이프라인` and `OrdisCompanionApp`) actually correct?**
  _`ScreenModAnalyzer` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `desktop_companion.py` be split into smaller, more focused modules?**
  _Cohesion score 0.06409130816505706 - nodes in this community are weakly interconnected._
- **Why does `ScreenModAnalyzer` connect `ScreenModAnalyzer` to `desktop_companion.py`, `WFDataIndexer`, `OrdisCompanionApp`, `LLMOrchestrator`, `optimizer_engine.py`, `WarframeDamageEngine`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `OrdisCompanionApp` (e.g. with `DamageBreakdownDialog` and `EmbeddedLLMRunner`) actually correct?**
  _`OrdisCompanionApp` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `WFDataIndexer` be split into smaller, more focused modules?**
  _Cohesion score 0.06397306397306397 - nodes in this community are weakly interconnected._
- **Are the 4 inferred relationships involving `WFDataIndexer` (e.g. with `4.2. 인게임 모딩 OCR 및 한국어 퍼지 매칭 파이프라인` and `5. 진행 현황 및 마일스톤 (Progress & Milestones)`) actually correct?**
  _`WFDataIndexer` has 4 INFERRED edges - model-reasoned connections that need verification._