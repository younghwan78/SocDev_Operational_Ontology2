# CURRENT_TASK.md

## 활성 Stage

**없음 — Stage 8~12 교정 계획 완료 (2026-07-06). 다음 단계는 사용자 결정 대기.**

> 원점 목표 복원이 완료됐다: 5대 질문 코크핏(위험 지도/변경 영향/이슈 분석/Ask SoC/
> 시나리오 상세) + 데모 스토리 + TAT 측정 체계. 진행 이력은 `CHANGELOG.md` 참조.

## 다음 후보 (착수 전 사용자 승인 필요)

1. **사내 검증 워크숍 실행** — `internal_docs/validation/` 자료로 실무 리더 검증
   (TAT 측정 + fixture 가설 판정) → 교정 백로그 도출. **권장 다음 단계.**
2. **Stage 13+ (이연 계획)** — `internal_docs/design/02_implementation_roadmap.md` 참조:
   JIRA/Confluence read-only 커넥터(보안 승인 선행), 사내 임베딩+pgvector 한국어 시맨틱
   검색(키워드 retriever 대체), 운영 파일럿(실무 리더 1~2명 주간 사용).
   원점 문서 원칙: "ingestion 자동화보다 연결 모델 검증이 먼저" — 1번 이후 착수 권장.
3. 워크숍 피드백 기반 교정 (위험 룰 가중/원인 유형/archetype 수정 — 변경 규율 6단계).

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
