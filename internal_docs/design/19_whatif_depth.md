# 19. what-if 워크벤치 심화 — 화면 연결·가정 세트 영속화

> 2026-07-17 착수 (사용자 승인: "다음 후보 계속 진행해줘"). 설계 18에서 남긴
> 후속 3건. 설계 16 §0 공통 원칙 승계 (결정론 / 수치 점수 금지 / 가정은
> assumption+confidence≤medium / 한국어 1급).

## 1. 패키지 구성

| # | 패키지 | 내용 | 커밋 단위 |
|---|---|---|---|
| X1 | 이슈 상세 → 워크벤치 | WhatIfCard "지도에서 실험" 링크 (URL 직렬화 재사용) | 1 |
| X2 | 가정 세트 영속화 | `whatif_sets` 저장 계약 + API + 저장/불러오기 UI | 1 |
| X3 | 변경 영향 → 워크벤치 | 영향 결과 → new_issue 가정 브리지 링크 | 1 |

## 2. X1 — 이슈 상세 → 워크벤치 연결

이슈 상세의 1클릭 실험(WhatIfCard)은 목록 델타만 보여준다. 같은 가정을 지도
언어로 보고 싶으면 워크벤치로 넘어갈 수 있어야 한다.

- WhatIfCard에 **"지도에서 실험"** 링크 추가: 1클릭과 동일한 가정 1건을
  `/?project=<이슈의 project_id>&whatif=<JSON>`으로 직렬화해 위험 지도로 이동.
- 실행 결과가 있어야 보이는 게 아니라 **버튼 옆에 상시** — 실험 전에 바로
  지도로 가는 경로도 유효하다.
- 신규 계약 없음 (URL=상태 재사용).

수용 기준: 링크 클릭 → 위험 지도가 해당 가정 적용 상태로 열린다 (배너+오버레이).

## 3. X2 — 가정 세트 영속화 (저장 계약)

### 지위

`whatif_sets`는 **온톨로지 데이터가 아니라 운영 기록**이다 — ask_log(0005)·
agent_runs(0002)와 같은 지위. append-only: 수정/삭제 API를 만들지 않는다
(이름이 같은 세트를 다시 저장하면 새 기록 — 목록에서 최신이 위에 온다).
가정 자체는 여전히 실데이터가 아니며, 세트를 불러와도 적용은 URL 파라미터
경유(ephemeral)다.

### 계약

```text
WhatIfSet:
  id           # "wset_" + hex10 (서버 생성)
  name         # 사용자가 붙인 이름 (1자 이상)
  note         # 선택 — 가정 세트의 배경 설명
  project_id   # 선택 — 워크벤치의 프로젝트 컨텍스트
  assumptions  # list[WhatIfAssumption] 1..10 — 저장 전 overlay 검증 통과 필수
  created_at
```

- 마이그레이션 `0007_whatif_sets.sql`: id PK / name / project_id / created_at /
  payload jsonb (+ created 역순 인덱스). ask_log 패턴 그대로.
- Store: `WhatIfSetStoreProtocol` (save / list(project_id?) 최신순 / get(id)) —
  InMemory + Postgres 구현.
- API:
  - `POST /what-if/sets` {name, note?, project_id?, assumptions} → WhatIfSet.
    저장 전 `WhatIfService`의 overlay 조립으로 **검증만** 수행 (400/404 계약은
    POST /what-if와 동일) — 깨진 가정 세트는 저장되지 않는다.
  - `GET /what-if/sets?project_id=` → 최신순 목록.
  - `GET /what-if/sets/{set_id}` → 1건 (없으면 404).
- UI (워크벤치 패널): 가정 ≥1일 때 이름 입력+[세트로 저장]. 저장된 세트 목록
  (이름·가정 수·날짜) + [불러오기] = `whatif` URL 갱신(현재 바스켓 대체).

### 수용 기준

1. 저장→목록→불러오기 왕복이 메모리/PG 양쪽에서 동작 (PG는 DSN 게이트 테스트).
2. 깨진 가정(미존재 대상 등)은 저장이 거부된다 (400/404).
3. `test_no_write_endpoints` — 쓰기 예외 목록에 `/what-if/sets`만 추가.
4. 불러온 세트는 URL 직렬화로 적용 — 저장소(온톨로지)는 불변.

## 4. X3 — 변경 영향 → 워크벤치 브리지

변경 영향 화면은 "이 knob/IP를 바꾸면 어디에 영향이 가나"(전파 지도)를 답하지만,
그 영향이 **위험 지도 등급으로는 어떤 의미인지**는 보여주지 않는다.

- 변경 영향 결과 헤더에 **"가정으로 실험"** 링크: 결과를 new_issue 가정 1건으로
  직렬화 — 제목 = "가정: <IP/knob> 변경 영향" 계열, scenario_ids = 영향 시나리오,
  ip_ids = 대상 IP + 연쇄 IP, severity = medium (가정 기본값 — 과장 금지).
- 신규 계약 없음: 기존 new_issue 가정 + URL 직렬화 재사용. 판정 룰은 위험
  지도와 동일하므로 "전파 → 등급 번역"이 룰 신설 없이 성립한다.

수용 기준: 변경 영향 실행 → 링크 클릭 → 워크벤치에 가정이 적용된다.
등급이 바뀌는 셀이 있으면 투영 표기로, 이미 높음인 행뿐이면 "변화 없음" +
가정 이슈 등장 신호로 정직하게 표시된다 (변화 없음도 답이다).

## 5. 검증

설계 16 §6과 동일: 전체 회귀 + openapi/gen:api 재생성 + PG는 soc_test +
실서버(8155/5275) 확인.

## 6. 구현 상태

- **X1~X3 구현 완료 (2026-07-17)** — 상세: CHANGELOG. 커밋 편차: X1·X3는
  같은 브리지 성격(코드 소량, URL 직렬화 재사용)이라 커밋 1개로 합침 —
  X1+X3 / X2 / 마감 3커밋.
- 검증: backend 275(+2 API 세트 왕복·거부) / PG soc_test 12(+1 스토어 패리티) /
  ruff / mypy / frontend build·34 tests·lint / 실서버 확인 — X1 이슈 상세→지도
  (가정 적용·후보 "적용됨" 정합), X2 저장→목록→모두 해제→불러오기 왕복(PG),
  X3 변경 영향→지도(가정 주입 신규 등장 + "변화 없음도 답" 표시, sys_* 연쇄
  블록 ip_ids 허용 확인). 마이그레이션 0007은 soc_demo·soc_ontology 모두 적용.
