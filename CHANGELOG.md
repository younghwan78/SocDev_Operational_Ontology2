# CHANGELOG

## Stage 4 — 한국어 Frontend: 시나리오 상세 화면 (2026-07-04)

### 추가

- `frontend/` 신규 구축: Vite + React 19 + TypeScript + react-router v7 + TanStack Query v5.
- API 타입 자동 생성: openapi-typescript(`npm run gen:api`) + openapi-fetch 타입 클라이언트.
  수동 API 타입 없음 (56의 1,463줄 수동 types.ts 방식 폐기).
- 화면:
  - 시나리오 목록 (`/scenarios`): 프로젝트 필터, 그룹/KPI 표시.
  - 시나리오 상세 (`/scenarios/:id/:tab`): 개요(기본 정보·근거 공백·KPI·IP·요청·이슈·
    변형·측정) / 타임라인(주차 그룹) / 이벤트·활동(근거 문장 표시) / 추적.
- 공통 traceability drill-down 패널 (`TraceabilityPanel`): breadcrumb 스택 기반 —
  이후 모든 화면이 재사용할 단일 패턴.
- 한국어 전용 UI: `src/i18n/ko.ts` 단일 소스 + JSX 영어 하드코딩 금지 가드 테스트.
- uvicorn 추가 — `uv run uvicorn backend.api.app:create_app --factory`로 API 구동.
- README: 실행/검증/계약 재생성 가이드.

### 검증

```text
npm run build / test(4 passed) / lint → pass
uvicorn 스모크: health ok, analysis 응답 (gaps 9, timeline 21)
backend 회귀 유지: pytest / ruff / mypy pass
```

## Stage 3 — 결정론 서비스 + Read-only API (2026-07-04)

### 추가

- `backend/resolve/`: `ObjectIndex`(전역 ID 해석, 내장 전파 포함),
  `TraceabilityService`(명시 relations + 암묵 참조 필드의 양방향 링크, 한국어 관계 유형).
- `backend/services/scenario_analysis.py`: 시나리오 종합 — 그룹/변형/KPI/요청/이벤트/
  역할 활동/이슈/근거 카탈로그/측정, 근거 공백 진단(누락·미가용·요구 미충족·확신도 차단),
  주차 타임라인(이벤트·활동·요청·마일스톤).
- `backend/services/portfolio.py`: U/V/W 요약 + 주의 lane 6종(근거 부족/정의 필요/
  확신도 차단/전파 검토/리스크 해소 후보/경영 주의) + 시나리오×프로젝트 매트릭스.
  수치 점수·결정 자동화·담당자 할당 없음 (56 원칙 유지).
- `backend/services/review.py`: 주간 인덱스/스냅샷 파생 뷰.
- `backend/api/`: FastAPI read-only 표면 13개 GET 엔드포인트
  (health/meta/glossary/projects/scenarios/analysis/timeline/events/traceability/
  portfolio/weekly). GET 외 메서드 부재를 테스트로 강제.
- `openapi.json` 커밋 + 드리프트 테스트 — Stage 4 frontend 타입 생성 소스.
- 저장소 백엔드 자동 선택: `SOC_ONTOLOGY_DSN` 설정 시 PostgreSQL, 아니면 in-memory.

### 수정

- `InMemoryRepository.list`가 미지 컬렉션에 KeyError — PostgresRepository와 계약 통일
  (백엔드 간 API 패리티 테스트로 검증).

### 검증

```text
uv run pytest (+ POSTGRES_TEST_DSN) → 53 passed
  - API 패리티: 메모리/PostgreSQL 백엔드 응답 동일 (analysis/portfolio/weekly/traceability)
uv run ruff check / mypy → pass (35 files)
validate-data → 오류 0건 유지
```

## Stage 2 — PostgreSQL 계층 (2026-07-04)

### 추가

- `backend/db/`: psycopg3 연결 관리(`SOC_ONTOLOGY_DSN`), 버전드 SQL 마이그레이션 + 경량 러너.
- `migrations/0001_core.sql`: Phase3-lite 패턴 —
  `ontology_objects`(collection+id PK, 필터 컬럼, JSONB payload, source 추적, GIN 인덱스),
  `relations` 그래프 투영, pgvector-ready `semantic_chunks` 투영.
- `backend/ingest/yaml_seed.py`: fixture 전량 멱등 반입 (ON CONFLICT upsert).
- `backend/db/repository.py`: `PostgresRepository` — payload에서 모델 재구성, 적재 순서 보존.
- `backend/loaders/protocols.py`: `RepositoryProtocol` — in-memory/PostgreSQL 공용 계약.
  `check_integrity`가 protocol 기반으로 일반화됨.
- CLI: `db-init` / `db-seed` / `db-check` (한국어 출력).
- 테스트: DSN 없이 도는 단위 테스트 6건 + `POSTGRES_TEST_DSN` 게이트 통합 테스트 6건
  (시드 건수, in-memory 패리티, 멱등성, PG 위 무결성 0오류, 투영 테이블).

### 검증

```text
uv run pytest -p no:cacheprovider → 24 passed, 6 skipped (DSN 게이트)
POSTGRES_TEST_DSN=... uv run pytest -m postgres → 6 passed (pgvector/pg16, soc58_test DB)
uv run ruff check / mypy → pass
validate-data → 오류 0건 유지
```

## Stage 1 — 온톨로지 v1.0 계약 + 프로젝트 스캐폴드 (2026-07-04)

### 추가

- uv 기반 프로젝트 스캐폴드: pyproject.toml, ruff/mypy/pytest 설정.
- `backend/ontology/` 8모듈 온톨로지 계약 (Pydantic v2, extra="forbid"):
  - project / scenario / ip / event / evidence / role / decision / relation.
  - 56의 스키마 30개를 통합: `event` + `development_event` → `DevelopmentEvent` 단일 계약.
  - 파생 뷰(portfolio board, weekly snapshot, scenario trace)는 저장 계약에서 제외.
  - 모든 저장 객체에 `source(origin/ref/ingested_at)` 출처 메타데이터.
  - 런타임 계약: `RoleOutput`, `GroundedStatement` (Stage 5 advisory 대비).
- 한국어 glossary (`backend/ontology/glossary.py`):
  - 전 모델/필드/enum의 label_ko — 커버리지 테스트로 강제.
  - `Confidence` enum이 56의 H/M/L 축약 표기를 정규화.
- JSON Schema 자동 export (`backend/ontology/schema_export.py`) → `schemas/` 33개.
  - 수동 3중 동기화(56 방식) 폐기 — Pydantic 모델이 단일 소스.
  - 드리프트는 테스트로 차단.
- 56 fixture 전량 변환 (`tools/convert_56_fixtures.py`) → `fixtures/` 8파일 465건.
  - id 별칭 필드(event_id, activity_id 등 8종) 제거 — 동일성 검증 후.
  - 구 events.yaml 4건을 DevelopmentEvent로 승격 (`event_category=legacy_event`).
  - `IPBaseSpec.spec_id`는 별칭이 아닌 원본 스펙 식별자로 판별되어 유지.
- In-memory repository + 참조 무결성 검사 (`backend/loaders/`):
  - 하드 참조(프로젝트/시나리오/IP/역할/이벤트/마일스톤/요청/전파/근거) 오류 0건.
  - 56 원본 데이터 자체의 느슨한 참조(시나리오 그룹의 미등록 시나리오 15건)는 경고로 분류.
- CLI `validate-data`: 적재 + 검증 + 무결성 + glossary 커버리지 보고 (한국어 출력).
- 테스트 18건: 적재/모델 계약/무결성/glossary/스키마 드리프트/변환 회귀(56 존재 시).

### 검증

```text
uv run pytest -p no:cacheprovider  → 18 passed
uv run ruff check backend tests tools → pass
uv run mypy → pass (18 files)
uv run python -m backend.cli.main validate-data → 오류 0 / 경고 15 / glossary 누락 0
```

## 설계 확정 (2026-07-04)

- `docs/design/01_system_architecture.md`: 운영 시스템 아키텍처 확정 — LLM 3단 체인
  (Claude CLI → 사내 on-prem → 결정론), PostgreSQL-first, 온톨로지 8모듈, 한국어 1급.
- `docs/design/02_implementation_roadmap.md`: Stage 1~8+ 전체 상세 계획.
