# 20. Digital Twin 3라운드 — 타 컬렉션 프로세스 모델·as-of 시점 비교·변경 영향 as-of UI

> 2026-07-17 착수 (사용자 승인: "남은 후보 구현 진행하고 commit해줘").
> CURRENT_TASK에 남아 있던 digital twin 후보 3건. 설계 16 §0 공통 원칙 승계.
> D4·Stage 13+는 사내 세션 일정/사내 표준 확정이 전제라 범위 외.

## 1. 패키지 구성

| # | 패키지 | 내용 | 커밋 단위 |
|---|---|---|---|
| Y1 | 타 컬렉션 프로세스 모델 | 레지스트리 일반화 + 액션/이벤트 모델 + history 표면 | 1 |
| Y2 | as-of 두 시점 diff | 위험 지도 시점 비교 API + UI 오버레이 | 1 |
| Y3 | 변경 영향 as-of UI | 기존 API 표면의 화면 노출 | 1 |

## 2. Y1 — 타 컬렉션 프로세스 모델

### 문제

전이 판정(건너뜀/역행/미등재)은 이슈에만 있다. 상태 전이가 기록되는 다른
컬렉션(액션 아이템, 개발 이벤트)도 같은 질문("프로세스답게 흘러왔는가")을
받을 수 있어야 한다. T2 전이 추출은 이미 컬렉션 불문 generic이다.

### 레지스트리 (계약 — `process_model.py`)

| 컬렉션 | 값 도메인 | 단계(rank) |
|---|---|---|
| issues | issue_status | 접수{open,synthetic_open} / 분석 / 우회 / 해결 / 종결{closed,done} (기존) |
| action_items | action_status | 미착수{open} / 진행{in_progress,blocked} / 종결{done,cancelled} |
| development_events | event_status | 접수{recorded,open} / 검토{in_review} / 처리{mitigated,deferred,available} |

- 판정 룰은 공통 (기존 이슈 룰 그대로): from=None 정상(단 모델 밖 상태는 미등재),
  rank+2↑ 건너뜀(건너뛴 단계 나열), 후퇴 역행(최종 단계발은 재개 병기 —
  이슈만 "프로세스 신호 참조" 문구 유지, 타 컬렉션은 "(재개)").
- `issue_transition_findings`는 하위 호환 wrapper로 유지 (RCA 무변경).
- blocked는 진행 단계 내 상태(차단은 단계가 아니라 상황), cancelled는 종결의
  한 형태 — 취소로의 직행도 "종결 직행"으로 드러나는 것이 맞다.

### 표면

- `GET /history/{collection}/{object_id}` 응답에 `transition_findings` 병기
  (모델 등재 컬렉션만 계산, 미등재 컬렉션은 빈 목록 — 판정 대상이 아니다).
  응답 모델은 `ObjectHistoryFindings`(기존 필드 + findings) — 저장 계약 무변경.
- CLI `history`에 판정 문구 출력 추가.
- 이슈 타임라인 UI는 기존 RCA 경로 그대로 (무변경).

### 수용 기준

1. action_items open→done 직행이 건너뜀으로, done→in_progress가 역행(재개)으로
   판정된다. development_events open→mitigated 직행도 건너뜀.
2. 모델 미등재 컬렉션(예: scenarios)은 findings 없이 기존 응답과 동일.
3. 이슈 RCA 표면·기존 테스트 무변경 (wrapper 하위 호환).

## 3. Y2 — as-of 두 시점 diff

### 문제

as-of는 "그 시점에 뭐라고 했는가"를 답하지만 "두 보고 시점 사이에 무엇이
바뀌었는가"는 사용자가 눈으로 비교해야 한다.

### 계약

- 비교 로직 공유: what-if의 heatmap 비교(행/셀 등급 변화)를
  `heatmap_diff.py`로 추출 — `WhatIfRowChange`/`WhatIfCellChange` 모델을
  그 모듈로 이동(이름 유지 — openapi 스키마 안정, what_if가 re-export).
  **룰이 하나면 "가정 비교"와 "시점 비교"가 같은 언어로 읽힌다.**
- `GET /as-of/risk/diff?ts_a=&ts_b=&project_id=` →
  `AsOfRiskDiff { meta_a, meta_b, changed_rows, unchanged_scenario_count, note_ko }`
  (ts_a=기준, ts_b=비교 — 각각 snapshot 재생 + RiskService 재계산).
- 오류 계약: ts 파싱 실패 400 (기존 as-of와 동일).

### UI (위험 지도)

- `asof`가 설정된 상태에서 **비교 시점** 입력(`asofb`) 추가 — 둘 다 있으면
  기본 지도는 ts_a(기존 as-of 뷰), diff의 변경 셀은 ts_b 등급을 점선 오버레이로
  (워크벤치 투영과 같은 시각 문법 — 점선 = "지금 실제가 아닌 값").
- 배너: 두 시점 + 변경 행 수. `whatif`와는 기존 규칙대로 상호 배타.

### 수용 기준

1. 데모 DB의 배치1 전/후 두 시점 diff에 uhd60_recording_kpi 행 변화가 나온다.
2. 같은 ts를 양쪽에 넣으면 changed_rows가 빈다 (동일 입력 동일 출력).
3. what-if 기존 응답 스키마·테스트 무변경 (모델 이동은 re-export).

## 4. Y3 — 변경 영향 as-of UI

- 변경 영향 화면 폼에 **시점 재구성** 입력(URL `asof`) — 있으면
  `GET /as-of/change-impact`로 전환, 정직성 배너 표시 (위험 지도와 동일 패턴,
  i18n 키 재사용). 없으면 기존 동작 그대로.
- 계약 신설 없음 (설계 17 §4에서 보류했던 UI 노출).

수용 기준: 시점 입력 시 배너+과거 상태 결과, 해제 시 현재 결과. 폼 파라미터
(ip/knob/capability/mode)와 시점이 모두 URL에 실려 공유 가능.

## 5. 검증

설계 16 §6과 동일: 전체 회귀 + openapi/gen:api + PG soc_test + 실서버 확인.

## 6. 구현 상태

- **Y1~Y3 구현 완료 (2026-07-17)** — 상세: CHANGELOG. 커밋 편차: app.py·
  test_api.py·client.ts가 패키지 간 공유라 백엔드(Y1+Y2)/프론트(Y2+Y3)/마감
  3커밋으로 정리.
- 검증: backend 282(+7: 프로세스 모델 4·diff 1·API 2) / PG soc_test 12 / ruff /
  mypy / validate-data 오류 0 / frontend build·34 tests·lint / 실서버 확인 —
  Y1 데모 이슈 history 판정 병기, Y2 데모 배치1 전/후 diff(중간→높음, 점선
  오버레이+비교 배너), Y3 변경 영향 시점 재구성(배너 + 과거 스냅샷 결과).
