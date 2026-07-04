# CURRENT_TASK.md

## 활성 Stage

**Stage 8 — 홈 개편 + 위험 지도 (Risk Heatmap)** (사용자 승인 완료 2026-07-05 — 착수 대기)

> 새 세션 시작 시 이 파일과 함께 반드시 읽을 것:
> 1. `docs/design/03_course_correction.md` — **교정 설계 (Stage 8~12의 기준 문서)**
> 2. `docs/design/02_implementation_roadmap.md` — Stage 8~12 수용 기준
> 3. 원점 문서(read-only): `D:\YHJOO\100_SoC_Operational_Ontology\01_Brainstorming\26.06.18 SoC ontology (ChatGPT).md`

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

## Stage 1~7 완료 기준선 (기반 — 유지)

```text
온톨로지 v1.0 계약 8모듈 + 한국어 glossary + fixture 465건 (무결성 오류 0)
PostgreSQL 계층 (마이그레이션 3개/시드/repository 패리티) — 테스트 DB: soc58_test@warroom-pg:55432
결정론 서비스(시나리오 분석·포트폴리오·리뷰·traceability) + FastAPI + openapi.json
한국어 frontend 4화면 + traceability drill-down 패턴
LLM 3단 체인(claude_cli→openai_compat→결정론) + evidence-grounded validator + 감사 기록
Excel/CSV 반입 (한국어 헤더 매핑, 배치 rollback)
backend 82 테스트 / frontend 5 테스트 / ruff / mypy / lint 전부 통과
```

---

## Stage 8 목표

UI를 "질문이 곧 메뉴인 코크핏"으로 재편하는 첫 단계. 홈을 **위험 지도(Risk Heatmap)**로
바꾸고 UI 공통 원칙을 도입한다. 상세 설계: `03_course_correction.md` §4.1, §3.

## 기준 가정

- Stage 1~7 계약·서비스는 기반으로 재사용한다. 온톨로지 저장 계약 변경 없음(위험 등급은 파생 뷰).
- **Guardrail 조정(승인됨)**: 수치 리스크 점수는 여전히 금지. 단 **정성 위험 등급(높음/중간/낮음)
  + 판정 근거 목록 명시**는 허용 — CLAUDE.md §6.3에 반영됨.
- 위험 판정은 결정론 룰: 근거 공백 수·종류(확신도 차단 가중), 이슈 심각도, schedule_signal,
  P1 요청 상태, 과거 유사 패턴. 모든 등급은 근거 객체 ref 목록을 동반한다.
- 기존 화면(포트폴리오 lane/리뷰/근거 탐색/시나리오 상세)은 삭제하지 않고 하위 층으로 재배치.

## In-scope

```text
backend/services/risk.py — 시나리오×IP 정성 위험 판정 룰 + 단위 테스트
GET /api/v1/risk/heatmap — 프로젝트 필터, 셀별 등급+근거 refs
frontend 홈 개편:
  - 내비: 위험 지도 / 변경 영향(비활성) / 이슈 분석(비활성) / Ask SoC(비활성) / 기존 화면(하위 메뉴)
  - heatmap (행=시나리오, 열=주요 IP, 셀=●◐○ 등급, 프로젝트 탭 U/V/W)
  - 셀/행 클릭 → 근거 패널 → 기존 시나리오 상세로 drill-down
  - "이번 주 주목" 3~5건 (P1 요청·새 공백·확신도 차단 우선)
UI 공통 원칙 적용: 내부 ID 숨김(hover/상세만), 색 의미 통일(빨강=위험/노랑=주의/초록=정상), 접기 기본
openapi 재생성 + 타입 생성 + 테스트 (backend/frontend)
```

## Out-of-scope (Stage 8에서 구현 금지)

```text
변경 영향 엔진 (Stage 9) / RCA·Test 온톨로지 확장 (Stage 10) / Ask SoC 질의 (Stage 11)
수치 리스크 점수, owner 할당, 결정 자동화, 쓰기 API
JIRA/임베딩 (Stage 13+)
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
uv run python -m backend.cli.main validate-data
cd frontend && npm run build && npm run test && npm run lint
```

## 수용 기준

- [ ] 홈 진입 10초 내 위험 시나리오 식별 가능 (heatmap이 첫 화면)
- [ ] 모든 등급이 근거 패널로 drill-down (근거 없는 등급 없음)
- [ ] 등급 판정이 결정론 테스트로 고정 (동일 fixture → 동일 등급)
- [ ] 화면에 내부 ID 직접 노출 없음 (hover/상세 제외 — 기존 가드 테스트 확장)
- [ ] 기존 4화면은 하위 메뉴에서 계속 접근 가능
- [ ] backend/frontend 전체 회귀 통과

## Scope Lock

Stage 9 이후의 어떤 동작도 구현하지 않는다. Stage 8 완료 시: changelog 갱신 → commit/push →
Stage 9 scope lock 갱신 후 정지 (사용자 승인 후 진행).
