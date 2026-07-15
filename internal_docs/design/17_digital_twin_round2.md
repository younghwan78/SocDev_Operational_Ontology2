# 17. Digital Twin 후속 2라운드 — 프로세스 전이 모델·what-if 확장·as-of 확대·KPI 차트

> 2026-07-15 착수 (사용자 승인: "다음 단계 진행"). 설계 16의 4패키지 완료 후
> `CURRENT_TASK.md`에 정리한 잔여 갭 4건. 설계 16 §0의 공통 원칙(전부 결정론 /
> 쓰기 경로 신설 없음 / 수치 점수 금지 / 가정은 assumption+confidence≤medium /
> 한국어 1급 / 시간축 분리)을 그대로 승계한다.

## 1. 패키지 구성과 구현 순서

| # | 패키지 | 내용 | 커밋 단위 |
|---|---|---|---|
| Q1 | 프로세스 전이 모델 | 이슈 상태의 단계 정의 + 전이 적합성 판정 (건너뜀/역행) | 1 |
| Q2 | what-if 가정 확장 | 신규 이슈 주입 + 목표 주차 시프트 + 이슈 신호 delta | 1 |
| Q3 | as-of 파생 뷰 확대 | 포트폴리오/변경 영향 as-of 표면 | 1 |
| Q4 | KPI 시계열 차트 | 라이브러리 없는 inline SVG 라인 차트 | 1 |

## 2. Q1 — 프로세스 전이 모델 (단계 전이 정의)

### 문제

P1이 재개(closed→open)는 잡지만, "분석·해결 기록 없이 곧장 종결" 같은 **단계
건너뜀**은 프로세스 모델이 없어 판정할 수 없다. 원점 문서의 프로세스 신호
아이디어를 성립시키려면 이슈 상태의 정상 진행 순서가 명시적 계약이어야 한다.

### 단계 정의 (계약 — `backend/services/process_model.py`)

`issue_status` 값 도메인(glossary) 전체를 단계로 사상한다:

| 단계(rank) | 단계 라벨 | 포함 상태 |
|---|---|---|
| 0 | 접수 | open, synthetic_open |
| 1 | 분석 | under_analysis |
| 2 | 우회 | workaround_applied |
| 3 | 해결 | resolved |
| 4 | 종결 | closed, done |

### 전이 판정 (결정론 — 전이 이력 위에서)

| 조건 | kind | 서술 예 |
|---|---|---|
| rank +1 또는 동일 단계 내 이동 | `normal` | (표시 안 함) |
| rank 2단계 이상 전진 | `skipped` | "접수→종결 — 분석/해결 단계 기록 없음" |
| rank 후퇴 | `backward` | "해결→분석 — 역행 (재개·재분석)" |
| 미등재 상태 값 | `unknown_status` | "프로세스 모델 밖의 상태 '...'" |

- created 첫 전이(from=None)는 어느 단계로 시작해도 정상 — 도입 시점이 다를 뿐이다.
- `backward` 중 종결셋→비종결셋은 P1의 재개와 동일 사실 — 중복 경고하지 않고
  P1 재개 문구를 우선한다 (판정 자체는 남긴다).
- 판정은 사실 서술 + 전이 ref(version, recorded_at) — 점수·차단 없음.

### 표면

- `RCAChain.transition_findings: list[TransitionFinding]`
  (`version/from_status/to_status/kind/kind_ko/note_ko`) — normal은 포함하지 않는다
  (변화가 아닌 것은 잡음). 계산은 P1과 같은 버전 소스 재사용.
- UI: 이슈 상세 "상태 전이 타임라인"의 해당 전이 항목에 판정 배지 병기
  (version 번호로 매칭 — 저장 계약 무변경, T2 응답도 무변경).

### 수용 기준

1. open→closed 직행 이력이 `skipped`로, resolved→under_analysis가 `backward`로
   판정되고 각각 단계 근거 문구를 갖는다.
2. 정상 진행(open→under_analysis→resolved→closed)은 findings가 비어 있다.
3. 미등재 상태 값은 `unknown_status`로 드러난다 (침묵 금지).
4. 버전 이력 없는 이슈는 findings 없음 — 기존 응답과 하위 호환.

## 3. Q2 — what-if 가정 확장 (신규 이슈 주입·주차 시프트·이슈 신호 delta)

### 확장 계약 (`WhatIfAssumption` — 기존 2종에 2종 추가)

| kind | 필수 필드 | overlay 효과 | delta 표면 |
|---|---|---|---|
| `issue_status` (기존) | target_id, value | 이슈 상태 치환 | 지도 + 이슈 신호 |
| `event_schedule_signal` (기존) | target_id, value | 이벤트 신호 치환 | 지도 |
| `new_issue` (신규) | target_id(**미존재 id**), scenario_ids, ip_ids | 가정 이슈 객체 주입 | 지도 + 이슈 신호 |
| `issue_week_shift` (신규) | target_id, week_delta | `due_week`를 delta만큼 이동 | 이슈 신호 |

- `WhatIfAssumption` 확장: `value: str | None`(kind별 필수성 검증),
  `week_delta: int | None`, `scenario_ids/ip_ids: list[str]`,
  `severity: str | None`, `title: str | None`.
- `new_issue` 검증: target_id가 **존재하면 400** (실데이터와 충돌 금지),
  scenario_ids/ip_ids는 실재해야 하며 각 1건 이상(효과 없는 가정 방지),
  severity는 값 도메인 검증. 주입 객체는 `confidence=low`,
  `symptom=note 또는 '가정 이슈'`, `source.origin=synthetic`,
  `source.ref="whatif:<target_id>"` — **ephemeral overlay에만 존재**.
- `issue_week_shift`: due_week가 없는 이슈에 적용하면 400 (시프트할 사실이 없다).

### 이슈 신호 delta (신규 응답 섹션)

`WhatIfResult.changed_issue_signals: list[IssueSignalChange]` —
baseline/overlay 각각 `RCAService(repo_x).list_issues()`(버전 소스 없이 — 주차
기반 신호만, 전이 이력은 가정과 무관하게 동일하므로 비교 대상이 아니다)를 돌려
`stale/overdue/verification/status` 변화와 신규 등장(가정 이슈)을 나열한다.
기존 지도 delta(`changed_rows`)는 그대로 — 두 delta는 항상 함께 계산된다.

### 수용 기준

1. `new_issue` 주입 시 해당 시나리오×IP 셀 등급이 open_issue 룰로 재계산되고,
   저장소에는 그 이슈가 존재하지 않는다.
2. 기존 id로 `new_issue` → 400. 미존재 시나리오/IP ref → 400.
3. `issue_week_shift`로 due_week가 기준 주차를 넘으면 overdue 신호가 delta에
   나타난다 (반대 방향도 동일).
4. 가정 에코·confidence 상한·결정론·저장소 불변 — 설계 16 §5 기준 유지.

## 4. Q3 — as-of 파생 뷰 확대 (포트폴리오·변경 영향)

- `GET /api/v1/as-of/portfolio/overview?ts=` →
  `AsOfPortfolioOverview { meta: AsOfMeta, overview: PortfolioOverview }`
- `GET /api/v1/as-of/change-impact?ts=&ip_id=&knob_id=&capability_id=&mode=` →
  `AsOfChangeImpact { meta: AsOfMeta, result: ChangeImpactResult }`
- 둘 다 `AsOfService.snapshot(ts)` 재사용 + 기존 서비스로 재계산 — 판정 룰
  신설 없음. 오류 계약은 기존 표면과 동일(400 ts / 404 IP / 400 knob).
- UI: **포트폴리오에만** 시점 재구성 컨트롤 추가 (위험 지도와 동일 패턴 —
  URL `asof` + 배너). 변경 영향은 폼 파라미터가 많아 API 표면만 제공하고
  UI 노출은 보류한다 (범위 결정 — 필요 시 별도 승인).

수용 기준: (1) 빈 로그에서 as-of 뷰 == 현재 뷰, (2) 반입→갱신 시나리오에서
과거 ts의 포트폴리오 집계가 옛 상태를 반영, (3) `test_no_write_endpoints` 불변.

## 5. Q4 — KPI 시계열 차트 (라이브러리 없는 inline SVG)

- 시나리오 상세 KPI 시계열 카드에 주차(x)×값(y) 라인 차트 — 프로젝트별 시리즈,
  점=관측(hover에 값·측정 단계·관측 id), 표는 유지(차트 아래 — 표가 계약,
  차트는 보조 시각화).
- **차트 라이브러리 도입 금지** — 순수 SVG + 기존 CSS 변수(테마 대응).
  dataviz 가이드라인 준수(작성 전 스킬 로드), 색은 테마 변수 기반으로
  라이트/다크 모두 가독.
- 축은 실제 주차/값 범위에서 결정론 계산 (nice-tick 근사, 데이터 없으면 미표시).
- 접근성: `role="img"` + 한국어 `aria-label` (시리즈·구간 요약).

수용 기준: (1) U/V 두 시리즈가 한 차트에 구분 표시, (2) 다크 모드 가독,
(3) frontend build·test·lint green (차트는 표와 같은 데이터 소스 — 계약 무변경).

## 6. 공통 검증

설계 16 §6과 동일 (전체 회귀 + API 변경 시 openapi/gen:api + PG는 soc_test).

## 7. 구현 상태

- 착수 2026-07-15. 패키지별 커밋, changelog는 마감 커밋에서 일괄 갱신.
