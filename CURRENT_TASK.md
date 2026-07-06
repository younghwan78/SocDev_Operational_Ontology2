# CURRENT_TASK.md

## 활성 Stage

**없음 — Stage 8~12 교정 계획 완료 (2026-07-06). 다음 단계는 사용자 결정 대기.**

> 원점 목표 복원이 완료됐다: 5대 질문 코크핏(위험 지도/변경 영향/이슈 분석/Ask SoC/
> 시나리오 상세) + 데모 스토리 + TAT 측정 체계. 진행 이력은 `CHANGELOG.md` 참조.

## 다음 단계 기준 문서

**`internal_docs/design/05_long_term_improvement_plan.md`** — Stage 13~19 상세 실행 계약
(현재 상태 스냅샷/관찰된 한계 L1~L12/단계별 In·Out-scope/수용 기준/실행 규약 포함,
다른 구현 주체가 이 문서만으로 착수 가능하도록 작성됨).

순서: Stage 13(워크숍 검증+교정 루프) → 14(CI·인증·배포·캐시) → 15(실데이터 반입 확대)
→ 16(운영 파일럿+효과 지표) → 17(시맨틱 검색+Ask 고도화) → 18(JIRA/Confluence 커넥터)
→ 19+(타 도메인 확장). 각 Stage 착수는 사용자 승인 필요.

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
