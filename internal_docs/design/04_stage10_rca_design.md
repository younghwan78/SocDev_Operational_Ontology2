# Stage 10 설계 노트 — 이슈 분석 (RCA 체인) + Test 온톨로지 확장

> 상위 기준: `03_course_correction.md` §4.3. 이 노트는 구현 계약을 확정한다 (변경 규율 1단계).
> 작성: 2026-07-05.

## 1. 온톨로지 확장 (event 모듈)

### 1.1 RootCauseType enum (6종 — 원점 문서 분류 승계)

```text
architecture_miss / spec_ambiguity / verification_gap /
power_model_error / sw_workaround_dependency / customer_scenario_mismatch
```

### 1.2 RootCause (구조화 원인 — Issue 내장)

| 필드 | 형 | 비고 |
|---|---|---|
| cause_type | RootCauseType | 필수 |
| description | str | 필수 — 원인 서술 |
| confidence | Confidence | 필수 — 원인 판정 확신도 |
| evidence_refs | list[str] | 근거 참조 (없으면 '근거 없는 원인'으로 화면에서 빨강) |

### 1.3 Test (신규 저장 객체 — 컬렉션 `tests`)

| 필드 | 형 | 비고 |
|---|---|---|
| id / source | OntologyObject 공통 | |
| title | str | |
| test_type | str | regression / scenario / cts_vts / power |
| result | str | passed / failed / blocked / planned |
| project_id | str | hard 참조 |
| linked_scenario_ids | list[str] | hard 참조 |
| verifies_issue_ids | list[str] | hard 참조 — 이 테스트가 검증하는 이슈 |
| linked_evidence_ids | list[str] | soft 참조 (evidence union) |
| executed_week | int \| None | |
| summary | str | 무엇을 어떻게 검증하는지 |

### 1.4 Issue 확장 (기존 필드 유지 + optional 추가 — 56 유래 이슈 4건은 무변경 통과)

| 필드 | 형 | 비고 |
|---|---|---|
| root_causes | list[RootCause] | 구조화 원인 (기존 root_cause_candidates는 문자열 후보로 유지) |
| fix_type | str \| None | hw_fix / sw_fix / tuning / spec_change / process_change / none |
| fix_description | str \| None | 조치 내용 |
| workaround | str \| None | 임시 우회 (SW workaround 의존 리스크의 근원) |
| verifying_test_ids | list[str] | tests 참조 — **비어 있으면 RCA 화면에서 빨강** |
| residual_risk | str \| None | 잔존 리스크 서술 |
| reusable_lesson | str \| None | 차기 과제 재사용 교훈 |
| resolved_week | int \| None | 종결 주차 (타임라인용) |

## 2. Fixture 전략 — 56 유래와 58 전용의 분리

- `fixtures/<module>.yaml`은 **변환기 생성물 유지** (직접 편집 금지 헤더 준수).
- 신규: 로더가 모듈별 **`<module>_58.yaml` 오버레이**(선택)를 같은 컬렉션 키로 병합 적재.
  58 전용 synthetic 데이터(이슈/테스트)는 `fixtures/event_58.yaml`에 산다.
  - id 충돌은 로더가 오류로 거부.
  - source.ref 규약: 58 전용은 `58:fixtures/event_58.yaml#<id>`.
- 라운드트립 테스트는 `*_58.yaml`을 제외한 파일만 변환 결과와 비교하도록 조정.
- **56 드리프트 재동기화 (이번 Stage에 포함)**: `Variant.source_basis: list[str]` 추가 후
  변환기 재실행 → 56의 2026-07-05 갱신(variants 6건, scenarios/relations/measurement_requirements)
  반영. diff 검토 후 채택.

### 2.1 이슈/테스트 구성 (원점 §7 archetype 기반, 계열별 6~7건 = 총 32건)

| 계열 | archetype 예 | 구성 원칙 |
|---|---|---|
| ISP | CSID/IFE BW 증가, HDR multi-frame latency, M2M DDR traffic, low-light power, HAL buffer mismatch, tuning IQ regression | 각 계열에 다음 상태를 섞는다: ① RCA 완결 체인(원인+조치+**passed 테스트**+교훈), ② **close됐지만 검증 테스트 없음**(수용 기준 사례), ③ 테스트는 있으나 failed/planned(미검증=노랑), ④ open(원인 후보만), ⑤ workaround 의존(잔존 리스크 명시) |
| DPU | preview+UI underrun, UHD playback layer BW, high refresh power, external display path, QoS frame drop | 〃 |
| Codec | 4K60 encode power spike, 8K30 bitrate/latency 위반, HDR decode BW, thermal 후 frame drop, FW scheduling latency | 〃 |
| Audio | A/V sync drift, call latency, low-power path 전환 실패, BT sync, thermal underrun | 〃 |
| DDR·NoC | 동시 동작 peak BW 초과, QoS priority 부족, compression 미적용, concurrent latency spike, resume latency | 〃 |

테스트 30건: regression/scenario/cts_vts/power 유형 분포, passed/failed/planned 결과 분포,
이슈 검증 연결(verifies_issue_ids)과 미연결 회귀 테스트 혼재.
프로젝트 분포: U(양산 회귀) 중심 + V/W(선행 검증).
기존 시나리오/IP/근거 ID만 참조한다 (무결성 오류 0 유지).

## 3. RCA 파생 뷰 (`backend/services/rca.py`)

```text
RCAChain
├─ issue 요약 (id/title/type/status/project/confidence)
├─ nodes: 고정 7단 세로 흐름 — 각 노드에 badge
│   1 증상(symptom)            badge: evidence_refs 있음→green, 없음→red
│   2 영향(scenarios/IPs/KPIs) badge: 범위 기록 있음→green, 없음→red
│   3 원인(root_causes)        badge: 구조화 원인+근거→green / 후보 문자열만·근거 없음→yellow / 없음→red
│   4 조치(fix/workaround)     badge: fix 기록→green / workaround만→yellow / 둘 다 없고 open→yellow, closed→red
│   5 검증 테스트              badge: 전부 passed→green / 일부 failed·planned→yellow / **없음→red (핵심)**
│   6 잔존 리스크              badge: 기록→green / 없음: closed→yellow, 그 외→red 아님(yellow)
│   7 재사용 교훈              badge: 기록→green / 없음→yellow
└─ verification_alert: closed인데 검증 테스트 없음 → 최상단 경고 플래그
```

노드 공통 필드: `step / step_ko / badge(green|red|yellow) / badge_reason_ko / items[](제목·설명·ref·source_refs)`.
이슈 목록 뷰(`IssueSummary`): 검증 상태 뱃지(verified/unverified/no_tests)와 필터 지원.
전부 결정론 — LLM 불개입, 모든 노드 항목에 원본 ref.

## 4. API / 화면

- `GET /api/v1/issues` — IssueSummary 목록 (project_id/verification 필터).
- `GET /api/v1/issues/{id}/rca` — RCAChain. 404 처리.
- Frontend `/issues` (내비 '이슈 분석' 활성화):
  좌측 이슈 리스트(필터 + 검증 상태 뱃지) → 우측 세로 RCA 흐름.
  "close됐지만 검증 테스트 없음" 이슈는 리스트와 체인 양쪽에서 빨간 강조.
- 기존 UI 공통 원칙 준수 (ID hover, 색 의미, 접기).

## 5. 수용 기준 대응

| 수용 기준 | 이 설계에서의 담보 |
|---|---|
| 검증 테스트 없는 close 이슈가 드러남 | verification_alert + 노드5 red badge + 리스트 뱃지, fixture에 해당 사례 포함 |
| RCA 완결 체인 1건 이상 | 계열마다 완결 체인 1건 이상 (총 5건+) |
| 변경 규율 6단계 | 이 노트(1) → 모델(2) → schema(3) → fixture(4) → 테스트(5) → changelog(6) |
| validate-data 오류 0 | 오버레이 로더 + 무결성 검사 확장(tests 참조) 후 검증 |
