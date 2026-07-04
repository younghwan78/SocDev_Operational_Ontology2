# CURRENT_TASK.md

## 활성 Stage

**Stage 1 — 온톨로지 v1.0 계약 + 프로젝트 스캐폴드** (사용자 승인 대기 — 구현 미착수)

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## 목표

56의 스키마 30개를 8개 온톨로지 모듈(project / scenario / ip / event / evidence / role / decision / relation)로 통합 정제하고, 한국어 glossary·JSON Schema 자동 export·시드 fixture 변환·validate CLI·테스트까지 — 이후 모든 Stage의 계약 기반을 완성한다.

상세 계획: `docs/design/02_implementation_roadmap.md` Stage 1 절.

## 기준 가정

- `docs/design/01_system_architecture.md`와 `02_implementation_roadmap.md`가 확정 설계다.
- Pydantic v2 모델이 계약의 단일 소스이며 JSON Schema는 자동 생성물이다.
- `event` + `development_event`는 하나의 DevelopmentEvent 계약으로 통합한다 (development_event 필드셋 기준, 56의 두 fixture 데이터를 모두 수용해야 함).
- 파생 뷰(portfolio board / weekly snapshot / scenario trace)는 저장 계약이 아니다 — Stage 1에서 모델링하지 않는다.
- 모든 저장 객체는 `source_origin` / `source_ref` 메타데이터를 가진다.
- in-memory repository는 테스트/개발 전용 지위다.

## In-scope

```text
uv 프로젝트 스캐폴드 (pyproject, ruff, mypy, pytest, git init, CHANGELOG.md)
backend/ontology/ 8모듈 + common.py + glossary.py + schema_export.py
한국어 glossary (label_ko 전수 정의 + 누락 검출 테스트)
schemas/*.schema.json 자동 export (수동 편집 금지 헤더)
tools/convert_56_fixtures.py — 56 synthetic_data 전량 변환 (56 원본 무수정)
fixtures/*.yaml 변환 결과
backend/loaders/ in-memory repository (ID lookup, 타입별 목록, 참조 무결성)
backend/cli/main.py — validate-data
tests/ — 모델 검증, fixture 로드, 관계 무결성, glossary 커버리지, schema 드리프트
```

## Out-of-scope (Stage 1에서 구현 금지)

```text
PostgreSQL / 마이그레이션 / pgvector
FastAPI / API 엔드포인트
LLM provider / advisory / 프롬프트
frontend
Excel/CSV 반입, JIRA/Confluence 커넥터
임베딩 / semantic retrieval
파생 뷰 (portfolio / weekly / trace)
수치 스코어링, owner 할당, 쓰기 API
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider
uv run ruff check backend tests
uv run mypy
uv run python -m backend.cli.main validate-data   # 오류 0건
```

## 수용 기준

- [ ] 변환 fixture 전량이 모델 검증 통과, `validate-data` 오류 0건
- [ ] event/development_event 통합 계약이 56 두 fixture를 모두 수용
- [ ] 모든 공개 필드·enum에 `label_ko` 존재 (테스트 강제)
- [ ] JSON Schema 재생성 diff 0 (드리프트 차단 테스트)
- [ ] pytest / ruff / mypy 통과

## Scope Lock

Stage 1은 사용자가 명시적으로 승인해야 시작한다. Stage 2 이후의 어떤 동작도 구현하지 않는다. 미래 지향 라벨·플레이스홀더·로드맵 문서는 구현 근거가 아니다. Stage 1 완료 시: changelog 갱신 → Stage 2 scope lock 초안 준비 → 정지.
