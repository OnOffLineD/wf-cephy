# Domain Context & Architecture Memory

> 이 문서는 프로젝트의 핵심 도메인 모델, 인터페이스, 상태 머신을 기록하는 하네스 메모리입니다.

## 1. Core Architecture Overview
- **System Purpose**: [프로젝트의 핵심 목표 및 제공 가치]
- **Key Modules**:
  - `core/`: 핵심 도메인 로직 및 데이터베이스
  - `services/`: 비즈니스 워크플로우 오케스트레이션
  - `ui/`: 사용자 인터페이스 및 프론트엔드
  - `tests/`: 단위, 통합, 회귀 검증 스위트

## 2. Key Entities & Data Models
- [핵심 모델 1 명세]: 주요 필드, 식별자, 제약조건
- [핵심 모델 2 명세]: 외래키 관계, M:N 매핑

## 3. Communication & Integration
- API Endpoints: 주요 엔드포인트 및 DTO
- External Dependencies: 연동되는 외부 API/서비스 목록
