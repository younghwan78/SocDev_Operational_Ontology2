# CURRENT_TASK.md

## 활성 Stage

**Stage 3 — 결정론 서비스 + Read-only API** (진행 중 — 연속 Stage 진행 사전 승인 세션)

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## Stage 1~2 완료 기준선

```text
온톨로지 v1.0 계약 8모듈 + 한국어 glossary + JSON Schema 자동 export
56 fixture 전량 변환 465건 (무결성 오류 0)
PostgreSQL 계층: 마이그레이션 / 멱등 시드 / PostgresRepository (in-memory 패리티 검증 완료)
RepositoryProtocol — 저장소 교체 가능
CLI: validate-data, db-init, db-seed, db-check
테스트 24건 + DSN 게이트 6건 / ruff / mypy 통과
```

테스트 DB: `postgresql://warroom:warroom@localhost:55432/soc58_test`
(56의 warroom-pg 컨테이너 공유 — 56의 warroom DB는 절대 접근 금지)

---

## Stage 3 목표

실무 리더의 시나리오 분석에 필요한 결정론 서비스와 read-only API를 제공한다.
LLM 없이 완결되는 조회 표면. 상세: `docs/design/02_implementation_roadmap.md` Stage 3 절.

## 기준 가정

- 응답은 RepositoryProtocol 위에서 결정론적으로 계산된다 (메모리/DB 교체 무관 동일).
- 파생 뷰(포트폴리오/리뷰)는 저장하지 않고 서비스 계층에서 계산한다.
- 응답 모델에는 glossary 기반 한국어 라벨 메타데이터를 동봉한다.
- openapi.json은 커밋한다 — Stage 4 frontend 타입 생성 소스.

## In-scope

```text
backend/resolve/: relation resolver (양방향), traceability 조립
backend/services/: scenario_analysis(시나리오 종합/근거 공백/타임라인), portfolio, review
backend/api/: FastAPI GET 엔드포인트 + openapi.json export
httpx TestClient 기반 API 테스트, 저장소 패리티 테스트
```

## Out-of-scope (Stage 3에서 구현 금지)

```text
POST 엔드포인트 (advisory 포함)
LLM provider / 프롬프트
frontend
임베딩 / semantic 검색
쓰기 API / 데이터 수정
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider
uv run ruff check backend tests tools
uv run mypy
uv run python -m backend.cli.main validate-data
```

## Scope Lock

Stage 4 이후의 어떤 동작도 구현하지 않는다. Stage 3 완료 시: changelog 갱신 → commit/push → Stage 4 scope lock 갱신 후 계속 진행.
