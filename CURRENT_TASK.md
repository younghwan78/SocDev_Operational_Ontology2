# CURRENT_TASK.md

## 활성 Stage

**활성 Stage 없음 — UI G1~G3(변경 영향 전파 지도) 완료 (2026-07-11).**

> G2 문장형 질의 빌더+요약 스트립 / G1 영향 전파 지도(순수 SVG, 간선=근거) /
> G3 노드→근거 패널(`?node=`)·화면 재편·docs 개정. 같은 날 W1~W3(유동 폭/열
> 카테고리/코크핏 정체성/스플리터) 완료. 상세: CHANGELOG.
>
> **후속 후보(미착수, 승인 필요)**: 공통 StatusBadge/AsyncSection 리팩터(badge 맵
> 중복·보조 쿼리 무언 실패), 목록 스켈레톤·가상화(500건+), 1280px 분기·프린트,
> docs/ 스크린샷 재캡처(변경 영향·위험 지도 — 화면이 크게 바뀜), Stage 13 트랙 A
> 또는 Stage 14 잔여(인증/배포/캐시).

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
