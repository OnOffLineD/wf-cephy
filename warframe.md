# Project Specification: Warframe Build & Synergy Optimizer (WF-Optimizer)

## 1. 프로젝트 개요 및 목표 (Project Overview & Goals)
본 프로젝트는 워프레임(Warframe)의 복잡한 데미지 수식, 생존 메커니즘, 외부 시너지(워프레임 어빌리티, 헬민스, 집정관 파편, 동반자, 아케인)를 수학적으로 시뮬레이션하여 최적의 빌드를 도출하는 **하이브리드 AI 에이전트 시스템**을 구축하는 것이다.

- **핵심 철학**: LLM(Gemma 4 E4B)은 **절대 직접 수식을 계산하지 않는다.** LLM은 사용자의 자연어 의도를 JSON 파라미터로 파싱(Orchestration)하고, 파이썬 시뮬레이션 엔진(`optimizer_engine.py`)이 산출한 정량적 결과를 바탕으로 빌드 가이드와 운용법을 해설(Reporting)한다.

### 1.1. 필수 달성 유스케이스 (Core Use Cases)
1. **리벤 및 단일 모드 정밀 비교 (`RIVEN_COMPARE`)**
   - 입력 예시: *"토리드 리벤 A(치확 120%, 치피 100%) vs 리벤 B(멀티샷 100%, 피해 100%) 중 뭐가 더 좋아?"*
   - 처리 로직: 무기 기본 스탯(인카논 폼 포함) 및 표준 7모드 세팅을 기준으로, 남은 1슬롯(또는 대체 슬롯)에 리벤 A와 B를 장착했을 때의 **기댓값(Expected DPS), 최소 보장 데미지(Min Roll), 상태이상 가중치 변화**를 비교하여 최적 옵션을 판별한다.
2. **워프레임 생존 및 유틸리티 최적화 (`SURVIVAL_BUILD`)**
   - 입력 예시: *"노바 생존 모딩 짜줘."*
   - 처리 로직: 단순 체력 모드(Vitality 등) 장착 시의 EHP와, 어빌리티 메커니즘(노바 1번 Null Star 피해 감소 + 4번 Molecular Prime 둔화/피해증가 + Adaptation 또는 실드 게이팅) 결합 시의 실효 생존력을 비교하여, 어빌리티 효율(위력/지속)을 해치지 않는 최고 효율 빌드를 추천한다.
3. **저스펙 무기 레벨캡(Lv.9999) 시너지 플랜 (`LEVELCAP_SYNERGY`)**
   - 입력 예시: *"MK1-브래튼을 레벨캡에서 쓸 수 있게 플랜 짜봐."*
   - 처리 로직: 무기 단독 모딩으로 적(Lv.9999 강철의 길 헤비거너 등) 처치가 불가능함을 감지하면, **외부 시너지 모듈(워프레임 버프, 헬민스 방어력 삭감, 집정관 파편, 동반자 상태이상 프라이밍, 외부 고정 치명타 버프)**을 역산하여 TTK(Time-To-Kill) 3초 이내를 달성하는 통합 마스터플랜을 구성한다.

---

## 2. 기술 스택 (Tech Stack)
- **Agent & Orchestration**: Google Antigravity Framework
- **Local LLM**: `Gemma 4 E4B` (via Ollama / llama.cpp, Function Calling & Structured JSON Output 전용)
- **Core Backend / Math Engine**: `Python 3.11+`
  - 수치 연산 및 배열 처리: `numpy`, `pydantic` (스키마 검증)
  - 최적화 알고리즘: `DEAP` 또는 커스텀 유전 알고리즘(Genetic Algorithm) + 분기 한정법(Branch and Bound)
- **Data Pipeline & Storage**:
  - 정형 데이터(무기/모드/워프레임 기초 스탯): `@wfcd/items` (Warframe Community Developers JSON 덤프) 기반 로컬 `SQLite` 또는 정규화된 JSON DB
  - 비정형 규칙/수식(위키 기반 지식): `Playwright` + `BeautifulSoup4` 크롤러 -> 정제된 Markdown 룰북 (`rules/*.md`)

---

## 3. 시스템 아키텍처 및 디렉토리 구조 (System Architecture)

```text
wf-optimizer/
├── ANTIGRAVITY_RULES.md          # 안티그래비티 에이전트 제어 지침 및 제약 사항
├── WARFRAME_OPTIMIZER_SPEC.md    # 현재 프로젝트 명세서
├── data/
│   ├── raw_wfcd/                 # WFCD 오픈소스 원본 JSON (Weapons, Mods, Warframes)
│   ├── wf_database.sqlite        # 정규화된 스탯 및 모드 제약 조건 DB
│   └── wiki_cache/               # 크롤링된 워프레임 위키 원본 HTML/Text
├── rules/                        # 위키 크롤링 및 정제된 수식/메커니즘 마크다운
│   ├── 01_damage_formulas.md     # 합연산/곱연산 버킷, 치명타 티어, 양자화(Quantization) 제외 실전 수식
│   ├── 02_status_and_scaling.md  # 적 레벨 스케일링, 방어력 DR, 상태이상(절단/화염/바이러스 등) 틱 수식
│   ├── 03_survivability_rules.md # EHP 계산식, 중첩 피해 감소(DR), 실드 게이팅 메커니즘
│   └── 04_synergy_matrix.md      # 헬민스(로어, 필리지 등), 집정관 파편, 아케인, 동반자 프라이밍 규칙
└── scripts/
    ├── data_ingestor.py          # WFCD 데이터 로드 및 위키 수식 페이지 크롤러
    ├── damage_simulator.py       # 단일 빌드 DPS, 최소/최대값, 상태이상 TTK 계산 엔진
    ├── survival_evaluator.py     # 워프레임 EHP, DR, 실드 게이팅 사이클 평가 엔진
    ├── genetic_optimizer.py      # 모드 풀 가지치기(Pruning) + 유전 알고리즘 최적 조합 탐색기
    ├── synergy_planner.py        # 레벨캡 달성을 위한 외부 시너지(워프레임/헬민스/동반자) 역산기
    └── pipeline_runner.py        # LLM 요청(JSON)을 받아 각 모듈을 실행하고 결과를 반환하는 CLI/API 엔트리포인트
```

---

## 4. 핵심 모듈별 상세 구현 방안 (Detailed Implementation Plan)

### Phase 1: 하이브리드 데이터 수집 파이프라인 (`scripts/data_ingestor.py`)
1. **기초 스탯 DB 구축**:
   - 위키에서 모든 무기 스탯을 크롤링하면 HTML 구조 변경에 취약하므로, GitHub `WFCD/warframe-items`의 JSON 데이터를 파싱하여 무기 기초 데미지, 치명타 확률/배수, 상태이상 확률, 연사력, 리벤 기질(Disposition), 인카논 진화 보너스를 `wf_database.sqlite`에 적재한다.
2. **위키 수식 및 기믹 크롤링 (`rules/*.md` 생성)**:
   - 워프레임 위키의 핵심 페이지(`Damage`, `Critical Hit`, `Status Effect`, `Armor`, `Shield`, 각 워프레임 어빌리티 페이지)를 크롤링하여 마크다운 수식 테이블로 변환한다.
   - **필수 구분 버킷(Damage Buckets)**:
     - `Base Damage`: 무기 기본 피해 + 인카논 진화 기초 피해
     - `Additive Base Damage`: Serration, Merciless, Galvanized Aptitude (단, 발사체 무기의 곱연산 예외 플래그 `is_multiplicative_gunco` 필드 포함)
     - `Elemental Damage`: 단일 속성 및 복합 속성 합연산 버킷
     - `Faction Damage`: Bane 모드 및 Roar 어빌리티 (상태이상 DoT 틱 계산 시 **Double Dipping** 제곱 적용 필수)
     - `Multishot`: 탄환 수 증가 및 상태이상 기대 횟수 증가
     - `Critical`: 치명타 티어($T = \lfloor \text{CritChance} \rfloor$)에 따른 최소 티어 보장값(`Min Roll`)과 가중 평균(`Expected Value`) 분리 산출

### Phase 2: 정밀 데미지 및 TTK 시뮬레이터 (`scripts/damage_simulator.py`)
1. **전투 상태 컨텍스트(`CombatState`) 정의**:
   - `initial` (0스택 초동 상태) vs `sustained` (갈바니즈드/아케인 최대 중첩 상태) 두 가지 시나리오를 동시 계산한다.
2. **출력 지표 다각화**:
   - `expected_hit`: 1발당 평균 기대 데미지
   - `min_guaranteed_hit`: 치명타가 낮은 티어로 터졌을 때의 최소 보장 데미지 (일격필살 안정성 지표)
   - `burst_dps` / `sustained_dps`: 재장전 시간을 제외한 순간 화력 및 재장전 포함 지속 화력
   - `simulated_ttk`: 특정 적(예: Lv.200 또는 Lv.9999 커럽티드 헤비거너)을 상대로 5초간 사격 시 **바이러스(체력 피해 최대 +325%) + 절단/화염/독 DoT 누적 데미지**를 0.1초 단위로 적분하여 실제 처치 소요 시간(초) 산출.

### Phase 3: 리벤 비교 및 기회비용 분석기 (`RIVEN_COMPARE` 모드)
1. **기회비용(Opportunity Cost) 반영**:
   - 빈 슬롯에 리벤만 넣는 것이 아니라, 해당 무기의 **표준 종결 8모드 빌드**를 먼저 생성한다.
   - 8개 모드 중 리벤으로 대체 가능한 가장 약한 슬롯(8번째 슬롯)을 찾고, `리벤 A 장착 빌드` vs `리벤 B 장착 빌드` vs `노리벤 순정 빌드` 3가지를 동시 비교한다.
2. **무기 기질(Disposition) 자동 보정**:
   - 사용자가 입력한 수치 그대로 계산하는 모드와, 무기 인게임 기질 수치에 맞춰 보정하는 모드를 모두 지원한다.

### Phase 4: 워프레임 생존 및 어빌리티 최적화기 (`scripts/survival_evaluator.py`)
1. **단순 체력 모딩 함정 방지 로직**:
   - 적 레벨에 따른 데미지 스케일링 공식:
     $$\text{Enemy Damage} = \text{Base Damage} \times \left(1 + (\text{Current Level} - \text{Base Level})^{1.55} \times 0.015\right)$$
   - 목표 레벨(예: 강철의 길 기본 Lv.150~200 또는 내구 Lv.1000+)의 적 DPS를 산출하여, 단순 체력 모드(Vitality)만 넣었을 때 버틸 수 있는 시간(초)을 계산한다.
2. **다중 피해 감소(DR) 및 실드 게이팅 평가**:
   -$$\text{Total EHP} = \frac{\text{Health}}{(1 - \text{DR}_{\text{Armor}}) \times (1 - \text{DR}_{\text{Ability}}) \times (1 - \text{DR}_{\text{Adaptation}})}$$
   - 어빌리티 피해 감소(예: 노바 Null Star 최대 90% DR, Eclipse 75% DR)가 어빌리티 위력/지속시간 스탯에 어떻게 연동되는지 계산하여, **체력 모드 대신 지속/위력 모드를 넣는 것이 EHP와 유틸리티 양면에서 우월함**을 수치로 입증한다.

### Phase 5: 레벨캡(Lv.9999) 시너지 역산기 (`scripts/synergy_planner.py`)
1. **트리거 조건**:
   - 목표 레벨이 `9999`(또는 `levelcap`)로 설정되었거나, 무기 단독 최적화 후 `simulated_ttk > 5.0초`인 경우 자동 활성화된다.
2. **시너지 레이어 강제 주입 및 탐색**:
   - **Step 1 (방어력/실드 무력화)**: 적 방어력으로 인한 90% 피해 감소를 제거하기 위해 헬민스 방어력 삭감(`Pillage`, `Tharros Strike`, `Terrify`) 또는 상태이상 우회(`Slash` DoT, `Toxin`) 옵션을 활성화한다.
   - **Step 2 (외부 기본/치명타 버프 주입)**: MK1-브래튼처럼 기본 치명타 확률(8%)과 배수(1.5x)가 낮은 무기는 자체 치명타 모딩 효율이 최악이므로, **고정 치명타 확률 버프(아케인 어벤저 +45%, 해로우 Covenant, 애다르자 카밧 Cat's Eye +60%)** 및 **무기 데미지 버프(Saryn Toxic Lash, Xata's Whisper, Mirage Eclipse, Rhino Roar)**를 조합한다.
   - **Step 3 (동반자 프라이밍 & 집정관 파편)**: 동반자(하운드/노틸러스/파란 팬저 등)가 바이러스 10스택 + 자기력/방사능 등 다중 상태이상을 사전 부여한다고 가정하여 `Galvanized Aptitude`의 피해량을 극대화하고, 집정관 파편(예: 타우포지드 적색/보라색 치명타 피해 또는 어빌리티 위력)을 할당한다.

---

## 5. LLM 오케스트레이션 프로토콜 (`pipeline_runner.py` 연동 규격)

Gemma 4 E4B의 추론 부담을 최소화하기 위해, LLM은 사용자 질의를 읽고 아래 **단일 JSON 스키마**만 생성하여 `pipeline_runner.py`에 전달한다.

### 5.1. LLM -> Python 입력 JSON 스키마
```json
{
  "task_type": "RIVEN_COMPARE | SURVIVAL_BUILD | LEVELCAP_SYNERGY | GENERAL_WEAPON_BUILD",
  "target_item": "Torid | Nova | MK1-Braton",
  "incarnon_mode": true,
  "enemy_context": {
    "faction": "Grineer | Corpus | Murmur | Corrupted",
    "level": 200,
    "is_steel_path": true
  },
  "riven_candidates": [
    {"name": "Option A", "stats": {"crit_chance": 1.2, "crit_damage": 1.0}},
    {"name": "Option B", "stats": {"multishot": 1.0, "base_damage": 1.0}}
  ],
  "constraints": {
    "allow_helminth": true,
    "allow_archon_shards": true,
    "allow_companion_primer": true
  }
}
```

### 5.2. Python -> LLM 결과 반환 JSON 스키마
`pipeline_runner.py`는 연산 완료 후 아래 형식의 결과만 반환하며, LLM은 이 수치를 절대 수정하지 않고 자연어 리포트로만 변환한다.
```json
{
  "status": "SUCCESS",
  "task_type": "RIVEN_COMPARE",
  "summary_metrics": {
    "winner": "Option A",
    "expected_dps_diff_percent": "+18.4%",
    "option_a": {"expected_dps": 1425000, "min_hit": 48200, "slash_tick_avg": 19500},
    "option_b": {"expected_dps": 1203500, "min_hit": 51100, "slash_tick_avg": 16400}
  },
  "recommended_build": [
    "Galvanized Chamber", "Critical Delay", "Vital Sense", "Hunter Munitions",
    "Malignant Force", "Rime Rounds", "Primed Firestorm", "[Riven: Option A]"
  ],
  "synergy_notes": [
    "Primary Merciless 12스택 상태에서 Option B의 피해 +100%는 합연산 희석(Diminishing Returns)이 발생함.",
    "Torid 인카논 폼의 높은 기초 치명타 스탯 덕분에 Option A의 치확/치피가 곱연산으로 크게 작용함."
  ]
}
```

---

## 6. 단계별 개발 마일스톤 (Implementation Roadmap)
- **Milestone 1 (Data & Schema)**: `WFCD` JSON 파서 작성 및 주요 무기/모드 200종 SQLite 적재, 기본 데미지 공식 마크다운(`rules/01_damage_formulas.md`) 작성.
- **Milestone 2 (Weapon Simulator & Riven Compare)**: `damage_simulator.py` 구현 및 토리드/라에툼 등 주요 무기 리벤 A/B 비교 테스트 통과.
- **Milestone 3 (Survivability Engine)**: `survival_evaluator.py` 구현, 워프레임별 어빌리티 피해 감소(DR) 규칙 매핑 및 노바/메사/레버넌트 생존 모딩 검증.
- **Milestone 4 (Level-Cap Synergy Solver)**: `synergy_planner.py` 구현, 외부 버프(헬민스/아케인/파편/동반자) 조합 탐색 및 MK1-브래튼 레벨캡 TTK 시뮬레이션 검증.
- **Milestone 5 (Antigravity & Gemma 4 E4B Integration)**: `pipeline_runner.py` CLI 연동 및 Gemma 4 E4B 프롬프트/툴 콜링 파이프라인 최종 결합.

## 7. 심화 최적화 레이어 확장 명세 (v4.0 Advanced Optimization Layers)

### 7.1. 상태이상 가중치 및 오버가드/감쇄 시뮬레이션 (`StatusWeighting & EnemyArchetype`)
1. **상태이상 가중치 최적화 규칙**:
   - 무기에서 직접 바이러스(Viral)와 지속 피해 속성(Heat, Slash, Electric, Blast)을 동시에 모딩할 경우, 반드시 $\text{Weight}_{\text{DoT}} > \text{Weight}_{\text{Viral}}$ 조건을 만족해야 한다.
   - 만약 165% 속성 모드(Primed Cryo Rounds 등) 채용으로 바이러스 비중이 45%를 초과하여 초당 DoT 틱 누적량이 감소하면, 유전 알고리즘에 가중치 페널티를 부여하고 **60/60 모드 채택 또는 외부 바이러스 공급(Nourish/동반자)**으로 우회한다.
2. **적 아키타입(`enemy_archetype`) 분기**:
   - `OVERGUARD_EXIMUS`: 자성(Magnetic) 상태이상 부여 시 오버가드 대상 피해 증폭(최대 +325%) 및 오버가드 파괴 시 30% 전기 폭발 데미지를 반영한다. 보조무기의 경우 `Secondary Fortifier` 아케인(오버가드 8배 피해 및 강탈) 가중치를 최상위로 격상한다.
   - `ACOLYTE_MINIBOSS`: 모든 상태이상 최대 중첩 수를 `4스택`(바이러스 4스택 = +175%)으로 Clamping하고, 고정 치명타 및 직접 타격 배수를 우선시한다.

### 7.2. 인카논 진화 트리 & 대적자 무기 숙주 보너스 (`Incarnon & Progenitor Solver`)
1. **인카논 진화 경로 동시 탐색**:
   - 인카논 무기(Torid, Laetum, Phenmor, Burston, Dual Toxocyst, Boar 등)가 입력되면, `data/incarnon_trees.json`에서 가능한 진화 경로 조합(예: `Crit Evolution` vs `Status Evolution` vs `Devouring Attrition Non-Crit`)을 각각 독립된 무기 프로파일로 생성하여 시뮬레이션한 뒤 가장 높은 성능을 내는 **진화 노드 선택지(Evolution II ~ IV)**를 모드 빌드와 함께 출력한다.
2. **쿠바/테넷/코다 숙주 속성(`Progenitor Bonus`) 추천**:
   - 대적자 무기는 최대 +60%의 숙주 속성(독, 화염, 자성, 전기, 방사능 등)을 기초 피해로 가진다. 엔진은 어떤 숙주 속성을 선택했을 때 모드 슬롯이 가장 많이 압축되는지(예: `자성 숙주 + 독 1모드 + 화염 1모드 = 자성+독+화염 3속성 2슬롯 완성`) 역산하여 **최적의 숙주 속성**을 함께 추천한다.

### 7.3. 초슬롯 압축기 (`Meta-Slot Compression: Shards, Focus, Tennokai`)
모드 8칸의 한계를 돌파하기 위해 아래 3가지 외부 시스템을 워프레임/무기 모드 슬롯과 등가 교환(Trade-off)한다.
- **합성 집정관 파편(Violet / Emerald / Topaz)**:
  - `Violet Shard (Equilibrium)` 1개 장착 시 ➔ 워프레임 `Equilibrium` 모드 제거 후 위력/범위 모드 추가.
  - `Emerald Shard (Corrosive Max Stacks +2)` 2개 장착 시 ➔ 부식 14스택(방어력 100% 영구 삭감) 달성으로 헬민스 방깎 강제 조건 해제.
  - `Topaz Shard (Secondary Crit on Heat Kill)` 장착 시 ➔ 메사 `Regulators` 등 보조무기 치명타 확률 보충.
- **오퍼레이터 포커스 학파(`Focus School`)**:
  - `Unairu` 선택 시 ➔ `Poise`(40초 넉다운 면역)로 `Primed Sure Footed` 대체, `Caustic Strike`로 100% 방깎 지원.
  - `Zenurik` 선택 시 ➔ `Wellspring`으로 초기 에너지 경제 해결 및 위력 +20% 공급.
  - `Madurai` 선택 시 ➔ `Sling Strength`(+40% 위력)로 스냅샷 어빌리티 브레이크포인트 달성.
  - `Vazarin` 선택 시 ➔ `Protective Sling`(5초 무적)으로 레벨캡 생존 보조.
- **근접 텐노카이(`Tennokai`)**:
  - 근접 무기 엑실러스 슬롯에 `Dreamer's Wrath` 또는 `Opportunity's Reach`를 배치하여, 일반 슬롯 손실 없이 12배수 연속기 유지형 강공격 빌드를 활성화한다.

### 7.4. 가성비 투자 등급 및 한계 기여도 리포팅 (`Investment Tier & Sensitivity Analysis`)
1. **투자 예산 필터 (`investment_tier`)**:
   - `budget_starter`: 포르마 0~1개, 레전더리(Primed/Archon) 모드 및 고가 아케인 제외, 일반 모드 기준 최적 빌드.
   - `standard_mid`: 포르마 3~5개, 갈바니즈드 및 기본 아케인(Merciless/Molt Augmented) 포함.
   - `endgame_omni`: 포르마 무제한(Update 38.5 Omni Forma 및 Umbra Forma 포함), 타우포지드 합성 파편 5개, 풀랭크 레전더리 아케인 및 리벤 포함 최고점 빌드.
2. **슬롯별 한계 기여도(`marginal_sensitivity`) 산출 의무**:
   - 최종 추천된 8개 모드 각각에 대해 해당 모드를 제거했을 때의 성능 감소율(`+XX.X% 기여`)을 계산하여 출력한다.
   - 기여도가 가장 낮은 1~2개 슬롯을 **`[Flex Slot / 자유 교체 슬롯]`**으로 명시하고, 사용자가 리벤을 넣거나 편의성 모드(재장전, 탄속, 범위)로 바꿀 때 어떤 모드를 빼야 하는지 정확히 지목한다.