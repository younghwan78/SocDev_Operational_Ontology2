# CURRENT_TASK.md

## 활성 Stage

**Stage 6 — 나머지 화면: 포트폴리오 현황 · 리뷰 센터 · 근거 탐색** (진행 중 — 연속 Stage 진행 사전 승인 세션)

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## Stage 1~5 완료 기준선

```text
온톨로지 v1.0 계약 + glossary + fixture 465건 + PostgreSQL 계층
결정론 서비스 + FastAPI (GET 13개 + advisory POST/GET) + openapi.json
한국어 frontend: 시나리오 목록/상세 5탭 (개요·타임라인·이벤트·조언·추적)
LLM 3단 체인 (claude_cli → openai_compat → 결정론) + validator + 감사 기록
실 E2E: Claude CLI 출력이 validator에 거부→결정론 fallback 동작 확인
backend 71 테스트 / frontend 4 테스트 / ruff / mypy / lint 통과
```

---

## Stage 6 목표

4화면 체계를 완성한다: ① 포트폴리오 현황, ③ 리뷰 센터, ④ 근거 탐색.
상세: `docs/design/02_implementation_roadmap.md` Stage 6 절.

## 기준 가정

- Stage 3의 결정론 서비스(포트폴리오/리뷰)와 기존 GET API를 소비한다 — 새 저장 계약 없음.
- 모든 화면은 시나리오 상세의 traceability 패턴과 스타일 시스템을 재사용한다.
- 화면 간 이동은 URL 기반 (공유/북마크 가능).
- 필요한 신규 GET 엔드포인트는 read-only 원칙 내에서만 추가한다.

## In-scope

```text
① 포트폴리오 현황 (/portfolio): U/V/W 요약, 주의 lane 6종, 시나리오×프로젝트 매트릭스
   → 셀/항목 클릭 시 시나리오 상세로 이동
③ 리뷰 센터 (/review): 주간 인덱스 → 주차 선택 → 이벤트/활동/요청 스냅샷
④ 근거 탐색 (/evidence): 근거 카탈로그 목록/필터(가용성·프로젝트), traceability drill-down
헤더 내비게이션 4화면 체계 완성
필요 시 evidence 목록 GET API 추가
컴포넌트 테스트
```

## Out-of-scope (Stage 6에서 구현 금지)

```text
Excel/CSV 반입 (Stage 7)
임베딩 검색 / JIRA/Confluence 커넥터 (Stage 8+)
쓰기 API, 수치 스코어링, 결정 자동화
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
cd frontend && npm run build && npm run test && npm run lint
```

## Scope Lock

Stage 7 이후의 어떤 동작도 구현하지 않는다. Stage 6 완료 시: changelog 갱신 → commit/push → Stage 7 scope lock 갱신 후 계속 진행.
