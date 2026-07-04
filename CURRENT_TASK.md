# CURRENT_TASK.md

## 활성 Stage

**Stage 7 — Excel/CSV 실데이터 반입 파일럿** (준비됨 — 사용자 승인 대기)

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## Stage 1~6 완료 기준선

```text
Stage 1: 온톨로지 v1.0 계약 8모듈 + 한국어 glossary + 56 fixture 465건 변환 (무결성 오류 0)
Stage 2: PostgreSQL 계층 (마이그레이션/멱등 시드/repository, 실DB 패리티 검증)
Stage 3: 결정론 서비스 (시나리오 분석/포트폴리오/리뷰/traceability) + read-only API
Stage 4: 한국어 frontend — 시나리오 목록/상세 5탭 + traceability drill-down 패턴
Stage 5: LLM 3단 체인 (claude_cli→openai_compat→결정론) + validator + 감사 기록 + 조언 탭
        실 E2E: validator가 부적합 LLM 출력 거부 → 프롬프트 강화 후 claude_cli 통과
Stage 6: 4화면 체계 완성 — 포트폴리오 현황 / 리뷰 센터 / 근거 탐색

검증: backend 73 테스트 (+PG 통합) / frontend 5 테스트 / ruff / mypy / lint 전부 통과
테스트 DB: postgresql://warroom:warroom@localhost:55432/soc58_test (56의 warroom DB 접근 금지)
```

---

## Stage 7 목표

첫 실데이터를 Excel/CSV로 반입해 synthetic과 병존시키고, 반입 워크플로를 검증한다.
상세: `docs/design/02_implementation_roadmap.md` Stage 7 절.

## In-scope (승인 후)

```text
backend/ingest/excel_csv.py: 열→온톨로지 필드 매핑 정의 기반 반입, 실패 행 한국어 보고서
우선 대상: 프로젝트/마일스톤, KPI 관측치/측정 근거
POST /api/v1/ingest/excel + CLI ingest-excel
UI: source_origin 뱃지(가상/반입/연동) 전 화면 표시, 반입 이력 조회
반입 단위 rollback (개별 객체 수정 API 없음 유지)
```

## Out-of-scope

```text
JIRA/Confluence 커넥터, 임베딩 검색 (Stage 8+)
개별 객체 수정/삭제 API
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
cd frontend && npm run build && npm run test && npm run lint
```

## Scope Lock

Stage 7은 사용자가 명시적으로 승인해야 시작한다 (연속 진행 세션은 Stage 6에서 종료됨).
