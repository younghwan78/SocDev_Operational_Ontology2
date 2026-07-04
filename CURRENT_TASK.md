# CURRENT_TASK.md

## 활성 Stage

**Stage 5 — LLM Provider Chain + Scenario Advisory** (진행 중 — 연속 Stage 진행 사전 승인 세션)

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## Stage 1~4 완료 기준선

```text
온톨로지 v1.0 계약 + glossary + fixture 465건 + PostgreSQL 계층 (패리티 검증)
결정론 서비스 + FastAPI 13 GET 엔드포인트 + openapi.json
한국어 frontend: 시나리오 목록/상세(개요·타임라인·이벤트·추적), traceability 패널
backend 53 테스트 / frontend 4 테스트 / ruff / mypy / lint 통과
```

---

## Stage 5 목표

Claude CLI(1차) → 사내 on-prem OpenAI 호환(2차) → 결정론 코어(3차) 체인으로
role agent 조언을 생성하고, evidence-grounded validator와 감사 기록으로 통제한다.
상세: `docs/design/02_implementation_roadmap.md` Stage 5 절.

## 기준 가정

- 모든 provider 출력은 RoleOutput 계약으로 파싱되고 validator를 통과해야 채택된다.
- validator는 provider와 무관하게 항상 실행된다 — supporting_basis 없는 주장 거부,
  근거 약하면 high confidence 금지, 일반론 거부.
- 테스트는 LLM 실호출 없이 통과한다 (mock provider 계약 테스트).
- `allow_external_llm` 정책 스위치: false면 Claude CLI(외부)를 건너뛰고 on-prem부터.
- 감사 기록(agent_run): provider/모델/입력 해시/검증 결과/소요시간 저장.
- 조언은 한국어로 출력한다.

## In-scope

```text
backend/agents/providers/: LLMProvider 프로토콜 + claude_cli / openai_compat / deterministic
backend/agents/runner.py: 컨텍스트 조립 → role 프롬프트 → 체인 실행 → RoleOutput 파싱
backend/agents/validators.py: evidence-grounded 검증 관문
감사 기록 저장 (메모리/DB)
POST /api/v1/scenarios/{id}/advisory + GET (기존 결과 조회)
frontend: 시나리오 상세에 조언 탭 추가 (provider/확신도 표시)
provider 계약/체인 fallback/validator 테스트
```

## Out-of-scope (Stage 5에서 구현 금지)

```text
멀티 에이전트 자율 토론
수치 리스크 스코어 자동 산정
임베딩 retrieval (키워드 후보로 시작)
포트폴리오/리뷰 센터/근거 탐색 화면 (Stage 6)
Excel 반입 (Stage 7)
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
cd frontend && npm run build && npm run test && npm run lint
```

## Scope Lock

Stage 6 이후의 어떤 동작도 구현하지 않는다. Stage 5 완료 시: changelog 갱신 → commit/push → Stage 6 scope lock 갱신 후 계속 진행.
