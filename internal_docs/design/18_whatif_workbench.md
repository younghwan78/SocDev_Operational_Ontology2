# 18. what-if 워크벤치 — 위험 지도 가정 실험 모드

> 2026-07-17 착수 (사용자 승인: "좋아 진행해줘"). 배경: 사용자 관찰 —
> "UX적으로는 다양한 선택지를 미리 보여주고 실제 운영/결정에서의 scope을
> 넓혀주는 것도 의미가 있다". 설계 16 §0 공통 원칙(전부 결정론 / 쓰기 경로
> 신설 없음 / 수치 점수 금지 / 가정은 assumption+confidence≤medium / 한국어 1급)
> 을 그대로 승계한다.

## 1. 문제

what-if 엔진(`POST /what-if`)은 가정 4종·복합 10개·지도/신호 delta를 지원하지만,
UI 표면은 이슈 상세의 1클릭 버튼 2종뿐이다. 즉:

- **반응형만 가능** — 이미 열어본 이슈 하나에 대한 실험. 선택지를 펼쳐놓고
  조합하는 **탐색형** 사용은 API 직접 호출로만 가능하다.
- 실험 결과가 목록으로만 나온다 — 위험 지도라는 "공용 언어" 위에 겹쳐 보이지
  않는다.
- 가정 조합을 회의 전에 공유할 방법이 없다.

## 2. 원칙 (이 워크벤치가 지키는 것)

1. **후보는 제안이지 결정이 아니다** — 시스템은 "실험해볼 가치가 있는 질문"을
   기존 신호에서 결정론으로 도출해 근거와 함께 나열할 뿐, 아무것도 실행하거나
   우선순위를 매기지 않는다 (수치 점수 금지 유지).
2. **판정 룰 신설 없음** — 후보 도출은 이미 존재하는 신호(검증 없는 종결,
   미해결 고심각, due_week, 일정 신호)를 읽기만 한다. 실험 계산은 기존
   `POST /what-if` 그대로.
3. **저장 없음** — 가정 세트는 URL 직렬화로 공유·재사용한다. 저장 계약(가정
   세트 영속화)은 별도 설계로 남긴다.
4. **오버레이는 정직하게** — 투영 등급은 기준 등급과 항상 구분되는 표기 +
   "가정 N개 적용 중 — 실데이터 아님" 배너. 가정이 없으면 지도는 평소와 동일.

## 3. W1 — 가정 후보 제안 (백엔드)

### 계약

`GET /api/v1/what-if/candidates?project_id=` →
`WhatIfCandidateList { candidates: list[WhatIfCandidate], note_ko }`

```text
WhatIfCandidate:
  id            # "{rule}:{target_id}" — 결정론
  rule / rule_ko
  kind          # 그대로 POST /what-if에 넣을 수 있는 가정 좌표
  target_id / target_title / project_id
  value         # issue_status·event_schedule_signal 후보의 가정 값
  week_delta    # issue_week_shift 후보의 기본값(UI에서 조정 가능)
  label_ko      # "가정: 이 종결이 잘못이라면(다시 열리면)?"
  basis_note_ko # 왜 이 후보인가 — 발화한 신호의 사실 서술
```

### 도출 룰 (전부 기존 신호 읽기, 신설 없음)

| rule | 소스 신호 | 제안 가정 |
|---|---|---|
| `unverified_close` | 이슈 `closed_without_verification` (RCA 요약) | `issue_status` → `open` — "이 종결이 잘못이라면?" |
| `open_high_resolve` | 미종결 이슈 & severity `high` | `issue_status` → `resolved` — "해결되면 얼마나 풀리나?" |
| `due_week_shift` | 미종결 이슈 & `due_week` 존재 | `issue_week_shift` 기본 `week_delta=-2` — "일정이 당겨지면?" |
| `event_at_risk` | 이벤트 `schedule_signal ∈ {at_risk, window_closing}` | `event_schedule_signal` → `on_track` — "정상 진행되면?" |

- 정렬: 룰 순서(위 표) → target_id — 결정론, 우선순위 점수 아님.
- `project_id` 필터: 이슈/이벤트의 project_id 일치分만.
- 한 이슈가 여러 룰에 걸리면 각각 후보가 된다 (룰이 곧 질문이므로 중복 아님).

### 수용 기준

1. 검증 없는 종결 이슈가 `unverified_close` 후보로, at_risk 이벤트가
   `event_at_risk` 후보로 나온다 — 각각 근거 문구 포함.
2. 후보의 (kind, target_id, value/week_delta)를 그대로 `POST /what-if`에 넣으면
   400 없이 계산된다 (후보=실행 가능한 가정).
3. project_id 필터가 동작한다. 같은 데이터에서 항상 같은 순서.
4. `test_no_write_endpoints` 불변 (GET 전용).

## 4. W2 — 위험 지도 가정 실험 모드 (프론트)

### 상태 모델 (URL=상태)

- URL `whatif` 파라미터 = 가정 배열의 JSON 직렬화(URI 인코딩). 링크 공유가 곧
  가정 세트 공유. 파싱 실패 시 무시(빈 세트)하고 파라미터 제거.
- 가정이 1개 이상이면: `POST /what-if` 결과를 조회해 오버레이 + 배너 표시.
- 패널 열림/닫힘은 로컬 상태 (공유 대상 아님).

### 화면 구성

1. **툴바**: "가정 실험" 칩(토글). 가정 적용 중이면 active 표시.
2. **워크벤치 패널** (지도 위 카드):
   - 적용 중 가정 칩 목록 — 개별 ✕ 제거, "모두 해제", 10개 상한 표시.
   - **후보 목록** (`GET /what-if/candidates?project_id=`) — 룰 배지 + 라벨 +
     근거 문구 + [추가] 버튼. week-shift 후보는 delta 숫자 입력(기본 −2).
   - **신규 이슈 주입 폼** (컴팩트): 제목 / 시나리오 다중 선택(현재 지도 행) /
     IP 다중 선택(현재 지도 열) / 심각도 — 지도에 이미 있는 목록을 재사용하므로
     별도 조회 없음. target_id는 `whatif_` 접두 + 자동 생성.
   - **결과 요약**: 변경 행 수 / 변화 없는 시나리오 수 / 이슈 신호 델타 목록
     (이슈 상세 WhatIfCard와 동일 서식).
3. **지도 오버레이**: 변경된 셀·종합은 투영 등급 심볼로 표시하되 구분 표기
   (점선 링) + title "기준 X → 투영 Y (가정)". 미변경 셀은 평소와 동일.
4. **배너**: 가정 적용 중 상시 — "⚗ 가정 N개 적용 중 — 실데이터가 아니며
   저장되지 않습니다".

### as-of와의 상호작용

시점 재구성(asof)과 가정 실험(whatif)의 동시 적용은 **막는다** — 의미가 겹치면
("과거 상태에 가정을 얹으면") 해석 부담이 커진다. whatif 활성화 시 asof 파라미터
제거, asof 입력 시 whatif 제거. 각 모드 배너에 명시.

### 수용 기준

1. 후보 [추가] → 지도 셀이 투영 표기로 바뀌고 배너가 뜬다. 제거하면 원복.
2. URL 복사 → 새 탭에서 같은 가정 세트와 오버레이가 재현된다.
3. new_issue 폼으로 낮은 등급 셀이 투영 높음으로 표시된다.
4. 이슈 신호 델타(지연/정체/검증/상태)가 패널에 나온다.
5. asof와 상호 배타. frontend build·test·lint·한국어 게이트 green.

## 5. 검증

설계 16 §6과 동일: 전체 회귀 + openapi/gen:api 재생성 + 실서버(8155/5275) 확인.

## 6. 구현 상태

- **W1·W2 구현 완료 (2026-07-17)** — 상세: CHANGELOG.
- 검증: backend 273(신규 후보 3 + API 1) / ruff / mypy / validate-data 오류 0 /
  frontend build·34 tests·lint / 실서버(8155/5275) 확인 — 후보 추가→셀 점선
  투영·배너·이슈 신호 델타, 신규 이슈 주입 폼(FHD120×ISP 낮음→높음),
  URL `whatif` 직렬화(2가정 조합) 재현.
- 계약 편차 없음. 가정 세트 영속화는 계획대로 범위 외(URL 직렬화로 해소).
