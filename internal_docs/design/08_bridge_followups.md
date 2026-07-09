# Bridge 이후 후속 작업 백로그

> 상태: v1.1 (2026-07-09 — H1·B1 완료 반영)
> 목적: 다음 세션이 이 문서만으로 이어받을 수 있도록 남은 일을 기록한다.
> 선행: `07_advisory_to_os_bridge.md`(Bridge 설계), `05_long_term_improvement_plan.md`(Stage 13~20)
> 각 항목 착수는 사용자 승인 필요 (CLAUDE.md §6.1).
>
> **완료: H1(lint 게이트 복구), B1(L8 귀속 통일) — CHANGELOG 참조.**
> 남은 우선 후보: H2/H3(위생), B2/B3(Bridge 연장), P1~P4(전략), 실데이터 워크숍(05 Stage 13).

---

## 0. 지금까지 (2026-07-09, 커밋 `4242786` push 완료)

- 05 장기 계획 v1.2 (검토 반영: G1 baseline, Stage 13 2트랙, UI 위생 조기화 등).
- Bridge 3기능 완료 — 전부 계약 변경 없는 결정론 파생 뷰(GET):
  - **F1 출처 지도** `GET /api/v1/source-map` — origin 집계(가상/반입/연동) 가시화.
  - **F2 엔티티 해석** `GET /api/v1/entity-resolution` — IP 별칭표 + 미해석 큐레이션 큐.
  - **F3 실행 초안** `GET /api/v1/action-draft/scenario/{id}` — 리뷰 팩 초안(무저장, 사람이 커밋).
- 회귀 기준선: backend 144 passed / 9 skipped, ruff·mypy(56 files) pass, validate-data 오류 0,
  frontend build/test(21) pass.

---

## 1. 즉시 정리(위생) — 작아서 아무 때나

| # | 항목 | 근거/위치 | 조치 |
|---|---|---|---|
| ~~H1~~ ✅ | ~~frontend lint 기존 오류 3건~~ **완료(2026-07-09)** | `DemoStoryBar`, `AskPage` | `SceneBar` key-remount + `question` URL 파생으로 render 순수성 위반 제거. lint 0. |
| H2 | **`frontend/tsconfig.tsbuildinfo` 추적됨** | 빌드마다 변경되는 캐시 아티팩트가 git에 추적 중 | `git rm --cached` + `.gitignore` 추가. |
| H3 | **원점 문서 사본 2개 디스크 잔존** | `internal_docs/26.06.18 …md`, `26.07.05 …md` (gitignore로 추적만 제외됨) | 참조본은 `D:\YHJOO\…`가 정본(CLAUDE.md §7). 디스크 사본은 삭제 여부를 사용자 결정. |

---

## 2. Bridge 자연 연장 (설계 07 §6에 명시)

| # | 항목 | 내용 | 편입 대상 |
|---|---|---|---|
| ~~B1~~ ✅ | ~~F2 → risk.py 귀속 통일 (L8 완전 해소)~~ **완료(2026-07-09)** | `IPAliasIndex.resolve_all`(다중값) 추가 → `event_related_ips` 재작성, `ip_match_tokens` 폐기. change_impact도 공용 인덱스 사용. **동작 보존**(63/63 이벤트 일치)이라 `test_risk` 무변경. | — |
| B2 | **F1 → 반입 진척 지표 상시화** | 출처 지도의 synthetic→integrated 비율을 파일럿 효과 지표 패널에 편입(홈 하단 카드). | 05 Stage 17 |
| ~~B3~~ ✅ | ~~F3 → 초안을 ReviewPack 반입으로~~ **완료(2026-07-10)** | 설계 `10_review_pack.md`. ReviewPack이 묶은 시나리오들의 실행 초안+근거 태세를 조립하는 파생 뷰(`GET /review-packs`) + 결정 컬럼 빈 round-trip CSV. **B3b(채운 CSV → ingest → Decision 재진입)는 후속** — ingest 매핑 필요. | B3b: 05 Stage 20 |

> B1 결과 메모: naive 단일 `resolve` 치환은 공유 토큰('memory'→MIF·SMMU, 'ai'→GPU·NPU)을
> 임의의 한 IP로 축소해 정당한 귀속을 잃는 **회귀**였다. 다중값 `resolve_all`로 현재 동작을
> 정확히 보존하면서 중복 휴리스틱만 제거하는 방향으로 수정함. (F2가 재확인한 "affected_domains가
> IP 토큰과 비-IP 개념축을 섞는다"는 지점은 데이터 계약 개선 과제로 남음 — 05 §3.2.)

---

## 3. 아직 안 한 전략 제안 (7/9 제안 §3 중 미착수)

Bridge에서 F1(=G-1)·F2(=G-2)·Action Draft(=§1)를 했다. 남은 제안:

| # | 제안 | 핵심 | 규모 | 근거 |
|---|---|---|---|---|
| ~~P1~~ ✅ | ~~Evidence Ladder 전면화 (G-3)~~ **완료(2026-07-09)** | 설계 `09_evidence_ladder.md`. 원점의 `evidence_level`(시맨틱 메타)이 아니라 evidence_catalog 실필드(measurement_stage·scenario_match·availability)로 재정초 — 강→약 5단 정성 등급 + 근거. `GET /evidence/ladder` + 근거 탐색 분포 패널. fixture→real "레벨업" 훅(origin) 포함. | — |
| P2 | **측정을 제품 기능으로 (G-4)** | TAT를 localStorage 데모 로깅이 아니라 "OS의 운영 지표"로. 05 Stage 17 telemetry를 코어 루프로 승격. **단 C1(pre-tool baseline) 선행 필수.** | M~L | 원점 §10, 05 C1 |
| P3 | **`Path` 객체 도입 (G-5)** | IPBlock/SystemInfluenceBlock만으로는 "ISP M2M **path**가 DDR을 밀었다"는 인과 경로 표현 불가. 대규모 계약 변경 — 도입 시 change_impact가 질적 도약. | L | 원점 §2 Phase 2, archetype 근본원인 서술 |
| P4 | **시퀀싱 이견 반영** | 05는 Stage 14(경화)를 실데이터(15) 앞에 둠 → "fixture 완벽주의 함정"(원점 §10 위험3) 위험. **CI만 얇게 먼저 + 실데이터 소량 반입 당기기** 재배열 검토. | 문서 | 원점 §10, 7/9 제안 §4 |

---

## 4. 다음 세션 착수 순서 권장

- ~~H1 lint 부채~~ ✅ / ~~B1 L8 해소~~ ✅ — 완료. Bridge 코드 레벨 마무리됨.
1. **H2/H3 위생** — `tsconfig.tsbuildinfo` untrack, 원점 문서 디스크 사본 처리(사용자 결정). 저비용.
2. 사용자 우선순위: 실데이터 워크숍(05 Stage 13) vs P1 Evidence Ladder vs P4 시퀀싱 재배열.

## 5. 착수 전 필독 (순서)

`CLAUDE.md` → `CURRENT_TASK.md` → 본 문서 → `07_advisory_to_os_bridge.md` →
`05_long_term_improvement_plan.md` 해당 Stage → 대상 서비스 코드와 그 테스트.
