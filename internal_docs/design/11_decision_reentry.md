# 결정 재진입 (B3b) — 리뷰 팩 결정 CSV → Decision 설계

> 상태: v1.0 (2026-07-11)
> 실현: 백로그 `08_bridge_followups.md` §4 Phase 2. `10_review_pack.md` §2.2의 후속 —
> 원점 4층 루프(review → decision)의 마지막 고리를 **ingest 경로로** 닫는다.
> 선행: `10_review_pack.md`(리뷰 팩·결정 CSV), Phase 1 반입 표면(중첩 매핑 지원).

## 1. 문제 — 내보내기만 있고 재진입이 없다

리뷰 팩은 결정 컬럼이 빈 CSV를 내보낸다(사람이 회의에서 채움). 그러나 채운 CSV를
`Decision` 객체로 되돌리는 경로가 없어 "결정 ← 근거" 추적이 문서 밖에서 끊긴다.
쓰기 API 금지 원칙상 재진입은 **기존 ingest 계층(배치+rollback)** 로만 가능하다.

## 2. 계약 — 온톨로지 무변경, `decisions` 매핑 1종 추가

`Decision` 모델(decision.py)을 그대로 사용한다. 행 1개 = 결정 1개.

### 2.1 CSV 템플릿 v2 (프론트 `toDecisionCsv` 개정)

| 컬럼 | 채움 | 반입 매핑 |
|---|---|---|
| 결정 ID | 시스템 제안(`decision_<팩>_r<n>`), 사람 수정 가능 | `id` |
| 프로젝트 ID | 팩이 단일 프로젝트면 시스템, 아니면 사람 | `project_id` |
| 회의 이벤트 ID | **사람** — 리뷰 회의를 `development_events` 매핑으로 먼저 반입 | `event_id` |
| 시나리오 ID / 시나리오 / 항목종류 / 신뢰등급 | 시스템 (읽기용) | 미반입 |
| 진술 | 시스템 (검토 항목 서술) | `supporting_basis.statement` |
| 근거 | 시스템 (항목 basis ref) | `supporting_basis.ref_id` |
| 근거 유형 | 시스템 (basis ref_collection, 없으면 `review_item`) | `supporting_basis.basis_type` |
| 확신도 | 시스템 프리필 `medium`, 사람 조정 (low/medium/high) | `supporting_basis.confidence` |
| 결정 | **사람** | `selected_option` |
| 결정 유형 | 사람 (빈칸 → 기본 `review_decision`) | `decision_type` |
| 트레이드오프 요약 | 사람 (빈칸 허용) | `tradeoff_summary` |
| 미해결 리스크 | 사람 (`;` 구분) | `unresolved_risks` |
| 담당 / 상태 | 사람 — **회의 기록용, 이번 단계 미반입** | 미반입 (§4) |

- **결정이 채워진 행만 Decision이 된다**: `결정`은 필수 열 — 빈 행은 거부 목록에 한국어
  사유로 보고된다(전량 실패 아님). 사람이 결정 없는 행을 지우지 않아도 된다.
- `Decision.event_id` 필수 문제는 **온톨로지 무변경**으로 해소: 리뷰 회의를
  `development_events` 매핑(Phase 1)으로 먼저 반입하고 그 ID를 기입한다.
  (event_id optional화 대안은 기각 — 결정은 항상 어떤 검토 사건에서 나온다는 계약 유지.)

### 2.2 `decisions` IngestMapping

`supporting_basis`는 Phase 1의 단일 하위 객체 리스트(`single_item_lists`) 재사용 —
행당 근거 1건. 다중 근거 결정은 같은 결정 ID로 만들지 **않는다**(id 중복) — 회의에서
근거가 여럿이면 대표 근거 1건 + `트레이드오프 요약`에 서술(한계는 §4).

## 3. Frontend — 템플릿 개정 + 계약 고정 테스트

- `toDecisionCsv`를 §2.1 컬럼으로 개정, 함수와 헤더 상수를 export.
- vitest: 헤더가 계약 목록과 일치 + 시스템 컬럼 프리필 검증.
- backend test: 같은 헤더 문자열로 만든 CSV가 `decisions` 매핑으로 수락됨을 고정 —
  **양쪽 테스트가 본 문서 §2.1을 기준으로 동일 리터럴을 검증**한다 (드리프트 시 각자 실패).

## 4. invariant 준수와 한계

- 쓰기는 ingest 배치뿐 — 신규 API 없음. rollback으로 결정 일괄 취소 가능.
- 결정 자동 생성·owner 자동 할당 없음 — `결정`은 사람이 채운 값 그대로.
  `담당/상태`는 Decision 계약에 없어 미반입(회의 기록) — ActionItem 반입은 후속
  (05 Stage 20 #3, 같은 CSV에 두 번째 매핑을 돌리는 방식 검토).
- traceability는 기존 규칙 재사용: `decisions`는 `event_id`(관련_이벤트)·
  `project_id`(소속_프로젝트)로 이미 연결된다 (`resolve/traceability.py`).
- ingest는 소프트 참조 — 회의 이벤트 ID 오기입은 검증 오류가 아니라 미연결로 나타난다
  (check_integrity soft 규칙과 동일 지위). 문서/템플릿에 명시.

## 5. 수용 기준

1. 채운 결정 CSV 반입 → `Decision` 객체 생성, `결정` 빈 행은 한국어 사유로 거부 보고.
2. 반입 결정이 traceability(회의 이벤트↔결정)로 조회된다. rollback 시 소멸.
3. 프론트 CSV 헤더 = 매핑 계약 (양쪽 테스트 고정). 시스템 컬럼 프리필 동작.
4. 온톨로지/schema 무변경 (Decision 모델 그대로). 수치 점수 없음.

## 6. 구현 순서

1. 본 설계 문서. → 2. `decisions` 매핑 + 샘플 CSV + 테스트. →
3. 프론트 `toDecisionCsv` v2 + 테스트. → 4. E2E + CHANGELOG.
