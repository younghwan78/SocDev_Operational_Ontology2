# CURRENT_TASK.md

## 활성 Stage

**Stage 8 — 사내 연동 고도화** (미착수 — 사용자 승인 대기)

연속 Stage 진행 사전 승인 세션(약 4시간)은 Stage 7 완료로 종료되었다.

## 작업 디렉토리

```text
E:\58_Claude_SoC_Operational_Ontology
```

Read-only 참조 디렉토리 (수정 금지):

```text
E:\56_Codex_SoC_Operational_Ontology
```

---

## Stage 1~7 완료 기준선

```text
Stage 1: 온톨로지 v1.0 계약 8모듈 + 한국어 glossary + 56 fixture 465건 (무결성 오류 0)
Stage 2: PostgreSQL 계층 (마이그레이션 3개 / 멱등 시드 / repository 패리티)
Stage 3: 결정론 서비스 (시나리오 분석·포트폴리오·리뷰·traceability) + read-only API
Stage 4: 한국어 frontend — 시나리오 목록/상세 + traceability drill-down 패턴
Stage 5: LLM 3단 체인 (claude_cli→openai_compat→결정론) + validator + 감사 기록 + 조언 탭
        실 E2E: 부적합 출력 거부→fallback, 프롬프트 강화 후 claude_cli 통과 확인
Stage 6: 4화면 완성 — 포트폴리오 현황 / 시나리오 / 리뷰 센터 / 근거 탐색
Stage 7: Excel/CSV 반입 파일럿 — 한국어 헤더 매핑, 실패 행 보고, 배치 rollback,
        source_origin 뱃지, 반입 이력

검증: backend 82 테스트 (+PG 통합) / frontend 5 테스트 / ruff / mypy / lint 전부 통과
테스트 DB: postgresql://warroom:warroom@localhost:55432/soc58_test (56 warroom DB 접근 금지)
```

---

## Stage 8 방향 (상세 계획은 승인 후 수립)

`docs/design/02_implementation_roadmap.md` Stage 8+ 절 참조:

```text
JIRA/Confluence read-only 커넥터 (사내 계정/보안 승인 선행 — 사용자 확인 필요)
사내 임베딩 API + pgvector 한국어 시맨틱 검색 (키워드 retriever 대체)
검색 결과는 supporting_basis 후보로만 진입 (증거 아님 — 56 원칙 유지)
운영 파일럿: 실무 리더 1~2명 주간 사용 → 피드백 루프
반입 매핑 확대 (KPI 관측치, 고객 요구 등)
advisory 비동기 실행 + 결과 캐시 (입력 해시 기준)
```

## Scope Lock

Stage 8은 사용자가 명시적으로 승인하고 범위를 확정해야 시작한다.
그 전에는 이 저장소의 어떤 기능도 추가 구현하지 않는다.
