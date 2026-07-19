# 설계 22 — Digital Twin 레퍼런스 정렬 (W1~W4)

> 출처: `internal_docs/SoC_dev_process_digital_twin_reference.html`
> (Palantir Ontology + DTO/OCEL/OCPM2 딥리서치, 2026-07-19 분석) 채택 후보 중
> 우선 권고 4건(②③①⑦)의 구현 설계. 후속 후보(④⑤⑥)와 채택 금지 항목은 §6.
> 상태: **설계 확정 대기 — 구현 착수는 사용자 승인 후** (scope lock 규율).

## 0. 배경과 판정 요약

레퍼런스 문서의 주장 중 58에 이미 있는 것(시간 모델 T1~T3, 프로세스 신호,
what-if, HITL quarantine, 리뷰 팩=게이트 증거 번들)은 제외하고, 없는 것 중
58 규율과 충돌하지 않는 것만 채택한다.

| 후보 | 판정 | 근거 |
|---|---|---|
| ② 결정 데이터-시점 스탬프 + 리플레이 | **W1 채택** | 설계 15~20 시간 모델의 자연스러운 회수처 — 거의 배선만 필요 |
| ③ 링크 커버리지 상설 지표 | **W2 채택** | 트윈 충실도 메타 KPI. handover 파일럿 판정(연결률 ≥70%)의 측정 기반 |
| ① OCEL 2.0 export | **W3 채택** | 파생 뷰 순수 직렬화 — 계약 무변경, 표준 정박 + 사내 설득 자료 |
| ⑦ 문서·전략 반영 | **W4 채택** | 코드 아님 — 포지셔닝·기록 규율·성공 판정 기준 |
| ④ 게이트 조건 형식화 | 후속 (설계 23 후보) | 도메인 모델 변경 — §6.2 변경 규율 체인 필요, 설계 선행 |
| ⑤ JIRA writeback 코멘트 | 후속 (Stage 19 결합) | 실계정 커넥터·보안 승인 필요 |
| ⑥ link-recovery 제안 에이전트 | 후속 (Stage 18 결합) | 임베딩 인프라 필요. quarantine 관문 재사용 |
| 수치 예측 모델 | **채택 금지** | CLAUDE.md §6.3 수치 스코어링 금지와 충돌 |
| Person 단위 추적 | **채택 금지** | 역할(7종) 수준 유지 — actor 최소 기록(R4)으로 충분 |
| SpecRequirement 신설 | 보류 | CustomerRequest·ScenarioIPRequirement 정리 선행 필요 |

## 1. 범위

- **In**: W1 결정 워터마크+리플레이 링크 / W2 링크 커버리지 상설 지표(+배치 추이) /
  W3 OCEL 2.0 JSON export CLI / W4 문서 4건 갱신.
- **Out**: `decided_at` 같은 domain-time 신규 필드(§2 원칙), OCEL SQLite 변형·PM4Py
  의존성, 게이트 판정 로직(④), writeback(⑤), LLM 링크 제안(⑥), 새 화면 추가
  (4화면 상한 유지 — 전부 기존 화면 내 확장).
- 전부 additive — DB 마이그레이션 없음 (payload jsonb 복원 패턴).

---

## 2. W1 — 결정 데이터-시점 워터마크 + "당시 상태 보기"

### 2.1 원칙: transaction time 축 유지

레퍼런스는 "모든 결정은 어떤 데이터 버전 위에서 내려졌는지 기록"을 요구한다.
58의 as-of 재생은 **recorded_at(transaction time) 축**이므로(설계 15 §3),
결정의 워터마크도 같은 축으로 잡는다: **"twin이 이 결정을 알게 된 시각" =
결정 객체의 첫 버전 `recorded_at`**. `decided_at`(domain time) 필드 신설은
하지 않는다 — 축 혼합 금지, 그리고 반입 CSV에 없는 값을 강요하지 않는다.

### 2.2 계약 (파생 뷰 — 저장하지 않음)

```python
class DecisionWatermark(BaseModel):
    decision_id: str
    project_id: str
    recorded_at: str | None       # ISO — 리플레이 진입점
    batch_id: str | None          # 계보 (버전 로그 유래일 때)
    source: str                   # version_log | ingested_at | precapture
    note_ko: str                  # 정직성 문구
```

해석 우선순위 (결정론 서비스 `DecisionWatermarkService`):

1. 버전 로그에 `decisions` 첫 버전 존재 → 그 `recorded_at` + `batch_id`
   (`source="version_log"`).
2. 없고 `source.ingested_at` 존재 → 그 시각 (`source="ingested_at"`).
3. 둘 다 없음(synthetic 시드) → `recorded_at=None`, `source="precapture"`,
   note_ko="캡처 이전 결정 — 버전 로그가 없어 당시 상태를 재생할 수 없다".

### 2.3 API

`GET /api/v1/decisions/watermarks?project=<id>` → `list[DecisionWatermark]`
(읽기 전용·결정론·프로젝트 필터 optional). 기존 `GET /decisions`는 무변경 —
프론트가 id로 조인한다.

### 2.4 UX — 리뷰 센터 결정 행 (ReviewPage `PackDecisions`)

결정 행 head에 추가:

```text
[선택] DVFS 옵션 B 채택        데이터 시점 2026-07-14 09:12 ⓘ
  근거: … (기존)
  [🕐 당시 위험 지도]  [⇄ 당시↔현재 비교]
```

- **시점 칩**: `formatDateTime(recorded_at)`, title에 `batch_id`+source 설명.
- **[당시 위험 지도]** → `/?project=<pid>&asof=<recorded_at>` — 기존 as-of
  재구성 뷰가 그대로 열리고, 정직성 배너(재생/가정/근사 건수)가 이미 동반된다.
- **[당시↔현재 비교]** → `/?project=<pid>&asof=<recorded_at>&asofb=<now>` —
  Y2 두 시점 diff로 "결정 이후 무엇이 변했나"를 셀 변화 언어로 보인다.
- `source="precapture"`이면 링크 대신 배지 `캡처 이전 결정` (title=note_ko).
  거짓 리플레이 금지 — 링크를 비활성으로 두지 않고 아예 만들지 않는다.
- i18n: `ko.review.decision_watermark`, `decision_replay`, `decision_diff`,
  `decision_precapture` 신설. 하드코딩 영어 금지.

### 2.5 수용 기준

- 버전 로그 있는 결정 / ingested_at만 있는 결정 / synthetic 결정 3종의
  워터마크 판정 단위 테스트 (Memory + PG 게이트).
- API 응답 스키마 openapi 재생성 + 프론트 타입 자동 생성.
- 프론트 테스트: precapture 결정에 링크가 렌더되지 않음 / recorded_at 있는
  결정의 링크 href에 asof 파라미터 포함.

---

## 3. W2 — 링크 커버리지 상설 지표 (트윈 충실도)

### 3.1 정의 — 컬렉션별 명시 링크 필드 (계약 상수)

"linked" = 아래 필드 중 **1개 이상 비어있지 않음**. ingest `linkage_fields`
(J1 배치 연결률)와 같은 철학의 전역 상설판 — 판정 상수를 한 곳
(`backend/services/source_map.py`)에 두고 ingest와 문구를 일치시킨다.

| 컬렉션 | 링크 필드 |
|---|---|
| issues | `affected_scope.scenarios/ip_blocks/system_blocks`, `verifying_test_ids`, `evidence_refs` |
| development_events | `related_ip_ids`, `linked_scenario_ids`, `linked_evidence_ids`, `linked_milestone_ids` |
| tests | `linked_scenario_ids`, `verifies_issue_ids`, `linked_evidence_ids` |
| kpi_observations | `scenario_id`, `evidence_id` |
| evidence / measurement_evidence | `related_ip_ids` (+ 각 계약의 명시 링크 필드) |
| action_items | `source_decision_id` (필수 필드 — 항상 linked, 대조군 역할) |

`affected_domains` 같은 도메인 태그는 링크가 아니다 — 명시 ID 참조만 센다
(L8 원칙과 동일). 비율 표기는 데이터 충실도 집계이지 리스크 점수가 아니다
(§6.3 무관 — source_map.py 기존 각주와 같은 지위).

### 3.2 계약 (additive)

```python
class LinkFieldCoverage(BaseModel):
    field: str
    field_ko: str            # glossary 라벨
    linked: int              # 이 필드가 비어있지 않은 객체 수

class LinkCoverage(BaseModel):
    collection: str
    collection_ko: str
    total: int
    linked: int              # 정의 §3.1 충족 객체 수
    fields: list[LinkFieldCoverage]

class SourceCoverage(BaseModel):    # 기존 + additive
    collections: list[CollectionCoverage]
    totals: OriginTotals
    links: list[LinkCoverage] = []          # 신규
    link_note_ko: str = ""                  # "연결률은 위험 지도·변경 영향의 신뢰 한계" 설명
```

### 3.3 배치 추이 (연결률 시계열의 최소 구현)

`IngestBatch`에 additive 필드 `linkage_total: int = 0` /
`linkage_connected: int = 0` — J1 품질 리포트가 이미 계산하는 값을 배치
기록에 동반 저장한다 (payload jsonb 복원 — 마이그레이션 불필요, dry_run은
기록되지 않으므로 무관). 기존 배치(필드 없음)는 0/0 → 추이에서 "기록 없음"
으로 제외 표시.

### 3.4 UX — 출처 지도 새 카드 "온톨로지 연결률"

전체 요약 카드와 컬렉션별 카드 사이:

```text
┌ 온톨로지 연결률 (트윈 충실도) ──────────────────────────┐
│ 연결률은 위험 지도·변경 영향이 볼 수 있는 범위의 한계다. │
│ 파일럿 판정 기준: 핵심 컬렉션 연결률 ≥70% (handover §…) │
│                                    ┆70%                  │
│ 이슈           ██████████░░░░░░░░  ┆   42/98 (43%)   ▸  │
│ 개발 이벤트    ████████████████░░  ┆   88/96 (92%)   ▸  │
│ 검증 테스트    ██████████████░░░░  ┆   61/78 (78%)   ▸  │
│ KPI 관측       ████░░░░░░░░░░░░░░  ┆   10/52 (19%)   ▸  │
│ ▸ 펼침: 필드별 건수 칩 — 시나리오 42 · IP 31 · 테스트 12 │
│ 최근 배치 연결률: b_0712 64% → b_0715 71% → b_0718 69%  │
└──────────────────────────────────────────────────────────┘
```

- 막대에 70% 기준선 눈금 1개 — **판정·경고 색은 쓰지 않는다** (기준선 표시일
  뿐 등급이 아니다). 행 `<details>` 펼침에 필드별 칩.
- 배치 추이는 최근 10개 배치의 `linkage_connected/linkage_total` 텍스트 나열
  (스파크라인 도입은 과잉 — 기존 반입 이력 문법 재사용).
- 컬렉션 자체가 없으면(빈 저장소) 카드 숨김 — R1 온보딩과 충돌하지 않는다.
- i18n: `ko.source_map.link_*` 신설.

### 3.5 수용 기준

- 정의 §3.1 판정 단위 테스트 (필드별/복합/action_items 대조군).
- 기존 SourceCoverage 소비처 무파손 (additive 검증 — openapi 재생성).
- 배치 저장·복원 왕복 테스트 (Memory + PG): linkage 카운트 유지, 구 배치
  payload(필드 없음) 복원 시 0/0.
- 프론트: 연결률 카드 렌더 + 70% 기준선 존재 + 빈 저장소에서 미표시.

---

## 4. W3 — OCEL 2.0 export (읽기 전용 파생 뷰)

### 4.1 목적과 지위

내부 계약을 바꾸지 않고 버전 로그+상태 전이를 OCEL 2.0 JSON으로 직렬화한다.
(a) 표준 포맷 정박, (b) PM4Py/Celonis 등 외부 프로세스 마이닝 도구 호환,
(c) "우리 데이터는 표준 교환 포맷으로 나온다" 사내 설득 자료.
스냅샷 export/compare 회귀 도구 계열(이식 금지 대상)과 무관 — 이것은 교환
포맷 산출이지 회귀 스냅샷이 아니다.

### 4.2 매핑 (transaction time 축 — 정직성 원칙)

| OCEL 개념 | 58 원천 |
|---|---|
| objects | 온톨로지 객체 전 컬렉션 — `type=collection`, attributes=스칼라 필드만 |
| events | 버전 로그 행 — `type = {collection}_{change_kind}`; status 전이 동반 시 `{collection}_status_{to_status}`로 세분 |
| event time | `recorded_at` (**transaction time** — 메타에 명시) |
| E2O | 이벤트 → 대상 객체(qualifier `subject`) + payload 명시 링크 필드의 참조 객체(qualifier=필드명) |
| O2O | 현재 상태의 명시 링크 필드 (§3.1 상수 재사용) |

**domain time(week)은 timestamp로 변환하지 않는다** — 주차는 객체 attribute로
남긴다. 가짜 타임스탬프 제조 금지. 파일 메타(`ocel:global-log` 상당)에
"time axis = transaction time (recorded_at)" 명시.

### 4.3 CLI

```bash
uv run python -m backend.cli.main export-ocel --out out/soc_twin.ocel.json
```

- Typer 서브커맨드, 저장소·버전 로그 읽기만. `--collection` 필터 optional.
- SQLite 변형·PM4Py 검증은 Out (의존성 추가 금지) — 대신 OCEL 2.0 JSON 필수
  키(objects/events/type/time/relationships) 스키마 준수 자체 테스트.

### 4.4 수용 기준

- 고정 fixture 위 export 결과의 구조 테스트: 필수 키, 이벤트 수 = 버전 로그
  행 수, E2O subject 존재, O2O가 §3.1 필드에서만 유래.
- 결정론: 같은 저장소 상태 → 같은 출력 (정렬 고정).
- `docs/`가 아니라 `internal_docs/ops/handover.md`에 사용법 기록 (외부 도구
  연계는 운영자 작업 — 사용자 UI 가이드 아님).

---

## 5. W4 — 문서·전략 반영 (코드 아님)

1. **`internal_docs/ops/handover.md`** 파일럿 절 확장:
   - **기록 규율 캠페인** 문단 — "미기록 작업은 트윈에 없다, 지연 업데이트는
     duration을 전부 왜곡한다" (Thermo Fisher 교훈). JIRA 상태 전이 즉시성·
     이슈 링크 필드 기입을 파일럿 참여 팀 합의 사항으로 명시.
   - **P1 exit 지표**: 객체 매핑률 ≥90% (반입 대상 중 매핑 성공), 링크
     커버리지 베이스라인 기록 + 핵심 컬렉션 ≥70% 목표 (W2 카드가 측정 도구).
   - W3 OCEL export 사용법 한 절.
2. **`internal_docs/26.07.05 비지니스 가치 논의.md` 후속 절** — "제품 트윈/
   팹 트윈이 아니라 **개발 프로세스 트윈**" 3층 구분과 업계 공백 논거를
   한 절로 정리 (사내 보고용 한 줄 정의 포함). 레퍼런스의 '단일출처' 태그
   항목은 공식 인용 전 원문 확인 필요 표기 유지.
3. **`internal_docs/design/05_long_term_improvement_plan.md`** — Stage 13/17
   성공 판정 기준에 "게이트 리뷰에서 트윈 지표(연결률·결정 리플레이)가 공식
   인용됨" 추가.
4. **`docs/`** (사용자 가이드): source-map 가이드에 연결률 해석 한 절,
   review 가이드에 "당시 상태 보기" 사용법 한 절 (구현 완료 후 스크린샷 없이
   텍스트 먼저).

---

## 6. 후속 예고 (이번 범위 아님 — 착수 별도 승인)

- **④ 게이트 조건 형식화 (설계 23 후보)**: `ProjectMilestone.exit_criteria`
  (요구 근거 유형·미해결 blocker 이슈 상한 등 결정론 판정 가능한 기준) +
  리뷰 팩의 충족/미충족 판정. §6.2 변경 규율 체인(설계→모델→schema→fixture→
  테스트→changelog) 전부 필요 — 별도 설계 문서로.
- **⑤ JIRA writeback 코멘트 (Stage 19)**: 침습성 최저 단계(코멘트)만.
  RCA "검증 없는 종결" 발견 → HITL 승인 → 해당 JIRA 이슈 코멘트 발행.
  원칙 확인: 58의 "온톨로지 수정 API 금지"는 트윈 저장소 규칙이고 writeback은
  소스 시스템 출력 — 소스가 SoR로 남고 트윈은 재반입으로 따라간다.
- **⑥ link-recovery 제안 에이전트 (Stage 18)**: LLM이 누락 링크 제안 →
  quarantine 대기열 → 사람 승인 후 반입. W2 지표를 올리는 실행 수단.
- 채택 금지 재확인: 수치 예측 모델(§6.3 충돌), Person 단위 추적,
  SpecRequirement 신설(정리 선행).

## 7. 구현 순서와 검증

권장 순서: **W2 → W1 → W3 → W4** (W2가 계약 상수를 만들고 W3이 재사용;
W1은 독립; W4는 W1~W3 완료 후 문구 확정).

각 패키지 완료 시:

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
uv run python -m backend.cli.main validate-data
uv run python -m backend.api.openapi_export   # W1·W2 (계약 변경 시)
cd frontend && npm run gen:api && npm run build && npm run test && npm run lint
```

실서버(PG) smoke: 워터마크 3종 판정 / 연결률 카드 / export-ocel 파일 생성.
완료 후 CHANGELOG + CURRENT_TASK 마감, 다음 후보(④ 설계 23) 기록 후 정지.
