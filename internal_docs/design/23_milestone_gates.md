# 설계 23 — 마일스톤 게이트 조건 형식화 (설계 22 후속 ④)

> 출처: `internal_docs/design/22_digital_twin_alignment.md` §6 후속 예고 ④ +
> 레퍼런스 문서의 `Milestone → gates / milestone_gate_review`(게이트 판정의
> 증거 번들) 대응. 리뷰 팩이 사실상 이미 하는 일(증거 번들 조립)에 부족했던
> 한 조각 — **마일스톤에 exit 기준을 계약으로 명시하고, 충족 여부를 결정론으로
> 판정** — 을 채운다. 도메인 모델 변경이므로 §6.2 변경 규율 체인을 따른다.

## 1. 원칙과 범위

- **판정은 결정론**: LLM 무관. 충족/미충족/판정 불가 3값 + 근거 ref 목록.
  수치 점수·가중치·자동 차단 없음 (§6.3 — 건수 상한 같은 결정론 기준은 점수가
  아니다). 게이트는 **판정을 보여줄 뿐 아무것도 막지 않는다** (조언 시스템 지위).
- **In**: `GateCriterion` 계약(3종 kind) + `ProjectMilestone.exit_criteria`
  (additive, 기본 빈 목록 — 56 유래 데이터 무변경 통과) / `GateReviewService`
  파생 뷰 / 리뷰 팩 문서 통합(`ReviewPackDocument.gates`) / 리뷰 센터 UI 섹션 /
  fixture 3개 마일스톤 예시 / glossary·VALUE_LABELS·JSON Schema 동기화.
- **Out**: 게이트 전용 화면(4화면 상한), 독립 API 엔드포인트(리뷰 팩 경유로
  충분 — 필요 시 후속), 판정 이력 저장(파생 뷰 — as-of로 재구성 가능), 새
  criterion kind 추가(사내 게이트 정의 확보 후), writeback(⑤).

## 2. 계약 (§6.2 체인: 모델 → glossary → schema → fixture)

```python
class GateCriterion(OntologyModel):
    criterion_id: str
    kind: str                 # gate_criterion_kind 도메인 (아래 3종)
    description: str          # 사람이 읽는 기준 서술 (한국어)
    # kind별 파라미터 — 해당 kind에서만 의미를 갖는다
    max_open_issues: int | None = None    # max_open_issues: 허용 상한 (기본 0)
    min_severity: str | None = None       # max_open_issues: 이 심각도 이상만 계수
    evidence_types: list[str] = []        # required_evidence: 요구 근거 유형
    scenario_ids: list[str] = []          # 범위 제한 — 비면 프로젝트 전체

class ProjectMilestone(OntologyObject):
    ...  # 기존 필드 무변경
    exit_criteria: list[GateCriterion] = []   # additive
```

### 2.1 criterion kind 3종 (v1 — 전부 기존 결정론 재료로 판정)

| kind | 뜻 | 판정 재료 | met 조건 |
|---|---|---|---|
| `max_open_issues` | 미해결 이슈 상한 | issues (status ∉ 종결, scenario 범위·min_severity 필터) | 미해결 건수 ≤ max_open_issues(기본 0) |
| `required_evidence` | 요구 근거 존재 | evidence_catalog (evidence_type별, scenario 범위) | 요구 유형 각각에 `availability=available` 항목 ≥ 1 |
| `verified_closure` | 검증된 종결 | issues(종결 상태) × tests | 종결 이슈마다 `verifying_test_ids` 중 `result=passed` ≥ 1 (RCA "검증 없는 종결" 경고의 게이트화) |

- 종결 상태 = `resolved / closed / done` (process_model ISSUE_STAGES의 해결·종결 단계).
- 미해결 = 그 외 상태 (`open / synthetic_open / under_analysis / workaround_applied`).
- min_severity 순서: `critical > high > medium > low > info` (severity 도메인).
  severity 없는 이슈는 필터 시 계수하지 않는다 — 근거 없는 심각도 추정 금지,
  대신 판정 note에 "심각도 미기재 n건 제외"를 명시한다 (침묵 금지).

### 2.2 판정 값

`met`(충족) / `not_met`(미충족) / `not_evaluable`(판정 불가 — 미등재 kind,
필수 파라미터 누락). 요구 대상 데이터가 0건인 경우는 not_evaluable이 아니라
**사실대로 판정**한다: required_evidence에서 해당 유형 근거가 하나도 없으면
not_met(근거 부재도 사실), verified_closure에서 종결 이슈가 0건이면 met(위반
없음)이며 note에 "종결 이슈 없음"을 명시한다.

### 2.3 파생 뷰 (저장하지 않음)

```python
class GateBasisRef:      # 판정 근거 한 건 — 위험 지도 basis와 같은 문법
    ref_collection: str; ref_id: str; note_ko: str
class GateCriterionVerdict:
    criterion_id: str; kind: str; kind_ko: str; description: str
    verdict: str; verdict_ko: str; note_ko: str
    basis: list[GateBasisRef]        # 위반 이슈/발견·누락 근거 등
class MilestoneGateReview:
    milestone_id: str; milestone_title: str; project_id: str
    week: int | None; met: int; not_met: int; not_evaluable: int   # 정수 집계
    criteria: list[GateCriterionVerdict]
```

`ReviewPackDocument.gates: list[MilestoneGateReview] = []` (additive) —
pack.project_ids에 속한 마일스톤 중 **exit_criteria가 있는 것만**, week 순.

## 3. UX — 리뷰 센터 팩 문서 "마일스톤 게이트" 섹션

롤업 카드 다음에:

```text
┌ 마일스톤 게이트 ────────────────────────────────────┐
│ Project W specification freeze (W21)   충족 1 · 미충족 1 │
│  [미충족] 스펙 확정 전 실측 근거 확보                    │
│     요구 유형 current_project_measurement — available 0건 │
│     · 누락: 실측 근거 없음 (uhd60_recording_eis_on)      │
│  [충족] 치명·높음 미해결 이슈 0건                         │
└──────────────────────────────────────────────────────┘
```

- 배지: 충족=`badge-ok`, 미충족=`badge-danger`, 판정 불가=`badge-warn`.
  **미충족은 경고색이되 차단 아님** — 문구는 항상 "판정+근거"이며 지시가 아니다.
- basis 행은 hover에 ref_id (내부 ID 화면 노출 금지 원칙 유지).
- exit_criteria 있는 마일스톤이 없으면 섹션 자체를 렌더하지 않는다.
- i18n: `ko.review_pack.gate_*`. verdict/kind 라벨은 VALUE_LABELS 경유.

## 4. glossary·스키마·fixture

- OBJECT_LABELS: `GateCriterion: "게이트 기준"`. 필드 라벨: `exit_criteria`
  (ProjectMilestone), criterion_id/kind/max_open_issues/min_severity/
  evidence_types (GateCriterion 전용; description·scenario_ids는 공통 라벨 재사용).
- VALUE_LABELS: `gate_criterion_kind` {max_open_issues: 미해결 이슈 상한 /
  required_evidence: 요구 근거 존재 / verified_closure: 검증된 종결},
  `gate_verdict` {met: 충족 / not_met: 미충족 / not_evaluable: 판정 불가}.
- JSON Schema 재생성 (`python -m backend.ontology.schema_export`).
- fixture: `project_w_spec_freeze_q2`(required_evidence + max_open_issues),
  `project_w_architecture_review_q2_q3`(verified_closure),
  `project_u_es_release_w12`(max_open_issues min_severity=high) — 리뷰 팩
  fixture(pack_project_w_multimedia_review)가 project_w라 팩 화면에서 보인다.

## 5. 수용 기준

- [ ] kind 3종 × met/not_met 판정 단위 테스트 + scenario 범위 필터 +
  min_severity(미기재 제외 note) + 미등재 kind→not_evaluable + 종결 0건→met
- [ ] exit_criteria 없는 마일스톤은 gates에 나타나지 않음
- [ ] 리뷰 팩 문서에 gates 포함 (기존 소비처 무파손 — additive)
- [ ] 56 유래 fixture/반입 데이터가 exit_criteria 없이 통과 (기본값)
- [ ] schema/glossary/VALUE_LABELS 동기화 (드리프트 테스트 green)
- [ ] UI: 게이트 섹션 렌더 + 배지 3종 + 빈 게이트 시 미렌더 (프론트 테스트)
- [ ] 전체 회귀 + 실서버(PG) smoke
