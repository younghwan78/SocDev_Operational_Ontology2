# 리뷰 팩 조립 — 결정 ← 근거 루프 (B3) 설계

> 상태: v1.0 (2026-07-10)
> 실현: 백로그 `08_bridge_followups.md` §2 B3. 원점 4층 루프의 마지막 고리(review → decision).
> 선행: `07_advisory_to_os_bridge.md`(Bridge F3), `09_evidence_ladder.md`(근거 태세).

## 1. 문제 — 정의만 되고 안 쓰이는 ReviewPack, 닫히지 않는 루프

`ReviewPack`(함께 검토할 시나리오 묶음)은 온톨로지에 정의·등록됐지만 **어떤 서비스·화면에서도
노출되지 않는다**(fixture `pack_project_w_multimedia_review` 1건 — W의 3개 시나리오 묶음).
한편 실행 초안(F3)은 시나리오 1개 단위라, 리뷰 회의에서 **여러 시나리오를 한 번에** 검토하고
**결정을 근거에 연결해 추적**하는 흐름이 없다 — "대시보드"에 머물고 "운영체제"의 피드백 루프가 열려 있다.

## 2. 계약 — 기존 초안·태세 재사용, 파생 뷰만 추가 (온톨로지 무변경)

`ReviewPack`이 묶은 시나리오들의 **실행 초안(ActionDraft)을 한 장으로 조립**한다. 각 시나리오의
위험 근거·이슈·근거 공백 + 근거 태세를 그대로 싣고, 회의용 롤업을 더한다. 저장하지 않는다.

### 2.1 응답

```text
GET /api/v1/review-packs              → list[ReviewPackSummary]
GET /api/v1/review-packs/{pack_id}    → ReviewPackDocument   (없으면 404)
```

- `ReviewPackSummary{pack_id, title, purpose, project_ids, scenario_ids}`.
- `ReviewPackDocument{pack_id, title, purpose, project_ids, scenarios: ActionDraft[], rollup, provenance_note}`.
  - 시나리오 단위는 **F3 ActionDraft를 그대로 재사용**(scenario/posture/sections 포함) — 중복 계약 없음.
  - `ReviewPackRollup{scenario_count, risk_items, issue_items, evidence_gap_items, measured, predicted, absent}`
    — 회의 헤드라인(항목·근거 태세 집계, 정수 건수, 점수 아님).

### 2.2 결정 round-trip CSV (프론트 생성)

리뷰 팩을 **결정 컬럼이 빈 CSV**로 내보낸다 — 회의에서 사람이 채우고, 추후 ingest로 재진입해
`Decision`으로 추적(B3b 후속). 백엔드는 JSON GET만 두고 CSV는 프론트에서 조립(F3 복사 패턴).

| 컬럼 | 채움 | 의미 |
|---|---|---|
| 시나리오 / 항목종류 / 진술 / 근거ref / 신뢰등급 | 시스템 | 근거 있는 검토 항목 |
| 결정 / 담당 / 상태 | **사람(빈칸)** | 회의 산출 — 재진입 시 Decision 근거로 |

## 3. Frontend — 리뷰 센터에 리뷰 팩

리뷰 센터(주간 스냅샷) 상단에 **리뷰 팩** 섹션: 팩 목록 → 선택 시 조립 문서(시나리오별 태세 배지 +
초안 섹션) + **CSV 내보내기(결정 템플릿)** 버튼. 라우팅은 로컬 상태(선택 팩)로 단순 유지.

## 4. invariant 준수

- 결정론 GET 파생 뷰 — LLM·쓰기 없음. `test_no_write_endpoints` 무영향.
- 온톨로지/fixture/glossary/JSON Schema 무변경 — 계약 프리(F1~F3·사다리와 동일 지위).
- 결정 자동 생성·owner 자동할당 없음 — CSV는 사람이 채우고, 재진입은 ingest로만(§6.3).
- 정성 태세만, 수치 점수/가중치/rank 없음.

## 5. 수용 기준

1. 동일 fixture → 동일 조립(결정론). 저장 부작용 없음.
2. 팩의 각 시나리오가 초안(있으면 섹션, 없어도 태세)으로 포함되고, rollup 집계가 시나리오 합과 일치.
3. 없는 pack_id → 404.
4. 요약/문서 한국어. 응답 계약에 score/weight/rank 없음.

## 6. 구현 순서 (각 단계 commit)

1. 설계 문서(본 문서).
2. `backend/services/review_pack.py` + `GET /review-packs`·`/{id}` + 테스트.
3. Frontend 리뷰 팩 섹션 + CSV 내보내기 + i18n/client 타입.
4. CHANGELOG·`08_bridge_followups.md`(B3 완료) 갱신. B3b(재진입 ingest)는 후속 기록.
