# CHANGELOG

## Stage 10 — 이슈 분석: RCA 체인 + Test 온톨로지 확장 (2026-07-06)

> "이 이슈의 원인은? 정말 해결됐나?" — **close됐지만 검증 테스트가 없는 이슈가
> 빨갛게 드러나는 것**이 이 화면의 존재 이유 (`internal_docs/design/04_stage10_rca_design.md`).
> 변경 규율 6단계(설계→모델→schema→fixture→테스트→changelog) 준수.

### 온톨로지 확장 (event 모듈)

- `Test` 저장 객체 신설 (컬렉션 `tests`): test_type(regression/scenario/cts_vts/power),
  result(passed/failed/blocked/planned), 시나리오/이슈/근거 연결, 실행 주차.
- `RootCauseType` enum 6종 (원점 문서 분류 승계): architecture_miss / spec_ambiguity /
  verification_gap / power_model_error / sw_workaround_dependency / customer_scenario_mismatch.
- `RootCause` 구조화 (유형/서술/확신도/근거) + `Issue` 확장: root_causes, fix_type,
  fix_description, workaround, verifying_test_ids, residual_risk, reusable_lesson,
  resolved_week — 전부 optional, 56 유래 이슈 4건 무변경 통과.
- glossary label_ko 전체 추가, JSON Schema/openapi 재생성, 무결성 검사 확장
  (tests↔issues/scenarios/projects hard 참조, issue affected_scope 검증).

### 56 드리프트 재동기화

- `Variant.source_basis` 추가 후 변환기 재실행 — 56의 2026-07-05 갱신 반영
  (변형 +1건 matched_baseline, 측정 요구 +2건, 관계 +18건). **converter roundtrip 복구.**
- 로더에 `<module>_58.yaml` 오버레이 지원: 56 생성물과 58 전용 synthetic을 분리 관리
  (id 충돌 거부, 계보 ref `58:fixtures/...`). roundtrip 테스트는 `_58` 제외 비교.

### Fixture 보강 (`fixtures/event_58.yaml`)

- 원점 문서 §7 archetype 기반 이슈 **32건** (ISP 7 / DPU 6 / Codec 6 / Audio 6 / DDR·NoC 7)
  + 검증 테스트 **30건**. 상태 구성: RCA 완결 체인(전부 통과) 5건+,
  **검증 테스트 없는 close 이슈 3건**(수용 기준 사례), failed/planned 미검증, workaround 의존,
  open 후보 단계 혼재. validate-data 무결성 오류 0 유지.

### RCA 서비스 + 화면

- `backend/services/rca.py`: 7단 체인 파생 뷰 — 증상→영향→원인→조치→검증 테스트→
  잔존 리스크→재사용 교훈. 노드별 근거 뱃지(green/red/yellow) + 판정 사유.
  검증 상태(verified/unverified/no_tests), 종결+미검증 경고. 원인은 기록된 데이터만
  표시(LLM 추론 없음).
- API: `GET /api/v1/issues`(project/verification 필터, 경고 이슈 선두 정렬),
  `GET /api/v1/issues/{id}/rca`.
- Frontend `IssueAnalysisPage`(`/issues`, 내비 '이슈 분석' 활성화): 이슈 목록(검증 뱃지,
  경고 빨간 강조) → 세로 RCA 흐름(색 보더+뱃지+사유). UI 공통 원칙 준수.
- `docs/` 가이드에 `issues.md` 추가 (뱃지 규칙/원인 유형 6종 해석, 스크린샷 2장).

### 검증

```text
backend 117 passed(+rca 12, api 1) / 0 failed — converter roundtrip 포함 전부 green
ruff / mypy pass · frontend build / test(15) / lint pass · validate-data 오류 0
E2E: 실구동 — 이슈 36건 목록(경고 3건 선두·빨간 강조), 검증 없는 close 이슈의
  검증 노드 red + 경고 배너, 완결 체인 이슈 all-green(테스트 2건 통과) 확인.
```

## Stage 9 — 변경 영향 (Change Impact) (2026-07-05)

> "이 IP/knob을 바꾸면 어디에 영향이 가나?" — TAT 효과 1위 유스케이스 복원
> (`internal_docs/design/03_course_correction.md` §4.2). 결정론 그래프 순회만 사용, LLM 불개입.

### 추가

- `backend/services/change_impact.py`: 결정론 그래프 순회 엔진 (파생 뷰, 저장 없음).
  - 입력: IP 필수 + knob/capability/모드 선택. knob·capability·모드가 구체 링크를 만들면
    그 시나리오로 한정, 아니면 IP 수준(사용/의존+전체 요구)으로 확장.
  - 순회: scenario_ip_requirements → 영향 시나리오 → primary_kpis /
    ip_dependency_rules → 연쇄 IP(양방향: 선택 IP가 의존 ↔ 선택 IP에 의존, 조건 표시) /
    ip_knobs → 방향성(전력·지연·대역폭·리스크)·affected_kpis·related_scenarios /
    같은 IP 조합의 과거 이슈·이벤트 → 유사 사례(겹침 시나리오 명시).
  - **역할별 검토 체크리스트**: 역할 책임 경계(CLAUDE.md §2.2) 반영 — HW/SW는
    "feedback_items로 전달" 명시, Management는 "구현 세부 결정 아님". 트리거 근거가 있을
    때만 항목 생성 (일반론 금지, 테스트로 강제). 체크리스트 내보내기 텍스트 조립.
  - capability↔요구 매칭은 보수적 토큰 부분집합 일치만 — 근거 없는 연결 금지.
  - `services/common.py` `BasisItem` 신설 — risk 파생 뷰와 근거 항목 계약 공용화
    (`ip_match_tokens`/`event_related_ips`도 공용 승격).
- API: `GET /api/v1/change-impact`(ip_id/knob_id/capability_id/mode, 404/400 검증),
  `GET /api/v1/change-impact/options`(폼 옵션 — IP별 knob/capability/모드).
- Frontend `ChangeImpactPage`(`/change-impact`, 내비 활성화):
  IP→knob/capability/모드 셀렉트 → [분석 실행] → knob 방향성 뱃지 + 4분면
  (영향 시나리오/영향 KPI(knob 직접 ★ 우선)/연쇄 IP/역할별 체크리스트) + 과거 유사 사례.
  체크리스트 클립보드 복사. UI 공통 원칙(ID 숨김·색 의미·접기) 준수.

### 검증

```text
backend 103 passed(+change_impact 15, api 1) / 1 failed(기존 56 드리프트 — Stage 8 기록 참조)
ruff / mypy pass · frontend build / test(12) / lint pass
validate-data → 오류 0건 유지
E2E: ISP×pixel_mode 실구동 — 4분면 완결, 역할 경계 문구, 유사 사례 10건(이슈 우선),
  체크리스트 복사 "복사됨" 확인. API 프로브: 미지 IP 404 / knob-IP 불일치 400.
```

## Stage 8 — 홈 개편 + 위험 지도 (2026-07-05)

> 방향 교정(`internal_docs/design/03_course_correction.md`) 첫 구현 — 원점 문서의
> Milestone Risk Early Warning 복원. UI를 "질문이 곧 메뉴인 코크핏"으로 재편 시작.

### 추가

- `backend/services/risk.py`: 시나리오×IP **정성 위험 등급** 결정론 룰 (파생 뷰, 저장 없음).
  - 셀 룰: 미해결 이슈(높음) / 확신도 차단 근거(상한 low=높음, medium=중간 — 가중 차등) /
    일정 위험 신호 at_risk·delayed·window_closing(고심각도 결합 시 높음) / 고심각도 이벤트(중간) /
    요구 근거 미충족(중간) / 과거 유사 이슈(중간). 신호 없으면 낮음 + `no_signal` 근거.
  - 시나리오 종합 룰: 셀 최고 등급 + P0 요청 근거 부족(높음) / P1 요청(중간) / 근거 공백 누적 ≥3(중간).
  - **모든 등급은 판정 근거 목록(원본 객체 ref) 동반 — 근거 없는 등급 없음. 수치 점수 산출·표시 없음**
    (CLAUDE.md §6.3 승인 범위, 테스트로 강제).
  - 이벤트→IP 귀속은 IPBlock의 domain/aliases 토큰과 candidate option의 명시 참조로만 판별
    (synthetic ID 하드코딩 없음). heatmap 열도 시나리오가 참조하는 블록에서 파생 (10열, ip_cpu 제외).
  - "이번 주 주목" 3~5건: P0/P1 요청 근거 부족 → 확신도 차단 → 일정 위험 순, 최근 주차 우선.
- API: `GET /api/v1/risk/heatmap`(project_id 필터, 열은 필터와 무관하게 고정),
  `GET /api/v1/meta/labels`(내부 ID→표시명 — ID 숨김 원칙 지원).
- Frontend 홈 개편:
  - 내비 재편 — 위험 지도(홈) / 변경 영향·이슈 분석·Ask SoC(비활성, Stage 9~11 예정) /
    "데이터 탐색" 하위 그룹(기존 4화면 유지).
  - `RiskMapPage`: 프로젝트 탭 U/V/W, ●◐○ heatmap(위험 시나리오 우선 정렬), 셀/행 클릭 →
    판정 근거 패널 → 기존 시나리오 상세로 drill-down (3클릭 내 원본 근거 도달).
- UI 공통 원칙 전 화면 적용:
  - 내부 ID 숨김 — `useLabels` 훅으로 프로젝트/시나리오/그룹/IP/역할 ID를 표시명으로 렌더
    (ID는 hover title에만). 컴포넌트 가드 테스트로 강제.
  - 색 의미 통일 — 빨강=위험, 노랑=주의, 초록=정상 (`risk-high/medium/low`).
  - 접기 기본 — `CollapsibleList`(상위 5건+더 보기), 포트폴리오 주의 lane 44건 나열 문제 해소.

### 알려진 문제 (Stage 8 범위 밖 — 사용자 결정 필요)

- `test_converter_roundtrip` 1건 실패: 56 참조 데이터가 2026-07-05 15:23에 갱신됨
  (variants 5→6건, Variant에 `source_basis` 필드 추가, scenarios/relations/measurement_requirements 변경)
  — Stage 1 변환 스냅샷과 드리프트. 동기화는 온톨로지 계약·fixture 변경(변경 규율 6단계)이라
  별도 승인 필요. Stage 8 코드와 무관.

### 검증

```text
backend 87 passed / 1 failed(위 드리프트) / ruff / mypy pass
frontend build / test(9) / lint pass — RiskMapPage 3건 + ID 숨김 가드 포함
validate-data → 오류 0건 유지
E2E: uvicorn 8155 + vite 5275 실구동 — heatmap 렌더/셀 drill-down/프로젝트 탭 전환/
  주목 5건/포트폴리오 접기·표시명 브라우저 확인. 미지 project_id→빈 결과 200, DELETE→405.
```

## Stage 7 — Excel/CSV 실데이터 반입 파일럿 (2026-07-04)

### 추가

- `backend/ingest/tabular.py`: CSV(UTF-8/CP949)·XLSX 파서.
- `backend/ingest/mappings.py`: **한국어 열 이름** → 온톨로지 필드 매핑 레지스트리.
  1차 매핑: 프로젝트 마일스톤, 측정 근거. 리스트 열(`;` 구분)/정수 열 변환 지원.
- `backend/ingest/service.py`: 반입 서비스 — 파싱 → 매핑 → 모델 검증 → 배치 저장.
  - 실패 행은 한국어 사유와 행 번호로 보고 (`필수 열 누락`, `형 변환 실패`, 필드 검증 실패).
  - 모든 반입 객체는 `source.origin=imported` + `import:<배치>:<파일>#row<N>` 계보.
  - **rollback은 배치 단위만** — 개별 객체 수정/삭제 API는 계속 부재.
  - synthetic 데이터는 rollback의 영향을 받지 않음 (테스트 강제).
- 저장 백엔드별 writer: `MemoryIngestWriter`(개발) / `PostgresIngestWriter`(운영,
  마이그레이션 `0003_ingest_batches.sql`).
- API: `POST /api/v1/ingest/file`(multipart), `GET /api/v1/ingest/batches`,
  `POST /api/v1/ingest/batches/{id}/rollback`.
- CLI: `ingest-file --file --mapping [--dsn]` (DSN 없으면 검증만), `ingest-rollback`.
- UI: `SourceBadge`(가상/반입/연동) — 근거 탐색에 표시, 반입 이력 카드.
- 샘플: `samples/sample_milestones.csv` (한국어 헤더).

### 검증

```text
backend 82 passed (+PG: 반입→조회→rollback 왕복 포함) / ruff / mypy pass
frontend build / test(5) / lint pass
validate-data → 오류 0건 유지
```

## Stage 6 — 포트폴리오 현황 · 리뷰 센터 · 근거 탐색 (2026-07-04)

### 추가

- 4화면 체계 완성 (헤더 내비게이션: 포트폴리오/시나리오/리뷰 센터/근거 탐색).
- **① 포트폴리오 현황** (`/portfolio`): U/V/W 프로젝트 요약 카드, 주의 lane 6종
  (근거 부족/정의 필요/확신도 차단/전파 검토/리스크 해소 후보/경영 주의),
  시나리오×프로젝트 매트릭스 (요청/이벤트/근거 공백 카운트) — 셀 클릭 시 시나리오 상세.
  "참여 권장이며 담당 지정 아님 · 수치 점수 없음 · 결정 아님" 원칙을 화면에 명시.
- **③ 리뷰 센터** (`/review/:week?`): 주차 선택 → 이벤트/역할 활동/요청 스냅샷.
- **④ 근거 탐색** (`/evidence`): 근거 카탈로그 목록, 프로젝트/가용성 필터,
  측정/예측 구분, 시나리오 링크.
- `AttentionItem.scenario_ids` 추가 — 주의 항목에서 시나리오 상세로 직접 이동.
- API: `GET /api/v1/evidence` (project_id/scenario_id/availability 필터).

### 검증

```text
backend 73 passed (+ PG) / ruff / mypy pass
frontend build / test(5) / lint pass
```

## Stage 5 — LLM Provider Chain + Scenario Advisory (2026-07-04)

### 추가

- `backend/agents/providers/`: `LLMProvider` 프로토콜 + 3단 체인.
  - `claude_cli`(1차, 외부): headless 실행 `claude -p --output-format json`, 타임아웃/오류 처리.
  - `openai_compat`(2차, 사내): chat/completions 호환, `SOC_ONPREM_BASE_URL/MODEL/API_KEY`.
  - 결정론 어드바이저(3차, 내장): 근거 공백/일정 신호/측정 요구 규칙 기반 — 항상 가용.
- `backend/agents/validators.py`: evidence-grounded 검증 관문 (provider 무관 필수 통과) —
  supporting_basis 필수·미해석 근거 거부·일반론 거부·근거 약한 high confidence 금지.
- `backend/agents/runner.py`: 컨텍스트 조립(분석 결과 → 압축 JSON) → 역할별 프롬프트(한국어
  출력 강제, 역할 책임 경계 반영) → 체인 실행 → 검증 → `RoleAdvisory` 채택.
- 감사 기록 `AgentRun`: provider/모델/입력 해시/검증 기록/소요시간.
  `InMemoryRunStore` + `PostgresRunStore`(마이그레이션 `0002_agent_runs.sql`).
- 정책 스위치 `SOC_ALLOW_EXTERNAL_LLM=false` → 외부(사외) LLM 건너뜀 (실데이터 보안 대비).
  체인 구성은 `SOC_ADVISORY_PROVIDERS` 환경변수.
- API: `POST /api/v1/scenarios/{id}/advisory`(생성), `GET`(기록 조회).
  데이터 수정 엔드포인트는 여전히 없음 (PUT/PATCH/DELETE 부재를 테스트로 강제).
- 런타임 계약 `RoleAdvisory` 추가 + JSON Schema/openapi/frontend 타입 재생성.
- Frontend: 시나리오 상세에 "조언" 탭 — 생성 버튼, 역할별 조언 카드
  (생성 엔진/확신도 뱃지, 근거 문장, 검증 기록 표시).

### 실 E2E 검증 기록

실제 Claude CLI(haiku)로 PM 역할 advisory를 2회 실행:

1. 1차: LLM이 근거 공백 9건 상황에서 high confidence 출력 → **validator가 거부하고
   결정론 fallback 채택** (감사 기록에 거부 사유 보존). 검증 관문이 설계대로 동작.
2. 프롬프트에 "근거 공백 존재 시 high 금지" 규칙 명시 후 2차: **claude_cli 출력이
   validator 통과** — medium confidence, 해석 가능한 근거 ID 인용
   (req_v_emulator_power_unknown_w24 등), 한국어 조언, 검증 기록 0건.

### 검증

```text
uv run pytest (+ POSTGRES_TEST_DSN) → 71 passed (agents 16건, PG run store 왕복 포함)
frontend build / test / lint → pass
uv run ruff check / mypy → pass (45 files)
```

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

- `internal_docs/design/01_system_architecture.md`: 운영 시스템 아키텍처 확정 — LLM 3단 체인
  (Claude CLI → 사내 on-prem → 결정론), PostgreSQL-first, 온톨로지 8모듈, 한국어 1급.
- `internal_docs/design/02_implementation_roadmap.md`: Stage 1~8+ 전체 상세 계획.
