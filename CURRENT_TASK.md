# CURRENT_TASK.md

## 활성 Stage

**활성 Stage 없음 — 설계 24(링크 제안, link-recovery 사외 선행분) 완료 (2026-07-19).**

> 설계·구현: `internal_docs/design/24_link_proposals.md` + CHANGELOG.
> 결정론 룰 3종(IP 별칭 토큰/시나리오 토큰/시나리오 사용 IP 연쇄) +
> `GET /link-proposals` + 출처 지도 검토 카드. 저장·자동 반영 없음 — 반영은
> 원천 수정→재반입만. backend 323 · frontend 46 · 실서버 왕복 검증 green.
>
> **다음 후보 (착수는 사용자 승인 — 남은 것은 전부 사내 입력 필요)**:
> - **⑤ JIRA writeback 코멘트** (Stage 19 실계정 — 보안 승인·자격증명),
>   **⑥ 잔여** = LLM/임베딩 제안 룰 추가 (Stage 18 임베딩 인프라).
> - 게이트 kind 확장(사내 게이트 정의), D4 검증 세션, Stage 14 잔여(SSO),
>   사내 반입 리허설, 스케일 트리거(이슈 1천건+ 시).
> - **사외에서 더 할 수 있는 것은 소진** — 설계 21~24로 twin 레퍼런스 정렬·
>   게이트·링크 큐레이션까지 완료. 다음 진전은 사내 데이터/계정/일정이 필요.

### 직전 완료 — 설계 23(마일스톤 게이트 조건 형식화) (2026-07-19)

> 설계·구현: `internal_docs/design/23_milestone_gates.md` + CHANGELOG.
> GateCriterion(kind 3종) + exit_criteria(additive) + GateReviewService
> (met/not_met/not_evaluable + 근거 ref) + 리뷰 팩 gates 통합 + UI 섹션 +
> 변환기 보강 fixture 3건. backend 316 · frontend 44 · 실서버 smoke green.
>
> **다음 후보 (착수는 사용자 승인)**:
> - **⑤ JIRA writeback 코멘트** (Stage 19 실계정 커넥터 결합 — 보안 승인 필요),
>   **⑥ link-recovery 제안 에이전트** (Stage 18 임베딩 결합).
> - 게이트 후속: 사내 게이트 정의 확보 후 criterion kind 확장, 필요 시 독립
>   API/포트폴리오 노출.
> - 사내 반입 리허설 / D4 검증 세션 / Stage 14·18·19 잔여 / 스케일 트리거 —
>   설계 21 마감 목록과 동일 (전부 사내 입력 필요).

### 직전 완료 — 설계 22(Digital Twin 레퍼런스 정렬 W1~W4) (2026-07-19)

> 설계·구현: `internal_docs/design/22_digital_twin_alignment.md` + CHANGELOG.
> W1 결정 워터마크+리뷰 센터 리플레이 링크 / W2 링크 커버리지 상설 지표
> (출처 지도 카드+배치 추이) / W3 `export-ocel` OCEL 2.0 JSON /
> W4 문서(기록 규율 캠페인·P1 exit 지표·프로세스 트윈 포지셔닝·게이트 인용
> 기준). backend 305 · PG 12 · frontend 42 · 실서버 smoke green. 전부
> additive — DB 마이그레이션 없음.
>
> **다음 후보 (착수는 사용자 승인)**:
> - **설계 23 후보 — 게이트 조건 형식화(④)**: `ProjectMilestone.exit_criteria`
>   계약 + 리뷰 팩 결정론 판정. §6.2 변경 규율 체인 필요 — 설계 문서 선행.
> - **⑤ JIRA writeback 코멘트** (Stage 19 실계정 커넥터 결합),
>   **⑥ link-recovery 제안 에이전트** (Stage 18 임베딩 결합).
> - 사내 반입 리허설 / D4 검증 세션 / Stage 14·18·19 잔여 / 스케일 트리거 —
>   설계 21 마감 목록과 동일 (전부 사내 입력 필요).
> - Out: domain-time 필드 신설, 새 화면 추가, 게이트 판정(④)·writeback(⑤)·
>   link-recovery(⑥), OCEL SQLite·PM4Py 의존성. 전부 additive — 마이그레이션 없음.

### 직전 완료 — 설계 21(사내 실데이터 구축 전 준비 R1~R9) (2026-07-18)

> 설계·구현: `internal_docs/design/21_pre_data_readiness.md` + CHANGELOG 최신 항목.
> R1 빈 DB 온보딩 / R2 반입 열 스펙 / R3 dry-run / R4 actor 기록 /
> R5 위험 지도 정렬+1주 프리셋 / R6 오류 detail+재시도 / R7 시나리오 상세 정합 /
> R8 P2 마감 / R9 마스터 데이터 절차 문서화. backend 289 · frontend 36 ·
> 실서버(PG) 검증 green. 전부 additive — DB 마이그레이션 없음.
>
> **다음 후보 (착수는 사용자 승인 — 전부 사내 입력 필요)**:
> - **사내 반입 리허설** — handover §2b 마스터 시드 절차 + dry-run 2단계 반입.
> - **D4 검증 세션 자료** / **Stage 13 트랙 A** — 사내 세션 일정 확정 시.
> - **Stage 14 잔여**(인증 고도화 — actor는 최소 기록만 넣었음, 사용자 식별은
>   사내 SSO 표준 필요), **Stage 18 잔여**(임베딩), **Stage 19**(실계정 커넥터 +
>   동기화 상태 UI).
> - 스케일 트리거(검토 보고서 §5): 이슈 1천건+ 시 서버 필터·가상화,
>   버전 로그 6개월분 as-of 응답 측정, 다과제 project_ids 복수화.

### 직전 완료 — Digital Twin 3라운드 Y1~Y3 (2026-07-17)

> 설계·구현 상태: `internal_docs/design/20_digital_twin_round3.md` (§6).
> Y1 프로세스 모델 레지스트리(이슈+액션+이벤트, history 판정 병기) /
> Y2 as-of 두 시점 diff(heatmap_diff 공유, 위험 지도 비교 시점+점선 오버레이) /
> Y3 변경 영향 as-of UI. backend 282 · PG 12 · frontend 34 · 실서버 green.
>
> **digital twin 후보는 소진** — 설계 15~20으로 시간 모델(T1~T3)·프로세스
> 신호·what-if 루프·KPI 시계열이 전부 표면화됐다.
>
> **다음 후보 (착수는 사용자 승인 — 전부 사내 입력 필요)**:
> - **D4 검증 세션 자료** (가설 판정 모드·TAT baseline) — 사내 세션 날짜/형식
>   확정 시 착수 (제안서 조건).
> - **Stage 13 트랙 A** (워크숍 검증+교정 루프) — 세션 일정과 연동.
> - **Stage 14 잔여** (인증 고도화/배포/캐시 정책) — 사내 표준 필요.
> - **Stage 18 잔여** (시맨틱 검색 사내분 — 임베딩 인프라), **Stage 19**
>   (JIRA/Confluence 실계정 커넥터) — 보안 승인·자격증명 필요.

### 직전 완료 — 디지털 트윈 데모 가이드 (2026-07-16)

> `docs/demo-digital-twin.md` + `samples/demo_twin_*.csv` — 2주 반입 스토리 위
> 4장면(프로세스 신호/as-of/what-if/KPI) 대본, 전 장면 실서버 검증 (`db52b50`).

### 직전 완료 — Digital Twin 후속 2라운드 (2026-07-16)

> 설계 17: Q1 전이 판정 배지(타임라인) / Q2 new_issue·issue_week_shift·
> changed_issue_signals / Q3 as-of 포트폴리오 UI + 변경 영향 API /
> Q4 --chart-1..4 팔레트(라이트·다크 검증) + KPI 선택기 확장(primary ∪ 관측).

### 직전 완료 — Digital Twin 갭 후속 4패키지 (2026-07-15)

> 설계 16: P1 전이 이력 신호(collection_versions·재개 배지·28일 정체) /
> P2 as-of(재생 규칙 4종 + AsOfMeta 정직성 메타 + 위험 지도 시점 재구성 UI) /
> P3 KPIObservation 계약+fixture 10점+반입 매핑+시계열 API·표 (운영 DB 재시드) /
> P4 POST /what-if(가정 2종, RiskService 재사용, 저장소 불변, 1클릭 UI).

### 직전 완료 — 시간 모델 T1+T2 (2026-07-14)

> append-only 버전 로그(0006) / 캡처 3관문(unchanged 무기록·retracted 불삭제·시드
> 멱등) / IngestWriterProtocol 4메서드 확장(Memory·PG 패리티) / history API·CLI·
> 이슈 상세 타임라인 / VALUE_LABELS change_kind. backend 235·frontend 34 green.

### 직전 완료 — D1~D3 (2026-07-12), D4는 검증 세션 일정 확정 대기

> D1 운영 배포 패키지(인증/로깅/compose 리허설/sync-status/runbook) /
> D2 문서 재정비(스크린샷 9장 headless 재캡처·ingest 가이드·핸드오버 킷) /
> D3 시맨틱 검색 사외 선행분(임베딩 provider·embed-chunks·Ask 하이브리드).
> **D4(검증 세션 자료 — 가설 판정 모드·TAT baseline)는 사내 세션 날짜/형식이
> 정해지면 착수** (제안서 조건). 사내 도입 절차: internal_docs/ops/handover.md.

### 직전 완료 — Backend B1~B5 사내 실운영 갭 교정 (2026-07-12)

> B1 Ask 정책 우회 수정 / B2 psycopg_pool 연결 계층(병렬·자동 복구·idle-in-tx 0) /
> B3 행동(action_items 왕복)·피드백(feedback_items 계약 배선) 재진입 /
> B4 LLM 캐시(질문+카드 지문, 자동 무효화) / B5 페이지네이션+CI PG job.
> 상세: CHANGELOG. **잔여(승인 필요)**: API 인증·구조화 로깅(Stage 14),
> sync-jira 스케줄 가이드, 시맨틱 검색(Stage 18).

### 직전 완료 — UI E1~E6 탐색 화면 6종 폴리싱 (2026-07-12)

> 포트폴리오(레인 상황판·과제 필터)/시나리오(도메인 칩·위험 배지)/리뷰 센터
> (주간 상황판·팩 열람·CSV 다운로드)/근거 탐색(사다리=필터)/출처 지도(한 줄
> 밀도)/데이터 반입(이력 4카운트) — 화면별 commit. VALUE_LABELS 3도메인 추가.
> 상세: CHANGELOG.

### 직전 완료 — Ask SoC A1~A5 재설계 (2026-07-12)

> A1 한↔영 도메인 브리지(한국어 질문 검색 복원) / A2 인라인 인용 마커(각주 칩) /
> A3 즉시 프리뷰(GET /ask/preview) / A5 Q&A 로그·FAQ(ask_log, 마이그레이션 0005 —
> 사용자 요청: 좋은 예제 축적) / A4 답변|카드 스플리터. 실서버 검증 완료.
> 상세: CHANGELOG. **범위 외**: 시맨틱 검색(Stage 18), 대화형 후속질문,
> 서버측 LLM 캐시(Stage 14).

### 직전 완료 — 반입 J1~J4(사내 데이터 현실 갭 교정) (2026-07-11)

> J1 품질 리포트+큐레이션 루프(거부 행 CSV·quarantine 보류 풀 — 재반입 자동 해소) /
> J2 upsert 증분 동기화(신규·갱신·변동 없음, --since auto, pagination, env prefix) /
> J3 신선도·일정 신호(정체/지연 배지, week_columns) / J4 이슈↔문서 연결
> (doc_refs·related_issue_ids·RCA 관련 문서 후보). 전부 실서버 왕복 검증. 설계:
> `internal_docs/design/14_ingest_reality_gaps.md`. 같은 날 UI W1~W3(코크핏)·
> G1~G3(변경 영향 전파 지도) 완료. 상세: CHANGELOG.
>
> **후속 후보(미착수, 승인 필요)**: upsert 버전 이력, 다과제 project_ids 복수화
> (설계 14 §4), 공통 StatusBadge/AsyncSection 리팩터, 목록 가상화(500건+),
> docs/ 스크린샷 재캡처, Stage 13 트랙 A 또는 Stage 14 잔여(인증/배포/캐시).

### 직전 완료 — UI 실사용자 재설계 P0~P2 (2026-07-11)

> 설계 `internal_docs/design/13_ui_operational_redesign.md` 전 패키지 구현·검증 완료
> (CHANGELOG 참조): P0-1 신뢰 품질(B1·B2·B3) / P0-2 운영 루프 UI(반입 센터·결정 왕복) /
> P0-3 URL=상태+스케일 / P1 사용성·접근성(axe 게이트) / P2 마감(다크모드·Ctrl+K).
>
> **후속 후보(미착수, 승인 필요)**: 목록 스켈레톤·가상화(500건+), 공통
> StatusBadge/AsyncSection 리팩터(badge 맵 7종·무언 실패 정리), 1280px 분기·프린트
> 스타일, docs/ 스크린샷 재캡처, Stage 13 트랙 A 또는 Stage 14 잔여(인증/배포/캐시).

### 직전 완료 — 사내 실운영 준비 Phase 0~4 (2026-07-11)

> **방향 재정의 (2026-07-11, 사용자)**: 목표는 워크숍 데모가 아니라 **사내 실운영
> (operational ontology) + JIRA/Confluence 연동**. 사외에서는 fixture로 구현·검증
> 가능한 것을 최대한 앞당긴다 — 백로그 P4("CI 얇게 먼저 + 반입 표면 당기기") 채택.
>
> **완료 (상세: CHANGELOG, 설계: 11/12_*.md)**:
> - **Phase 0 얇은 CI** — backend/frontend/contracts 3 job (`.github/workflows/ci.yml`).
> - **Phase 1 반입 표면 확대(Stage 15 사외 선행분)** — 매핑 4종(issues/tests/
>   development_events/evidence_catalog, 중첩·bool·root_causes) + 샘플 CSV + 왕복·파생 뷰
>   통합 테스트. 계약 정밀화(L8): `related_ip_ids` 명시 링크 우선, `Issue.severity`.
> - **Phase 2 B3b 결정 재진입** — 결정 CSV(템플릿 v2, 양쪽 계약 테스트) → `decisions`
>   매핑 → Decision. traceability 시작 시 스냅샷 제거(반입 객체 즉시 연결 조회).
> - **Phase 3 JIRA/Confluence 커넥터 사외 선행분** — Protocol+Fake+설정 YAML 매핑,
>   `ingest_rows(origin=integrated)` 경유, `sync-jira/sync-confluence` CLI(dry-run).
>   사내 후속: 보안 승인·실 자격증명·실 스키마 값·주기 실행.
> - **Phase 4 U1 값 한국어화 + 위험 지도 근거 태세** — `VALUE_LABELS` 17 도메인 +
>   fixture 전 값 커버리지 게이트 + `useValueLabels`, 시나리오 행 태세 배지.
>
> **다음 후보 (착수는 사용자 승인)**:
> - Stage 13 트랙 A(가설 판정 모드 + baseline — 사내 검증 세션 준비) 또는
>   Stage 16 잔여 U2~U9(URL=상태·접근성·로딩 규약·스케일).
> - Stage 14 잔여(인증/배포/LLM 캐시 — 사내 표준 필요), P3 Path 객체(대형, 실데이터 검증 후).
> - 사내 반입 리허설: `sync-jira --execute`(PostgreSQL) + curation 워크플로(05 Stage 15 §3).

## 다음 단계 기준 문서

**`internal_docs/design/05_long_term_improvement_plan.md`** — Stage 13~19 상세 실행 계약
(현재 상태 스냅샷/관찰된 한계 L1~L12/단계별 In·Out-scope/수용 기준/실행 규약 포함,
다른 구현 주체가 이 문서만으로 착수 가능하도록 작성됨).

순서: Stage 13(워크숍 검증+교정 루프) → 14(CI·인증·배포·캐시) → 15(실데이터 반입 확대)
→ **16(UI 정밀 감사·개편 — 상세: `internal_docs/design/06_stage16_ui_overhaul.md`)**
→ 17(운영 파일럿+효과 지표) → 18(시맨틱 검색+Ask 고도화) → 19(JIRA/Confluence 커넥터)
→ 20+(타 도메인 확장). 각 Stage 착수는 사용자 승인 필요.

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조: `E:\56_Codex_SoC_Operational_Ontology` (수정 금지)

## 로컬 실행 (이 머신 포트 규칙 — CLAUDE.md §0-a)

```bash
uv run uvicorn backend.api.app:create_app --factory --port 8155
cd frontend && VITE_API_TARGET=http://127.0.0.1:8155 npx vite --host 127.0.0.1 --port 5275 --strictPort
```

8000/5173/5174/8100 등 다른 포트는 다른 세션 소유 — 절대 접근 금지.

---

## Stage 1~12 완료 기준선 (2026-07-06)

```text
기반 (Stage 1~7): 온톨로지 v1.0 계약 + 한국어 glossary / PostgreSQL 계층 /
  결정론 서비스 + FastAPI / 한국어 frontend / LLM 3단 체인 + validator / Excel·CSV 반입
코크핏 (Stage 8~12, 원점 목표 복원):
  8  위험 지도 홈 — 정성 등급 룰(근거 ref 필수, 수치 점수 금지) + UI 공통 원칙
  9  변경 영향 — 그래프 순회 4분면 + 역할별 검토 체크리스트 + 복사 내보내기
  10 이슈 분석 — Test/RootCause 온톨로지 확장 + §7 archetype 이슈 32/테스트 30 +
     RCA 7단 체인("검증 없는 close" 빨간 경고) + 56 재동기화(_58 오버레이 로더)
  11 Ask SoC — 키워드 검색 + LLM 인용 답변(검증 관문, 미가용 시 결정론) + 프리셋 5종
  12 데모 스토리 4장면 + TAT 앱 내 로그 + 측정 기준표 + 워크숍 가설 자료
검증: backend 127 테스트 / frontend 21 테스트 / ruff / mypy / lint / validate-data 오류 0
docs/ = 사용자 UI 가이드(GitHub Pages 소스, 6문서+스크린샷) / internal_docs/ = 설계·검증 자료
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
uv run python -m backend.cli.main validate-data
cd frontend && npm run build && npm run test && npm run lint
```

## Scope Lock

새 Stage는 사용자 승인 없이 착수하지 않는다. 착수 시 이 파일을 해당 Stage scope로 갱신한다.
