# Domain & State Architecture Guardrails

이 문서는 프로젝트별 특화 제약조건 및 데이터 무결성 규칙을 정의합니다.

## 1. 3-Tier State Management Architecture
1. **Tier 1 — Immutable Raw Vault (원천 불변 계층)**:
   - 외부 수신 원천 데이터, 감사 로그, 원본 증빙 파일은 등록 즉시 불변(Immutable) 상태를 유지한다.
   - 고유 식별자(SHA-256 해시, 고유 키 등)를 부여하여 중복 등록을 원천 차단한다.
2. **Tier 2 — Mutable Override & Allocation Layer (가변 보정 계층)**:
   - 비즈니스 요구에 따른 수동 보정, 비목 분할, 매핑 관계는 가변 계층에서 관리한다.
   - 모든 보정 내역은 사유(Reason)와 타임스탬프를 포함하여 추적 가능(Auditability)해야 한다.
3. **Tier 3 — Idempotent Revision & Delivery Layer (멱등성 발행 계층)**:
   - 최종 결과물(문서, 장부, 빌드 아티팩트)은 원본을 파괴하지 않고 리비전(v1, v2) 형태로 발행하며, 언제 다시 빌드해도 결과가 동일한 멱등성(Idempotency)을 보장한다.

## 2. Hard Domain Verification Gates
- [프로젝트별 수식/비즈니스 게이트 1 작성: 예) 공급가액 + 부가세 == 합계]
- [프로젝트별 수식/비즈니스 게이트 2 작성: 예) 예산 한도 초과 검산]
- [프로젝트별 수식/비즈니스 게이트 3 작성: 예) 날짜 정합성 및 권한 체크]
