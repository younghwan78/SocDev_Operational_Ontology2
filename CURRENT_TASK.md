# CURRENT_TASK.md

## 활성 Stage

**Stage 2 — PostgreSQL 계층** (진행 중 — 2026-07-04 사용자가 연속 Stage 진행을 사전 승인함)

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## Stage 1 완료 기준선

Stage 1은 완료되어 다음을 제공한다:

```text
온톨로지 v1.0 계약 8모듈 (backend/ontology/, Pydantic v2 단일 소스)
한국어 glossary (전 모델/필드/enum label_ko, 테스트 강제)
JSON Schema 자동 export 33개 (schemas/, 드리프트 테스트 차단)
56 fixture 전량 변환 465건 (fixtures/ 8파일, 변환 회귀 테스트)
in-memory repository + 참조 무결성 검사 (오류 0건)
CLI validate-data (한국어 출력)
테스트 18건 / ruff / mypy 통과
```

---

## Stage 2 목표

PostgreSQL을 source of truth로 만드는 저장 계층과 시드 반입 경로를 구축한다.
상세: `docs/design/02_implementation_roadmap.md` Stage 2 절.

## 기준 가정

- Stage 1 온톨로지 계약이 회귀 기준선이다 — 도메인 의미 변경 금지.
- 테이블 설계는 56 Phase3-lite 패턴 승계: 관계 컬럼 + JSONB payload + relations 테이블 + pgvector-ready semantic_chunks.
- DSN 미설정 환경에서도 전체 단위 테스트가 통과해야 한다 (DB 없이 개발 가능).
- in-memory repository와 PostgreSQL repository는 동일 인터페이스(RepositoryProtocol)를 구현한다.

## In-scope

```text
backend/db/: psycopg3 connection 관리, 버전드 SQL 마이그레이션 + 경량 러너
backend/ingest/yaml_seed.py: fixture → DB 멱등 반입 (source_origin 태깅)
PostgreSQL repository (RepositoryProtocol 패리티)
CLI: db-init, db-seed, db-check
DSN 게이트 통합 테스트 (init → seed → 패리티 → 멱등성)
```

## Out-of-scope (Stage 2에서 구현 금지)

```text
pgvector 실제 임베딩 적재 / 검색
FastAPI / API 엔드포인트
LLM provider / advisory
frontend
Excel/CSV 반입, 외부 커넥터
파생 뷰 (portfolio / weekly / trace)
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider          # DSN 없이 전체 통과
uv run ruff check backend tests tools
uv run mypy
uv run python -m backend.cli.main validate-data   # 오류 0건 유지
# PostgreSQL 가용 시:
POSTGRES_TEST_DSN=... uv run pytest -m postgres -p no:cacheprovider
```

## Scope Lock

Stage 3 이후의 어떤 동작도 구현하지 않는다. Stage 2 완료 시: changelog 갱신 → commit/push → Stage 3 scope lock 갱신 후 계속 진행 (사용자 사전 승인 세션).
