# 구현 로드맵 — 전체 상세 계획

> 상태: v1.0 (2026-07-04)
> 선행 문서: `internal_docs/design/01_system_architecture.md`
> 이 문서는 전체 Stage의 상세 계획이다. 각 Stage 시작 시 이 문서에서 해당 Stage를 발췌·구체화하여 `CURRENT_TASK.md` scope lock을 생성한다.

## 0. 진행 규율 (모든 Stage 공통)

1. 한 번에 하나의 Stage만 활성화한다. 활성 Stage는 `CURRENT_TASK.md`가 정의한다.
2. Stage 시작 조건: 사용자의 명시적 승인.
3. Stage 완료 조건: 수용 기준 전체 충족 + 회귀 명령 통과 + `CHANGELOG.md` 갱신.
4. Stage 완료 후: 다음 Stage의 `CURRENT_TASK.md` 초안을 준비하고 **정지**. 자동으로 다음 Stage에 진입하지 않는다.
5. 도메인 의미 변경은 코드 단독으로 하지 않는다: 설계문서 → glossary/모델 → fixture → 테스트 → changelog 순서.
6. `E:\56_Codex_SoC_Operational_Ontology`는 항상 read-only 참조.

표준 회귀 명령 (Stage 1부터 누적 적용):

```bash
uv run pytest -p no:cacheprovider
uv run ruff check backend tests
uv run mypy
uv run python -m backend.cli.main validate-data
# frontend 존재 시 (Stage 4+)
cd frontend && npm run build && npm run test && npm run lint
```

## Stage 1 — 온톨로지 v1.0 계약 + 프로젝트 스캐폴드 [규모: L]

### 목표

56의 스키마 30개를 8개 온톨로지 모듈로 통합 정제하고, 한국어 glossary와 함께 이후 모든 Stage가 딛고 설 계약 기반을 만든다.

### 의존성

없음 (첫 Stage).

### In-scope

1. **프로젝트 스캐폴드**: `pyproject.toml`(uv, Python 3.11+), ruff/mypy/pytest 설정, `.gitignore`, git init, `CHANGELOG.md`.
2. **온톨로지 모델 8모듈** (`backend/ontology/`): Pydantic v2, 56 스키마 통합 매핑(설계문서 §4.2) 적용.
   - `common.py`: ID 규약, `SourceMeta`(source_origin/source_ref/ingested_at), `Confidence` enum, 공통 base.
   - `project.py` `scenario.py` `ip.py` `event.py`(event+development_event 통합) `evidence.py` `role.py` `decision.py` `relation.py`.
3. **한국어 glossary**: 모든 객체 타입/필드/enum의 `label_ko` 정의 (`glossary.py` + export 가능한 `glossary.yaml`). 누락 검출 테스트 포함.
4. **JSON Schema 자동 export**: `schema_export.py` → `schemas/*.schema.json` 생성 (수동 편집 금지 헤더 포함).
5. **시드 fixture 변환**: 56 `synthetic_data/*.yaml` → 58 계약에 맞는 `fixtures/*.yaml` 변환 스크립트(`tools/convert_56_fixtures.py`) + 변환 결과 커밋. 56 원본은 무수정.
6. **In-memory repository** (테스트/개발 전용 지위): 로더 + ID lookup + 타입별 목록 + 참조 무결성 검사.
7. **CLI**: `validate-data` (fixture 로드 + 모델 검증 + 관계 무결성 + glossary 커버리지 보고).
8. **테스트**: 모델 검증, fixture 로드, 관계 무결성, glossary 커버리지, schema export 안정성.

### Out-of-scope

PostgreSQL, FastAPI, LLM provider, frontend, Excel 반입, 임베딩/retrieval, 파생 뷰 (portfolio/weekly/trace).

### 산출물

`backend/ontology/*`, `backend/loaders/*`, `backend/cli/main.py`, `fixtures/*.yaml`, `schemas/*.schema.json`, `tools/convert_56_fixtures.py`, `tests/*`, `CHANGELOG.md`.

### 수용 기준

- [ ] 변환된 fixture 전체가 모델 검증을 통과하고 `validate-data` 오류 0건.
- [ ] event/development_event 통합 계약이 56의 두 fixture 데이터를 모두 수용.
- [ ] 모든 공개 모델 필드·enum에 `label_ko` 존재 (테스트로 강제).
- [ ] JSON Schema가 모델에서 재생성해도 diff 0 (드리프트 차단).
- [ ] `uv run pytest`, `ruff`, `mypy` 통과.

## Stage 2 — PostgreSQL 계층 [규모: M]

### 목표

PostgreSQL을 source of truth로 만드는 저장 계층과 시드 반입 경로를 구축한다.

### 의존성

Stage 1 (온톨로지 계약).

### In-scope

1. `backend/db/`: psycopg3 connection 관리, 버전드 SQL 마이그레이션(`migrations/000N_*.sql`) + 경량 러너.
2. 테이블 설계: 관계 컬럼(ID/타입/프로젝트/시나리오 필터) + JSONB payload + `relations` 테이블 + pgvector-ready `semantic_chunks` (56 Phase3-lite 패턴 승계, 통합 계약 반영).
3. `backend/ingest/yaml_seed.py`: fixture → DB 반입 (멱등, source_origin=synthetic 태깅).
4. PostgreSQL repository: in-memory repository와 동일 인터페이스(`RepositoryProtocol`), 패리티 테스트.
5. CLI: `db-init`, `db-seed`, `db-check`.

### Out-of-scope

pgvector 실제 임베딩 적재, API, LLM, frontend.

### 수용 기준

- [ ] `POSTGRES_TEST_DSN` 게이트 통합 테스트: init → seed → 패리티(메모리 vs DB 동일 결과) 통과.
- [ ] seed 재실행 멱등성 검증.
- [ ] DSN 미설정 시에도 전체 단위 테스트 통과 (DB 없이 개발 가능).

## Stage 3 — 결정론 서비스 + Read-only API [규모: M]

### 목표

실무 리더의 시나리오 분석에 필요한 결정론 서비스와 GET API를 제공한다. LLM 없이도 가치 있는 조회 표면 완성.

### 의존성

Stage 2 (repository).

### In-scope

1. `backend/resolve/`: relation resolver(양방향, 경로 탐색 depth 제한), traceability 조립.
2. `backend/services/`:
   - `scenario_analysis.py`: 시나리오 종합 — 관련 이벤트/이슈/근거/리스크/결정 취합, 근거 공백 진단, 타임라인 구성.
   - `portfolio.py`: U/V/W 현황 파생 뷰 (56 review board 6-lane 개념 통합, 저장하지 않음).
   - `review.py`: 주간 스냅샷/감사/백로그 파생 뷰.
3. `backend/api/`: FastAPI 앱, GET 엔드포인트 (health/meta, projects, scenarios, `scenarios/{id}/analysis`, `scenarios/{id}/timeline`, events, evidence, traceability, portfolio/overview, review 계열).
4. OpenAPI 스키마 export (`openapi.json` 커밋 — frontend 타입 생성 소스).
5. httpx TestClient 기반 API 테스트.

### Out-of-scope

POST 엔드포인트, LLM, frontend, 임베딩 검색.

### 수용 기준

- [ ] 시나리오 하나에 대해 분석/타임라인/traceability가 fixture 데이터로 완결 응답.
- [ ] 모든 응답 모델에 한국어 라벨 메타데이터 동봉 (glossary 소스).
- [ ] repository 백엔드(메모리/DB) 교체 시 API 응답 동일 (패리티 테스트).

## Stage 4 — 한국어 Frontend: 시나리오 상세 화면 [규모: L]

### 목표

1차 페르소나(실무 리더)의 핵심 화면 — **② 시나리오 상세** — 를 한국어 기본으로 신규 구축한다.

### 의존성

Stage 3 (API + openapi.json).

### In-scope

1. Frontend 스캐폴드: Vite + React 19 + TypeScript + react-router + TanStack Query + Vitest + ESLint.
2. `openapi-typescript`로 API 타입 자동 생성 (수동 타입 작성 금지).
3. 화면: 시나리오 목록 → 시나리오 상세 (탭: 개요 / 타임라인 / 이벤트·이슈 / 추적).
4. 공통 traceability 패턴 1종: 어떤 항목이든 클릭 → `supporting_basis` drill-down 패널. 모든 화면이 이 패턴 재사용.
5. 한국어 UI: glossary 기반 라벨, ko 기본 (i18n 구조는 두되 en은 후순위).
6. URL 라우팅: `/scenarios/:id/:tab` — 공유/북마크 가능.

### Out-of-scope

포트폴리오/리뷰/근거탐색 화면, advisory UI, 디자인 시스템 과잉 투자.

### 수용 기준

- [ ] `npm run build && npm run test && npm run lint` 통과.
- [ ] 시나리오 상세 4개 탭이 실제 API로 렌더, 근거 drill-down 동작.
- [ ] UI 문자열에 하드코딩 영어 없음 (glossary/리소스 경유 — 테스트로 강제).

## Stage 5 — LLM Provider Chain + Scenario Advisory [규모: L]

### 목표

Claude CLI(1차) → 사내 on-prem OpenAI 호환(2차) → 결정론 코어(3차) 체인으로 role agent 조언을 생성하고, evidence-grounded validator와 감사 기록으로 통제한다.

### 의존성

Stage 3 (서비스/API), Stage 4 (표시 화면) 권장.

### In-scope

1. `backend/agents/providers/`: `LLMProvider` 프로토콜 + 3개 구현.
   - `claude_cli.py`: headless 실행(`claude -p --output-format json`), 타임아웃/재시도.
   - `openai_compat.py`: 사내 endpoint (base_url/model/key 설정 주입).
   - `deterministic.py`: 56 mock agent 로직 정제 이식 — 항상 가용한 최종 fallback.
2. `backend/agents/runner.py`: 컨텍스트 조립(시나리오 분석 결과 + 관계 + 근거) → role별 프롬프트 → 체인 실행 → 구조화 출력 파싱.
3. `backend/agents/validators.py`: supporting_basis 필수, 근거 약할 때 high confidence 금지, 일반론 거부 — provider 무관 공통 관문.
4. 감사 기록: `agent_run` 저장 (provider/모델/입력 해시/출력/검증 결과/소요시간).
5. 정책 스위치: `allow_external_llm` 설정 (실데이터 반입 대비).
6. API: `POST /api/v1/scenarios/{id}/advisory`. UI: 시나리오 상세에 "조언" 탭 추가.
7. 프롬프트: 한국어 출력 강제, role 책임 경계(CLAUDE.md §2.2) 반영.

### Out-of-scope

멀티 에이전트 자율 토론, 수치 리스크 스코어 자동 산정, 임베딩 retrieval (키워드 후보로 시작).

### 수용 기준

- [ ] provider 계약 테스트 (mock) + fallback 체인 전환 테스트 통과.
- [ ] validator가 근거 없는 출력을 거부/강등하는 테스트 통과 (LLM 실호출 없이).
- [ ] 실행마다 감사 기록 생성, UI에서 provider/확신도 표시.
- [ ] LLM 미가용 환경에서도 결정론 조언으로 기능 유지.

## Stage 6 — 나머지 화면: 포트폴리오 현황 · 리뷰 센터 · 근거 탐색 [규모: M]

### 목표

4화면 체계 완성 (설계문서 §7 흡수 매핑 기준).

### In-scope

1. **① 포트폴리오 현황**: U/V/W 요약, 주의 lane(근거 부족/정의 필요/확신도 차단/전파 검토/리스크 해소 후보/경영 주의), 시나리오×프로젝트 매트릭스 → 클릭 시 시나리오 상세로.
2. **③ 리뷰 센터**: 주간 리포트, 결정·확신도 감사, 리스크 해소 백로그 (탭 구조).
3. **④ 근거 탐색**: evidence 검색/목록, role 활동 조회, 시스템 진단(설정 메뉴).

### 수용 기준

- [ ] 4화면 모두 시나리오 상세의 traceability 패턴 재사용.
- [ ] 화면 간 이동이 URL 기반으로 일관.

## Stage 7 — Excel/CSV 실데이터 반입 파일럿 [규모: M]

### 목표

첫 실데이터를 Excel/CSV로 반입해 synthetic과 병존시키고, 반입 워크플로를 검증한다.

### In-scope

1. `backend/ingest/excel_csv.py`: 매핑 정의(열→온톨로지 필드) 기반 반입, 검증 실패 행 보고서.
2. 우선 대상: 프로젝트/마일스톤, KPI 관측치/측정 근거 (설계문서 §5 매핑 표 1~2단계).
3. `POST /api/v1/ingest/excel` + CLI `ingest-excel`.
4. UI: source_origin 뱃지(가상/반입/연동) 전 화면 표시, 반입 이력 조회.
5. 반입 데이터 격리 정책: 삭제는 반입 단위 rollback만 허용 (개별 객체 수정 API 없음 유지).

### 수용 기준

- [ ] 샘플 Excel로 반입 → 시나리오 분석/포트폴리오에 실데이터 반영 확인.
- [ ] 오류 행 보고서가 어떤 행이 왜 실패했는지 한국어로 설명.
- [ ] 반입 rollback 동작.

## Stage 8~12 — 원점 목표 복원 (2026-07-05 개정, 사용자 승인)

> **설계 기준: `internal_docs/design/03_course_correction.md`** (원점 문서 대비 괴리 진단과 교정 설계).
> Stage 1~7 검증 결과 원점의 TAT 단축 유스케이스 4종이 부재하여 Stage 8+를 아래로 대체한다.
> UI를 "데이터 종류별 화면"에서 "질문이 곧 메뉴인 코크핏"으로 재편한다.

### Stage 8 — 홈 개편 + 위험 지도 [규모: L]

- In-scope: `backend/services/risk.py` 정성 위험 판정 룰(높음/중간/낮음 + 근거 목록, 수치 점수 없음) + 테스트,
  `GET /api/v1/risk/heatmap`, 코크핏 홈(heatmap + 근거 패널 + 이번 주 주목 3~5건),
  내비 재편(위험 지도/변경 영향/이슈 분석/Ask SoC — 미구현 메뉴는 비활성),
  UI 공통 원칙 적용(ID 숨김·색 의미 통일·접기 기본).
- 수용 기준: 홈 진입 10초 내 위험 시나리오 식별 가능(heatmap), 모든 등급이 근거 패널로 drill-down,
  등급 판정이 결정론 테스트로 고정, 기존 화면은 하위 층에서 접근 가능.

### Stage 9 — 변경 영향 [규모: M]

- In-scope: `backend/services/change_impact.py` 그래프 순회 엔진
  (scenario_ip_requirements/ip_knobs/ip_dependency_rules/과거 이슈), `GET /api/v1/change-impact`,
  변경 영향 화면(IP·knob 선택 → 영향 시나리오/KPI/연쇄 IP/역할별 검토 체크리스트/과거 유사 사례),
  체크리스트 내보내기. LLM은 문장화에만 선택 사용.
- 수용 기준: ISP knob 변경 예시로 4분면 출력 완결, 체크리스트가 역할 책임 경계와 일치, 결정론 테스트.

### Stage 10 — RCA 체인 [규모: L]

- In-scope: 온톨로지 확장(Test 객체, RootCause 유형 enum 6종, Issue 확장:
  fix_type/workaround/verifying_test_ids/residual_risk/reusable_lesson),
  원점 문서 §7 archetype 기반 fixture 보강(이슈 30~50건·테스트 30건·RCA 완결 체인),
  RCA 그래프 화면(증상→원인→조치→검증→잔존 리스크→교훈, 근거 뱃지).
- 수용 기준: "검증 테스트 없는 close 이슈"가 시각적으로 드러남, 변경 규율 6단계 준수, schema/openapi 재생성.

### Stage 11 — Ask SoC [규모: M]

- In-scope: 질의 서비스(온톨로지 검색→객체 수집→LLM 근거 인용 답변, 기존 체인·validator 재사용),
  `POST /api/v1/ask`, 홈 검색창 활성화 + 프리셋 질문 5종, 인용 클릭 시 객체 이동.
- 수용 기준: 원점 데모 질문 5종에 근거 인용 답변, validator 미통과 답변 미표시, LLM 미가용 시 검색 결과만으로 동작.

### Stage 12 — 데모 패키지 + 효과 측정 [규모: M]

- In-scope: 데모 스토리 모드(위험 발견→원인→변경 영향→결정 근거 4장면),
  TAT 측정 체계(데모 질문별 질문→근거 도달 시간 기록/비교표), 사내 검증 워크숍 자료(fixture 가설 목록).
- 수용 기준: 4장면 데모가 클릭만으로 진행, TAT before/after 비교표 산출.

## Stage 13+ — 사내 연동 고도화 (이연)

Stage 12 이후 상세 계획 수립 (원점 문서: "ingestion 자동화보다 연결 모델 검증이 먼저"):

- JIRA/Confluence read-only 커넥터 (사내 계정/보안 승인 선행).
- 사내 임베딩 API + pgvector 한국어 시맨틱 검색 (키워드 retriever 대체).
- 검색 결과는 항상 `supporting_basis` 후보로만 진입 (증거 아님 — 56 원칙 유지).
- 운영 파일럿: 실무 리더 1~2명 대상 주간 사용 → 피드백 루프.

## 리스크와 대응

| 리스크 | 영향 | 대응 |
|---|---|---|
| Stage 1 통합 계약이 56 데이터와 어긋남 | 이후 전 Stage 재작업 | 변환 스크립트가 56 fixture 전량을 통과하는 것을 Stage 1 수용 기준으로 강제 |
| Claude CLI headless 운영 제약 (세션/속도/비용) | advisory 지연 | 체인 fallback + 결과 캐시(입력 해시 기준) + 비동기 실행 |
| 사내 API 연동 승인 지연 | Stage 8 지연 | Stage 7 Excel 반입으로 실데이터 가치를 선행 입증 |
| 한국어 glossary 용어 흔들림 | UI/조언 품질 저하 | glossary를 계약으로 관리, 용어 변경은 changelog 필수 |
| frontend 재복잡화 | 56 전철 | 화면 4개 상한 + traceability 패턴 1종 강제 |

## Stage 순서 근거

Backend 계약(1)→저장(2)→서비스/API(3)를 먼저 세우는 이유는 frontend 타입과 화면이 전부 OpenAPI 계약에서 파생되기 때문이다. 시나리오 상세 화면(4)을 LLM(5)보다 먼저 두는 이유는 advisory 결과를 표시할 자리가 먼저 필요하고, 결정론 분석만으로도 실무 리더에게 즉시 가치가 있기 때문이다.
