# CURRENT_TASK.md

## 활성 Stage

**Stage 4 — 한국어 Frontend: 시나리오 상세 화면** (진행 중 — 연속 Stage 진행 사전 승인 세션)

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## Stage 1~3 완료 기준선

```text
온톨로지 v1.0 계약 + 한국어 glossary + fixture 465건 (무결성 오류 0)
PostgreSQL 계층 (마이그레이션/시드/repository, 실DB 패리티 검증)
결정론 서비스: 시나리오 분석 / 포트폴리오 lane 6종 / 주간 리뷰 / traceability
FastAPI read-only 13 엔드포인트 + openapi.json (드리프트 테스트)
테스트 53건 (PG 통합 포함) / ruff / mypy 통과
```

---

## Stage 4 목표

1차 페르소나(실무 리더)의 핵심 화면 — **시나리오 상세** — 를 한국어 기본으로 신규 구축한다.
상세: `docs/design/02_implementation_roadmap.md` Stage 4 절.

## 기준 가정

- API 계약은 openapi.json이 단일 소스 — 타입은 openapi-typescript로 자동 생성한다.
- 화면은 4개 상한 체계(포트폴리오 현황/시나리오 상세/리뷰 센터/근거 탐색)의 ②부터 만든다.
- traceability drill-down 패턴 1종을 만들고 이후 모든 화면이 재사용한다.
- UI 문자열은 한국어 기본. glossary API(/api/v1/meta/glossary)를 라벨 소스로 쓸 수 있다.
- 56 frontend는 참조만 한다 — 코드 복사 금지.

## In-scope

```text
frontend/ 스캐폴드: Vite + React 19 + TypeScript + react-router + TanStack Query + Vitest + ESLint
openapi-typescript 타입 자동 생성 (수동 API 타입 금지)
시나리오 목록 화면 (프로젝트 필터)
시나리오 상세 화면: 개요 / 타임라인 / 이벤트·이슈 / 추적 탭 (URL: /scenarios/:id/:tab)
공통 traceability drill-down 패널
한국어 라벨 (glossary 연동), 하드코딩 영어 금지
컴포넌트 테스트 (Vitest + Testing Library)
```

## Out-of-scope (Stage 4에서 구현 금지)

```text
포트폴리오 현황 / 리뷰 센터 / 근거 탐색 화면 (Stage 6)
advisory UI (Stage 5)
디자인 시스템 과잉 투자, 다크모드 등 부가 기능
i18n 다국어 전환 UI (구조만 허용)
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
cd frontend && npm run build && npm run test && npm run lint
```

## Scope Lock

Stage 5 이후의 어떤 동작도 구현하지 않는다. Stage 4 완료 시: changelog 갱신 → commit/push → Stage 5 scope lock 갱신 후 계속 진행.
