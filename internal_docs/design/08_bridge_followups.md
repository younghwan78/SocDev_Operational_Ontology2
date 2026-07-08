# Bridge 이후 후속 작업 백로그

> 상태: v1.0 (2026-07-09 — Bridge F1~F3 완료 시점 기록)
> 목적: 오늘 여기서 중단. 다음 세션이 이 문서만으로 이어받을 수 있도록 남은 일을 기록한다.
> 선행: `07_advisory_to_os_bridge.md`(Bridge 설계), `05_long_term_improvement_plan.md`(Stage 13~20)
> 각 항목 착수는 사용자 승인 필요 (CLAUDE.md §6.1).

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
| H1 | **frontend lint 기존 오류 3건** | `DemoStoryBar.tsx:44,96`, `AskPage.tsx:47` — `react-hooks/set-state-in-effect`, "impure function during render" | HEAD에서도 재현되는 선존 부채(Bridge와 무관). effect 내 setState를 파생 계산/`useMemo`로 리팩터. **품질 게이트(lint pass) 복구 목적.** |
| H2 | **`frontend/tsconfig.tsbuildinfo` 추적됨** | 빌드마다 변경되는 캐시 아티팩트가 git에 추적 중 | `git rm --cached` + `.gitignore` 추가. |
| H3 | **원점 문서 사본 2개 디스크 잔존** | `internal_docs/26.06.18 …md`, `26.07.05 …md` (gitignore로 추적만 제외됨) | 참조본은 `D:\YHJOO\…`가 정본(CLAUDE.md §7). 디스크 사본은 삭제 여부를 사용자 결정. |

---

## 2. Bridge 자연 연장 (설계 07 §6에 명시)

| # | 항목 | 내용 | 편입 대상 |
|---|---|---|---|
| B1 | **F2 → risk.py 귀속 통일 (L8 완전 해소)** | `risk.py::event_related_ips`를 `IPAliasIndex.resolve`로 통일. "명시 링크 우선 → 별칭 해석 → (없으면) 미해석 큐" 순. `tests/test_risk.py` 고정 기대값 재검토 필요. | 05 Stage 15 |
| B2 | **F1 → 반입 진척 지표 상시화** | 출처 지도의 synthetic→integrated 비율을 파일럿 효과 지표 패널에 편입(홈 하단 카드). | 05 Stage 17 |
| B3 | **F3 → 초안을 ReviewPack 반입으로** | 실행 초안을 `ReviewPack` 반입 템플릿(CSV)으로 내보내 "결정 ← 근거" 추적. 데모 5장면째. | 05 Stage 20 #3 |

> B1은 F2가 이미 인덱스를 만들어 두어 **가장 저비용**. L8을 코드에서 실제로 지운다.

---

## 3. 아직 안 한 전략 제안 (7/9 제안 §3 중 미착수)

Bridge에서 F1(=G-1)·F2(=G-2)·Action Draft(=§1)를 했다. 남은 제안:

| # | 제안 | 핵심 | 규모 | 근거 |
|---|---|---|---|---|
| P1 | **Evidence Ladder(0~5) 전면화 (G-3)** | `evidence.py`에 이미 있는 `evidence_level`·`confidence_upgrade_allowed`를 confidence와 매핑해 노출. fixture→real 전환 시 같은 객체가 Level 0→4로 "레벨업"하는 걸 시각화. G4(close evidence 연결률)의 상위 프레임. | M | 원점 §5.3 |
| P2 | **측정을 제품 기능으로 (G-4)** | TAT를 localStorage 데모 로깅이 아니라 "OS의 운영 지표"로. 05 Stage 17 telemetry를 코어 루프로 승격. **단 C1(pre-tool baseline) 선행 필수.** | M~L | 원점 §10, 05 C1 |
| P3 | **`Path` 객체 도입 (G-5)** | IPBlock/SystemInfluenceBlock만으로는 "ISP M2M **path**가 DDR을 밀었다"는 인과 경로 표현 불가. 대규모 계약 변경 — 도입 시 change_impact가 질적 도약. | L | 원점 §2 Phase 2, archetype 근본원인 서술 |
| P4 | **시퀀싱 이견 반영** | 05는 Stage 14(경화)를 실데이터(15) 앞에 둠 → "fixture 완벽주의 함정"(원점 §10 위험3) 위험. **CI만 얇게 먼저 + 실데이터 소량 반입 당기기** 재배열 검토. | 문서 | 원점 §10, 7/9 제안 §4 |

---

## 4. 다음 세션 착수 순서 권장

1. **H1 lint 부채** 정리 → 품질 게이트 green 복구 (독립적, 저비용).
2. **B1 (L8 해소)** — F2 인덱스 재사용, risk 테스트 갱신. Bridge를 코드에서 마무리.
3. 그다음은 사용자 우선순위: 실데이터 워크숍(05 Stage 13) vs P1 Evidence Ladder vs P4 재배열.

## 5. 착수 전 필독 (순서)

`CLAUDE.md` → `CURRENT_TASK.md` → 본 문서 → `07_advisory_to_os_bridge.md` →
`05_long_term_improvement_plan.md` 해당 Stage → 대상 서비스 코드와 그 테스트.
