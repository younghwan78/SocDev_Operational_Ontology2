# 근거 신뢰 사다리 (Evidence Ladder) — 설계

> 상태: v1.0 (2026-07-09)
> 실현: 백로그 `08_bridge_followups.md` §3 P1(Evidence Ladder, G-3) — 단, 원점 §5.3의
> `evidence_level`(시맨틱 청크 메타)이 아니라 **핵심 근거 카탈로그에 실재하는 필드**로 재정초.
> 선행: `CLAUDE.md` §3(evidence-grounded), §6.3(정성 등급 허용·수치 점수 금지), risk.py 패턴.

## 1. 문제 — "이 근거를 얼마나 믿을 수 있나"가 종합되지 않는다

현재 근거 탐색 화면(`EvidencePage`)은 원시 필드 6종(availability, is_measurement/prediction,
known_limitation, source_system, scenario_match…)을 나열만 한다. 실무 리더는 "이 조언이
**이 시나리오의 실측**인지, **유사 사례에서 빌려온 초기 예측**인지"를 6개 필드를 눈으로
조합해 판단해야 한다 — 판단 TAT의 병목이자, 근거 강도가 의사결정에 반영되지 않는 갭.

원점 비전에서 근거의 지위(실측 vs 예측, 정합 vs 유사)는 go/no-go를 가르는 1급 정보다.
이를 **결정론 정성 등급 + 판정 근거**로 종합해 노출한다.

## 2. 계약 — 온톨로지 무변경, 파생 뷰만 추가

`GET /api/v1/evidence`는 원시 `EvidenceCatalogEntry`를 반환한다. 등급은 저장 계약이 아니라
**서비스 계층 계산 결과**다 (risk/source_map과 동일). 온톨로지 모델·fixture·glossary 무변경.

### 2.1 신뢰 등급(tier) — 강→약 5단, 명명 정성 등급 (수치 없음)

기존 필드만으로 top-down 우선순위 분류(첫 매치 확정):

| 순위 | tier | tier_ko | 규칙(기존 필드) | 사업적 의미 |
|---|---|---|---|---|
| — | `absent` | 부재·미가용 | `availability`∈{missing, planned} **또는** `scenario_match`=none **또는** `confidence_contribution`=none | 근거 미확보 — 판단 유보/수집 필요 |
| 1 | `measured_direct` | 실측·정합 | `is_measurement` ∧ `measurement_stage`∈{current_silicon, field} ∧ `scenario_match`=strong | 이 시나리오를 직접 실측 — 최강 |
| 2 | `measured_analogous` | 실측·유사 | `is_measurement` **또는** `measurement_stage`∈{current_silicon, field, previous_project, customer_project} | 실측이나 타 프로젝트/부분 정합에서 인용 |
| 3 | `emulated` | 에뮬레이션 | `measurement_stage`=emulator | 에뮬/초기 실측 — 방향성 근거 |
| 4 | `predicted` | 예측·설계 | 그 외(예: `is_prediction`, architecture 단계) | 예측·설계 산출물 — 검증 전 |

- `absent`를 최우선으로 걸러 "없는 근거를 강하게 신뢰"하는 오류를 차단한다.
- **수치 점수·가중치·rank 필드 없음.** 목록 순서(강→약)로만 서열을 표현 — CLAUDE.md §6.3 준수.
- 각 등급은 판정을 유발한 필드를 `BasisItem`(services/common)으로 동반한다 (rule=필드명).

### 2.2 파생 뷰 응답

```text
GET /api/v1/evidence/ladder?project_id=&scenario_id=   → EvidenceLadder
  distribution : list[TierBucket]   # 강→약 고정 순서, tier별 건수
  entries      : list[EvidenceStrengthItem]  # 항목별 tier + 판정 근거
  totals       : LadderTotals        # total / measured / predicted / absent 요약 헤드라인
```

- `TierBucket{tier, tier_ko, count}` — 분포(근거 건강도). "W의 결정은 대부분 예측에 얹혀 있다".
- `EvidenceStrengthItem{evidence_id, title, project_id, scenario_id, tier, tier_ko, basis, origin}`.
- `LadderTotals{total, measured, predicted, absent}` — 실측/예측/부재 3분 요약(정수 건수, 점수 아님).
- `origin`(synthetic/imported/integrated)을 함께 실어 **fixture→real 전환 시 같은 항목이
  사다리를 오르는(예측→실측) "레벨업"**을 나중에 가시화할 훅으로 둔다.

## 3. Frontend — 근거 탐색에 신뢰 분포 패널 + 항목 배지

- `EvidencePage` 상단에 **근거 신뢰 분포** 카드: tier별 세그먼트 바 + 실측/예측/부재 헤드라인.
- 기존 근거 목록의 각 행에 **신뢰 등급 배지**(강=badge-ok … 부재=badge-danger) 추가 —
  `/evidence/ladder`의 entries를 id로 조인(기존 `/evidence` 목록 유지, 필드 중복 최소화).
- UI 문자열은 `i18n/ko.ts`, tier 라벨은 서비스의 `TIER_LABELS`(risk의 GRADE_LABELS 패턴).

## 4. invariant 준수 체크

- 결정론 GET 파생 뷰 — LLM·쓰기 없음. `test_no_write_endpoints` 무영향.
- 정성 등급 + 근거 목록, 수치 점수/가중치/rank 없음 (§6.3).
- 온톨로지/fixture/glossary/JSON Schema 무변경 — 계약 프리(F1~F3과 동일 지위).
- 근거 부족(absent)은 등급을 낮추고 근거로 명시 — "근거 없는 high confidence 금지"(§3) 정합.

## 5. 수용 기준

1. 동일 fixture → 동일 사다리(결정론). 저장 부작용 없음.
2. 모든 항목이 정확히 한 tier로 분류되고 최소 1개 판정 근거를 갖는다.
3. distribution 건수 합 = entries 수 = 필터된 evidence_catalog 수.
4. tier 라벨 한국어. 응답 계약에 score/weight/rank 필드 없음.
5. project/scenario 필터가 `/evidence`와 동일하게 동작.

## 6. 구현 순서 (각 단계 commit)

1. 설계 문서(본 문서).
2. `backend/services/evidence_ladder.py` + `GET /evidence/ladder` + 테스트.
3. Frontend 분포 패널 + 항목 배지 + i18n/client 타입.
4. CHANGELOG·`08_bridge_followups.md`(P1 진행) 갱신.
