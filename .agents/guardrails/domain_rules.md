# Domain & State Architecture Guardrails (Warframe Companion)

이 문서는 Warframe Companion 프로젝트의 특화 제약조건 및 데이터 무결성 규칙을 정의합니다.

## 1. 3-Tier State Management Architecture
1. **Tier 1 — Immutable Raw Vault (원천 불변 계층)**:
   - 외부 수신 원천 데이터(Warframe Community Developers JSON, 원본 스크린샷 캡처 이미지, 감사 로그)는 불변(Immutable) 상태로 유지한다.
   - 고유 식별자(SHA-256 해시, 고유 키)로 중복 등록을 원천 차단한다.
2. **Tier 2 — Mutable Override & Allocation Layer (가변 보정 계층)**:
   - 사용자 설정 오버라이드, 리벤 옵션 수동 보정, 커스텀 무기 통계 보정은 가변 계층에서 관리한다.
   - 모든 보정 내역은 사유(Reason)와 타임스탬프를 포함하여 추적 가능(Auditability)해야 한다.
3. **Tier 3 — Idempotent Revision & Delivery Layer (멱등성 발행 계층)**:
   - 계산된 DPS/TTK 지표 및 리벤 가치 평가 결과는 원본을 파괴하지 않고 리비전 형태로 발행하며, 동일 입력에 대해 항상 동일한 결과를 반환하는 멱등성(Idempotency)을 보장한다.

## 2. Hard Domain Verification Gates
1. **NO FORCED MODDING GENERATION**: 8모드 빌드 자동 생성 로직은 금지되며, 질의응답 및 스크린샷 진단 중심으로 구동한다.
2. **SCREENSHOT MOD DIAGNOSTIC**:
   - 모딩창 OCR 결과로부터 무기명, 장착 모드, 수치 속성을 추출한다.
   - 필수 4대 수치 지표: **Expected DPS, Burst DPS, Max Crit Roll (Peak), Min Roll (Trough)**를 정확히 산출한다.
   - 정보 불충분 시 재촬영 가이드를 친절히 안내한다.
3. **3-TIER STRICT CHAT ROUTING**:
   - **Level 1 (Smalltalk)**: 일상 대화, 인사 -> 위트 있는 세팔론 오르디스(Cephalon Ordis) 페르소나 응답. 빌드 템플릿 출력 금지.
   - **Level 2 (Game Guide / Mechanics)**: 보스 패턴, 속성 상성, 퀘스트 -> `rules/wiki_docs/` RAG 기반 인게임 액션 가이드.
   - **Level 3 (Screenshot Diagnostic)**: 이미지 입력 -> OCR 진단 및 데미지 엔진 수식 계산.
4. **UI/UX STANDARDS**:
   - 카카오톡 스타일 1:1 채팅 레이아웃 + Warframe 다크 테마.
   - 실시간 월드 이벤트 체크리스트(Cetus, Duviri, Sortie).
   - 스마트 할 일(Todo) 감지 및 인라인 확인/삭제(`[X]`).
   - 모든 JSON/텍스트 입출력 시 UTF-8 인코딩 강제.
