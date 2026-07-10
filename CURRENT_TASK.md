# CURRENT_TASK.md

## 활성 Stage

**활성 Stage 없음 — 사내 실운영 준비 Phase 0~1 완료 (2026-07-11). Phase 2 승인 대기.**

> **방향 재정의 (2026-07-11, 사용자)**: 목표는 워크숍 데모가 아니라 **사내 실운영
> (operational ontology) + JIRA/Confluence 연동**. 사외에서는 fixture로 구현·검증
> 가능한 것을 최대한 앞당긴다 — 백로그 P4("CI 얇게 먼저 + 반입 표면 당기기") 채택.
>
> **완료 (CHANGELOG 참조)**:
> - **Phase 0 얇은 CI** — backend/frontend/contracts 3 job (`.github/workflows/ci.yml`).
> - **Phase 1 반입 표면 확대(Stage 15 사외 선행분)** — 매핑 4종(issues/tests/
>   development_events/evidence_catalog, 중첩·bool·root_causes 지원) + 샘플 CSV 4종 +
>   왕복·파생 뷰 통합 테스트. 계약 정밀화(L8): `DevelopmentEvent.related_ip_ids`
>   (명시 링크 우선), `Issue.severity`(low/info→중간). E2E(실서버 8155) 검증 완료.
>
> **다음 로드맵 (각 Phase 착수는 사용자 승인 — `08_bridge_followups.md` §4)**:
> - **Phase 2 = B3b 결정 재진입**: 설계 `11_decision_reentry.md` 선행 → decisions 매핑 →
>   리뷰 팩 CSV 왕복. `Decision.event_id` 필수 처리 설계 포함. **쓰기 경로라 신중.**
> - **Phase 3 = JIRA/Confluence 커넥터 사외 선행분**: Protocol+Fake+설정 YAML 매핑+
>   ingest 경유(origin=integrated)+`sync-jira --dry-run`. 보안 승인 등은 사내 후속.
> - **Phase 4 = U1 값 도메인 한국어화 + 위험 지도 근거 태세 배지.**

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
