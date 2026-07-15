# 16. Digital Twin 갭 후속 4패키지 — as-of·프로세스 신호·KPI 시계열·what-if

> 2026-07-15 착수. 2026-07-14 digital twin 갭 분석과 시간 모델(15_temporal_model.md)의
> 후속 — T1+T2가 놓은 시간축(append-only `object_versions`) 위에 4개 능력을 세운다.
> 사용자 승인: "다음 후보(T3 as-of 재구성, KPI 시계열, 프로세스 신호, what-if 주입)를
> 이어서 진행" (2026-07-15).

## 0. 공통 원칙 (전 패키지 하드 제약)

- **전부 결정론.** LLM 무관여. 수치 리스크/우선순위 점수 금지 — 정성 등급·사실 서술만.
- **쓰기 경로 신설 없음.** what-if 포함 모든 계산은 ephemeral — 온톨로지 저장소에
  쓰지 않는다. 유일한 예외는 P3의 fixture/반입 매핑(기존 ingest 관문 경유).
- 모든 판정·비교·가정에 근거 ref 동반. 가정은 `assumption`으로 명시, confidence ≤ medium.
- 한국어 1급: 신규 값 도메인·필드는 glossary/VALUE_LABELS, UI 문자열은 `ko.ts` 경유.
- 시간 의미론은 설계 15 §3 그대로 — transaction time(`recorded_at`)과
  domain time(`week`)을 섞지 않는다. P1·P2는 transaction time, P3은 domain time 위다.

## 1. 패키지 구성과 구현 순서

| # | 패키지 | 시간축 | 내용 | 커밋 단위 |
|---|---|---|---|---|
| P1 | 프로세스 신호 정밀화 | transaction | 전이 이력 기반 정체·재개 판정 (J3 보강) | 1 |
| P2 | T3 as-of 재구성 | transaction | 임의 시점 상태 재생 → 위험 지도 재계산 | 1 |
| P3 | KPI 시계열 | domain | `KPIObservation` 계약 신설 + 과제 간 시점 정렬 비교 | 1 |
| P4 | what-if 주입 | (현재) | 가정 주입 → 위험 지도 delta (ephemeral overlay) | 1 |

P1→P2는 같은 읽기 확장(`collection_versions`)을 공유하므로 P1이 선행.
P3은 계약 변경 규율(모델→스키마→fixture→테스트) 체인이 길어 독립 커밋.
P4는 P1~P3과 독립이나 RiskService 재사용 방식이 P2와 동형이라 마지막.

## 2. P1 — 프로세스 신호 정밀화 (전이 이력 기반 정체·재개)

### 문제

J3 정체 판정(rca.py `_freshness`)은 `updated_week` 단일 값 의존 — 반입 데이터가
그 열을 안 주면 침묵하고, "닫혔다 다시 열림(재개)" 같은 프로세스 이상은 아예 못 본다.
T2가 만든 상태 전이 이력이 그 재료다 (원점 아이디어 3 "blocker가 N주 이상 open").

### 설계

- `IngestWriterProtocol` 읽기 확장 (P2와 공유):

  ```python
  def collection_versions(self, collection: str) -> list[ObjectVersion]: ...
  # Memory: 리스트 필터 / PG: SELECT ... WHERE collection=%s ORDER BY object_id, version
  ```

  `IngestService.collection_versions(collection)`로 노출. 객체별 N+1 조회 금지 —
  컬렉션 단위 1회 조회 후 메모리 그룹핑.

- `RCAService(repo, versions=None)` — 선택적 버전 소스(`IngestService`).
  fixture-only 환경(버전 없음)에서는 기존 주차 기반 판정으로 자동 폴백.
- 판정 (전부 사실 서술 + 전이 ref):
  - **재개(reopened)**: 전이 중 `from_status ∈ 종결셋 → to_status ∉ 종결셋`이 있으면
    true. 문구: "재개 — v{N}에서 '{from}'→'{to}' ({날짜})".
  - **전이 기반 정체**: 미해결 + 마지막 버전 `recorded_at`이 기준 시점보다
    `_STALE_DAYS`(28일) 이상 과거. 기준 시점 = 그 컬렉션 버전 로그의 최신
    `recorded_at`(결정론 — 벽시계 불사용, `_reference_week`와 같은 원리).
    주차 기반 정체와 OR 결합 — 문구에 어느 근거인지 명시.
- `IssueSummary` 확장: `reopened: bool = False`, `last_activity_at: str | None = None`
  (freshness_ko 문구에 근거 병기). `RCAChain`에도 `reopened` + alert 보강
  (재개된 미해결 이슈 경고).
- UI: 이슈 목록에 "재개" 배지, RCA 헤더에 재개 경고. `ko.ts` 경유.

### 수용 기준

1. ingest로 open→closed→open 전이를 만든 이슈가 `reopened=true` + 전이 근거 문구.
2. 버전 이력이 없는 fixture 이슈는 기존 주차 기반 판정과 결과 동일 (회귀 무변화).
3. 마지막 활동이 기준 시점 대비 28일 이상 과거인 미해결 이슈에 정체 신호 + 날짜 근거.

## 3. P2 — T3 as-of 재구성 (설계 15 §4.4 잔여)

### 의미론 (transaction time 전용)

"그 시점에 twin이 알던 것"을 재생한다. 규칙 (컬렉션별):

| 객체 상태 | as-of 처리 |
|---|---|
| 버전 이력 없음 (캡처 이전 시드/synthetic) | **현재 상태 그대로 포함** — "캡처 이전부터 존재" 가정. 응답 meta에 가정 건수 명시 |
| `recorded_at ≤ ts`인 버전 존재 | 그중 최신 버전 적용 — retracted면 제외, 아니면 그 payload |
| 모든 버전이 ts 이후, 첫 버전이 `created` | 제외 (그 시점 twin은 몰랐다) |
| 모든 버전이 ts 이후, 첫 버전이 `updated` | 캡처 이전부터 존재했으나 당시 payload 미상 — **가장 이른 기록 payload로 근사**, meta의 근사 건수로 명시 |

거짓 정밀도 방지: 근사·가정을 숨기지 않고 `AsOfMeta`로 응답에 동반한다.

### 구현

- `backend/services/as_of.py` — `AsOfService(repo, versions_source)`:
  - `snapshot(ts) -> tuple[InMemoryRepository, AsOfMeta]`: 규칙 적용 후 payload를
    `COLLECTIONS` 모델로 `model_validate`해 스냅샷 repo 구성 (검증 실패 행은
    meta에 카운트하고 건너뜀 — 죽지 않는다).
  - `AsOfMeta { as_of, replayed_versions, approximated_objects,
    precapture_assumed_objects, skipped_invalid, note_ko }`.
- API: `GET /api/v1/as-of/risk/heatmap?ts=<ISO8601>&project_id=` →
  `AsOfRiskHeatmap { meta: AsOfMeta, heatmap: RiskHeatmap }`.
  ts 파싱 실패는 400. 파생 뷰 재계산은 기존 `RiskService(snapshot_repo)` 재사용 —
  읽기 경로 무변경 원칙(설계 15 대안 B) 유지: as-of는 별도 표면이지
  기존 조회의 시간 매개변수화가 아니다.
- UI: 위험 지도에 "시점 재구성" 컨트롤(datetime-local) — 설정 시 as-of 응답으로
  전환 + 상단 배너(기준 시각·재생 버전 수·근사/가정 건수). 해제 시 현재 뷰 복귀.
- 성능: 요청마다 전체 재생 — 파일럿 규모(수천 객체)에서 무시 가능. 캐시는
  이력이 커지는 Stage 19 시점에 재평가 (설계 15 §4.5 retention과 동일 지위).

### 수용 기준

1. 반입→갱신→rollback 시나리오에서 각 시점 ts에 대해 재생 상태가 규칙표와 일치
   (갱신 전 ts → 옛 payload, rollback 후 ts → 제외, 재생성 후 ts → 새 payload).
2. 버전 없는 synthetic 객체는 항상 포함되고 meta에 가정 건수로 잡힌다.
3. as-of 위험 지도가 현재 지도와 동일 규칙·동일 계약(RiskHeatmap)으로 계산된다.
4. `test_no_write_endpoints` 불변 (GET only).

## 4. P3 — KPI 시계열 (`KPIObservation` 계약 신설)

### 문제

CLAUDE.md §2.3 event 모듈에 `KPIObservation`이 명시돼 있으나 코드에 부재(계약 드리프트).
KPI의 시간에 따른 궤적(과제 간 "같은 시점(마일스톤 정렬)에 어디까지 왔었나" 비교)을
담을 저장 계약이 없다 — `MeasurementEvidence`는 week가 없어 시계열이 못 된다.

### 계약 (변경 규율: 설계문서 → 모델 → 스키마 재생성 → fixture → 테스트 → changelog)

```python
class KPIObservation(OntologyObject):     # event 모듈 (CLAUDE.md §2.3)
    project_id: str
    kpi_id: str                            # kpi_definitions 참조
    scenario_id: str | None = None
    variant_id: str | None = None
    week: int                              # domain time — 우주/ISO 주차
    value: float                           # 수치 관측값 (정성 결과는 measurement_evidence 영역)
    unit: str | None = None                # 비면 KPIDefinition.unit 승계 표시
    measurement_stage: str | None = None   # evidence_catalog와 동일 도메인
    source_kind: str | None = None
    source_ref: str | None = None
    evidence_id: str | None = None         # 근거 연결 (soft)
    notes: list[str] = []
```

- `COLLECTIONS["kpi_observations"] = ("event", KPIObservation)`. glossary 라벨 등록.
- 무결성 검사: `project_id`(hard), `kpi_id`(hard), `scenario_id`(warning) 참조 추가.
- fixture: `fixtures/event.yaml`에 synthetic 시계열 — U/V 프로젝트 × 2개 KPI
  (예: `dou_power`, `ddr_bw`) 각 4~6점, 기존 시나리오/근거 ref에 앵커.
- 반입 매핑 `kpi_observations`(라벨 "KPI 관측") — 관측 ID/프로젝트 ID/KPI ID/
  시나리오 ID/주차/값/단위/측정 단계/출처 참조/근거 ID. 주차는 int, 값은
  Pydantic lax 변환(str→float).

### 서비스·API

- `backend/services/kpi_series.py` — `KPISeriesService(repo)`:
  - `catalog()`: 관측이 존재하는 KPI 목록(정의 메타 + 프로젝트별 건수) — UI 선택기용.
  - `series(kpi_id, scenario_id=None, project_ids=None, align_milestone_type=None)`:
    프로젝트별 주차 정렬 시계열. `align_milestone_type` 지정 시 각 프로젝트의 해당
    마일스톤 주차를 0으로 하는 `aligned_week`를 병기(마일스톤 없는 프로젝트는
    비정렬 + 사유 명시) — **과제 간 시점 정렬 비교**의 결정론 구현.
  - 추세 서술: 프로젝트별 첫→마지막 값과 `KPIDefinition.direction` 대조 →
    "개선/악화/변화 없음" **사실 서술** + 관측 ref 목록 (점수 아님).
- API: `GET /api/v1/kpi/catalog`, `GET /api/v1/kpi/series?...`.
- UI: 시나리오 상세에 "KPI 시계열" 섹션 — primary KPI 선택 → 주차×프로젝트 표
  + 추세 문구. (차트 라이브러리 도입 없음 — 표가 계약, 시각화는 후속.)

### 수용 기준

1. JSON Schema/openapi 재생성 후 계약 드리프트 게이트 green (`validate-data` 포함).
2. 정렬 비교: 같은 KPI에 대해 U/V가 마일스톤 기준 상대 주차로 비교되고,
   마일스톤 없는 프로젝트는 비정렬 사유가 명시된다.
3. 반입 왕복: KPI 관측 CSV 반입 → series에 반영 → rollback 시 제거.
4. 추세 서술이 direction을 반영한다 (lower_is_better에서 값 감소 = 개선).

## 5. P4 — what-if 주입 (가정 실험, ephemeral)

### 문제

원점 문서의 what-if("이 이슈가 안 풀리면/풀리면 무엇이 달라지나")가 부재.
`SimulationRun`은 56 보존용 죽은 계약 — 본 패키지는 그것을 쓰지 않는다
(감사 기록도 만들지 않는다: 결정론 계산이라 재현 가능, 저장할 상태가 없다).

### 설계

- `backend/services/what_if.py` — `WhatIfService(repo)`:

  ```python
  class WhatIfAssumption(BaseModel):
      kind: str          # issue_status | event_schedule_signal
      target_id: str     # 실재 검증 — 없으면 404급 오류
      value: str         # kind별 값 도메인 검증 (VALUE_LABELS 등재 값)
      note: str | None   # 사용자가 붙이는 가정 사유
  ```

  - overlay: 현재 repo의 컬렉션 목록을 얕은 복사, 대상 객체만
    `model_copy(update=...)`로 치환한 `InMemoryRepository` 구성 — **저장소 무변경**.
  - `run(assumptions)`: baseline `RiskService(repo).heatmap()` vs
    overlay `RiskService(overlay).heatmap()` diff →
    `WhatIfResult { assumptions(에코+assumption 명시+confidence=medium),
    changed_rows(시나리오별 baseline→projected 등급 + 달라진 셀과 그 근거),
    unchanged_scenario_count, note_ko("가정 기반 재계산 — 실데이터 아님") }`.
  - 등급 산정은 전부 기존 RiskService 룰 재사용 — what-if 전용 판정 룰을
    만들지 않는다 (룰이 하나면 가정 실험과 실제 지도가 절대 어긋나지 않는다).
- API: `POST /api/v1/what-if` (읽기 전용 계산 — advisory POST와 같은 지위,
  `test_no_write_endpoints` 허용 목록에 등재). 검증 실패는 400/404.
- UI: 이슈 상세(RCA)에 "가정: 이 이슈가 해결되면" 버튼 —
  `issue_status=resolved` 가정 1건으로 what-if 실행, 위험 등급 변화 패널 표시
  (변화 없음도 명시적으로 표시).

### 수용 기준

1. open 이슈를 resolved로 가정하면 해당 시나리오×IP 셀 등급이 실제로 그 이슈
   근거가 빠진 값으로 재계산된다 (반대 방향도 동일).
2. 존재하지 않는 target/미등재 값은 400/404 — 저장소는 어떤 경우에도 불변.
3. 응답의 모든 가정에 assumption 표시 + confidence medium 이하.
4. 동일 입력 동일 출력 (결정론).

## 6. 전 패키지 공통 검증

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
uv run python -m backend.cli.main validate-data
cd frontend && npm run build && npm run test && npm run lint
```

API 변경 시 `uv run python -m backend.api.openapi_export` + `npm run gen:api`.
PG 게이트 테스트는 `POSTGRES_TEST_DSN`(soc_test) — 운영 DB 오염 금지.

## 7. 구현 상태

- **P1~P4 전부 구현 완료 (2026-07-15)** — 수용 기준 전 항목 테스트 검증:
  P1 `eed9c2e` / P2 `9af20d9` / P3 `12902b6` / P4 `383c1f8`. 상세: CHANGELOG.
- 세부 편차: 없음 (설계 §2~§5 그대로). 부수 교정 1건 — PG 패리티 테스트의
  고정 id가 append-only 로그 누적으로 재실행 시 실패 → 실행별 고유 id.
- 운영 DB: 스키마 변경 없음(ontology_objects 범용) — `db-seed` 재실행으로
  kpi_observations 10건 반영 (시드 멱등 확인: 신규분만 버전 기록).
- 검증: backend 260 / PG soc_test 16 / frontend 34 / ruff / mypy /
  validate-data 오류 0 / openapi+gen:api 재생성.
