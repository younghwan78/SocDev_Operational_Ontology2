# 조언 레이어 → 운영체제 다리 (Advisory → Operating System Bridge)

> 상태: v1.0 (2026-07-09 — 신규)
> 최상위 기준: 원점 문서 `26.06.18 SoC ontology (ChatGPT).md`, `26.07.05 비지니스 가치 논의.md`
> 선행 문서: `05_long_term_improvement_plan.md`(Stage 13~20), `CLAUDE.md` §3·§6.3(불변 원칙)
> 목적: 현재 58이 갖춘 "조언·조회 레이어"를 원점 비전의 "SoC Development Operating System"으로
>   진화시키는 세 개의 저비용·고효과 기능을 **계약 변경 없이 파생 뷰(결정론)로** 추가한다.

---

## 0. 왜 이 세 기능인가 — 비전 대비 갭

원점 Palantir 모델은 4층이다: **객체 → 링크 → action/function → 실행·피드백 루프.**
현재 58은 3층(조회·조언·감사)에서 의도적으로 멈춰 있다(쓰기/자동실행 금지, CLAUDE.md §6.3).
이 가드레일을 **유지하면서** 비전의 4층으로 다가가는 세 다리:

| # | 기능 | 비전 근거 | 해소하는 갭 |
|---|---|---|---|
| F1 | **출처 지도** (Source Coverage / Fragmentation Map) | 원점 §8·§9 MVP 화면, 07.05 "맥락 파편화" | `SourceMeta.origin`이 전 객체에 이미 있으나 화면에 없음 → 파편화·진척 미가시화 |
| F2 | **엔티티 해석** (Entity Resolution) | 원점 §2 "식별자 파편화", `ip_aliases` "반드시 필요" | 명칭 불일치 해석이 `risk.py` 휴리스틱에 흩어짐(L8) → 커넥터 전제 부재 |
| F3 | **실행 초안** (Action Draft) | 원점 §1 4층 루프, §5 "review pack/checklist 생성" | 조언이 실행 초안으로 이어지지 않음 → advisory tool에 머묾 |

### 불변 원칙 준수 (세 기능 공통)

1. 셋 다 **결정론 파생 뷰(GET)** 다. 온톨로지 쓰기·자동 실행·수치 점수 없음.
2. F3(실행 초안)은 **생성만** 한다 — 저장·owner 자동할당 없음. "사람이 검토·커밋"이 계약.
   재진입은 ingest 계층으로만(기존 규율). `test_no_write_endpoints`는 GET이라 무영향.
3. 모든 출력 항목은 근거(`BasisItem`/`source_refs`)를 동반한다(§3 evidence-grounded).
4. 파생 뷰이므로 glossary 대상 아님 — RiskCell처럼 인라인 `_ko` 라벨 사용.
5. UI 문자열은 `frontend/src/i18n/ko.ts` 단일 소스, 내부 ID 노출 금지(hover/title만).

---

## 1. F1 — 출처 지도 (Source Coverage Map)

### 1.1 무엇을

전 컬렉션의 `SourceMeta.origin`(synthetic/imported/integrated)과 `ref` 유무를 집계해
"이 시스템의 지식 중 무엇이 가상이고 무엇이 실데이터인가"를 한 화면에 보인다.
파일럿 온보딩·top-management 설득 도구이자, synthetic→integrated 진척의 시각화.

### 1.2 백엔드 — `backend/services/source_map.py`

- `SourceCoverageService(repo)`; `coverage() -> SourceCoverage`.
- 컬렉션별로 `repo.list(key)` 순회하며 origin별 카운트 + `ref` 누락 카운트 집계.
- `collection_ko`는 `COLLECTIONS[key]` 모델명 → `glossary.object_label()`로 파생(신규 라벨 불필요).
- 응답 모델(인라인 `_ko`):
  - `SourceCoverage { collections: list[CollectionCoverage], totals: OriginTotals }`
  - `CollectionCoverage { collection, collection_ko, total, synthetic, imported, integrated, without_ref }`
  - `OriginTotals { total, synthetic, imported, integrated, integrated_ratio_note }`
    (비율은 "N/M" 문자열·정성 문구로 표기 — **수치 점수 아님**, 단순 집계 건수/비율 표시).
- 정렬: 실데이터(imported+integrated) 많은 컬렉션 먼저, 그다음 total 내림차순.

### 1.3 API / 프론트

- `GET /api/v1/source-map` → `SourceCoverage`.
- 프론트 `pages/SourceMapPage.tsx` — 데이터 탐색 그룹 내비에 "출처 지도" 추가.
  컬렉션별 막대(가상/반입/연동 세그먼트) + 전체 요약 카드 + `without_ref` 경고 뱃지.

### 1.4 수용 기준

- [ ] `GET /api/v1/source-map`이 전 컬렉션 origin 집계를 반환(동일 fixture → 동일 출력 테스트)
- [ ] 현재 fixture는 대부분 synthetic + `_58` 오버레이로 표시됨을 화면에서 확인
- [ ] 반입(Stage 15) 시 해당 컬렉션의 imported 막대가 증가함(반입 통합 테스트로 후행 검증 가능)

---

## 2. F2 — 엔티티 해석 (Entity Resolution)

### 2.1 무엇을

IP 명칭 불일치(ISP/IFE/IPE/Titan/CAM_IFE…)를 canonical `ip_id`로 해석하는 **1급 서비스**와,
해석되지 않는 토큰의 **큐레이션 큐**를 만든다. 원점이 "반드시 필요"라 못박은 `ip_aliases`의
구현체이자, `risk.py::ip_match_tokens` 휴리스틱(L8)을 대체 가능한 공용 인덱스.

### 2.2 백엔드 — `backend/resolve/entity_resolution.py`

- `IPAliasIndex(repo)`: `IPBlock`의 `name`/`domain`/`aliases` + 도메인 토큰을 정규화해
  `token → ip_id` 역인덱스 구축. (정규화 = lower + `_` 분해, `risk.py`의 기존 규칙 재사용)
- `resolve(token) -> str | None`.
- `report() -> EntityResolutionReport`:
  - `aliases: list[AliasEntry { ip_id, ip_name, aliases }]` — canonical 별칭표.
  - `unmatched: list[UnmatchedToken { token, occurrences, sample_refs }]` —
    전 `DevelopmentEvent.affected_domains`(+ 추후 반입 이슈 토큰)를 해석 시도해 실패한 토큰 큐.
- **큐레이션 경로**: unmatched는 화면·JSON으로 노출만 하고, 교정은 `IPBlock.aliases`를
  변경 규율(설계→모델/fixture→테스트→changelog)로 반영 — 쓰기 API 없음.

### 2.3 API / 프론트

- `GET /api/v1/entity-resolution` → `EntityResolutionReport`.
- 출처 지도 페이지 하단에 "식별자 해석" 섹션으로 표시(별칭표 + 미해석 큐).
  독립 페이지 대신 파편화 맥락과 함께 두어 "식별자 파편화"를 한 화면에서 본다.

### 2.4 후속 정합(선택, 이 단계 out-of-scope)

`risk.py::event_related_ips`를 `IPAliasIndex.resolve`로 통일하는 리팩터는 L8 해소의 다음 수순.
본 단계는 **인덱스·리포트 신설까지**로 한정(기존 risk 동작·테스트 기대값 불변 유지).

### 2.5 수용 기준

- [ ] `IPBlock`의 alias/domain이 canonical ip_id로 해석됨(고정 테스트)
- [ ] fixture의 event affected_domains 중 미해석 토큰이 큐로 수집됨(있다면)
- [ ] 미해석 큐가 화면·JSON으로 노출, 쓰기 경로 없음

---

## 3. F3 — 실행 초안 (Action Draft)

### 3.1 무엇을

시나리오(및 선택적 변경 컨텍스트) 기준으로 **리뷰 팩/체크리스트 초안**을 결정론으로 조립한다.
기존 파생 뷰(위험 근거·미해결 이슈·변경 영향 체크리스트)를 한 장의 "실행 초안"으로 묶어
**사람이 복사·다운로드하여 검토·커밋**한다. 자동 실행·저장·할당 없음 — 조언 tool과
operating system을 가르는 다리.

### 3.2 백엔드 — `backend/services/action_draft.py`

- `ActionDraftService(repo)`; `draft(scenario_id) -> ActionDraft`.
- 조립 소스(전부 기존 결정론 서비스 재사용):
  - `RiskService.heatmap()`에서 해당 시나리오 행의 `overall_basis` → "위험 근거" 섹션.
  - `RCAService`에서 해당 시나리오 연결 미해결/미검증 이슈 → "확인 필요 이슈" 섹션.
  - 시나리오의 미해결 근거 공백(review/risk 파생) → "근거 수집" 섹션.
- 응답 모델(인라인 `_ko`):
  - `ActionDraft { scenario_id, scenario_name, generated_context, sections: list[DraftSection], provenance_note }`
  - `DraftSection { kind, kind_ko, title, items: list[DraftItem] }`
  - `DraftItem { statement, basis: list[BasisItem], suggested_role_ko | None }`
    (`suggested_role`은 변경영향 체크리스트의 **역할 관점**을 정성 인용한 것 — 자동 할당 아님)
  - `provenance_note`: "이 문서는 결정론 파생 초안이며 최종 결정·할당이 아님. 사람이 검토·커밋."
- **저장 안 함.** ID·상태·owner 없음.

### 3.3 API / 프론트

- `GET /api/v1/action-draft/scenario/{scenario_id}` → `ActionDraft` (읽기 전용).
- 시나리오 상세(또는 위험 지도 행)에서 "실행 초안 생성" → 초안 표시 →
  "복사(JSON)" / "복사(Markdown)" 버튼(기존 change_impact `copy_checklist` 패턴 재사용).
- 초안 상단에 `provenance_note` 경고 배지 상시 노출.

### 3.4 수용 기준

- [ ] `GET /api/v1/action-draft/scenario/{id}`가 근거 동반 섹션을 반환(동일 fixture → 동일 출력)
- [ ] 모든 `DraftItem`이 최소 1개 `basis`를 가짐(근거 없는 초안 항목 금지)
- [ ] 초안이 저장되지 않음 — 조회 후 재조회해도 부작용 없음, 쓰기 경로 부재 유지
- [ ] 화면에서 초안 생성 → Markdown 복사 동작

---

## 4. 구현 순서 · 단계별 커밋

각 단계: 구현 → 전체 회귀(§5) → docs 갱신(필요 시) → CHANGELOG → **commit**.

```text
Step 0. 본 설계 문서 + CURRENT_TASK.md scope lock           → commit
Step 1. F1 출처 지도 (service+API+test+FE+openapi 재생성)   → commit
Step 2. F2 엔티티 해석 (resolve+API+test+FE 섹션)           → commit
Step 3. F3 실행 초안 (service+API+test+FE 버튼)             → commit
```

의존: F1이 가장 단순(계약 무변경)해 먼저. F2는 F1 페이지에 섹션 추가. F3는 독립.
셋 다 온톨로지 모델 변경 없음 → 변경 규율 6단계 중 fixture/schema 재생성 불필요,
단 **openapi 재생성 + `npm run gen:api`** 는 API 추가마다 필수(드리프트 테스트가 강제).

## 5. 회귀 명령 (매 단계)

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
uv run python -m backend.api.openapi_export   # API 추가 시
uv run python -m backend.cli.main validate-data
cd frontend && npm run gen:api && npm run build && npm run test && npm run lint
```

## 6. 이 다리 이후 (본 문서 범위 밖)

- F2 → `risk.py` 귀속을 `IPAliasIndex`로 통일(L8 완전 해소) → 05 Stage 15와 병합.
- F3 → 초안을 `ReviewPack` 반입 템플릿으로 내보내 "결정 ← 근거" 추적(05 Stage 20 #3).
- F1 → 반입 진척 지표를 파일럿 효과 지표 패널에 편입(05 Stage 17).
