# CURRENT_TASK.md

## 활성 Stage

**Stage 9 — 변경 영향 (Change Impact)** (준비 완료 — **사용자 승인 대기, 착수 금지**)

> 새 세션 시작 시 이 파일과 함께 반드시 읽을 것:
> 1. `docs/design/03_course_correction.md` §4.2 — **교정 설계 (Stage 8~12의 기준 문서)**
> 2. `docs/design/02_implementation_roadmap.md` — Stage 9 수용 기준
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

## Stage 1~8 완료 기준선 (기반 — 유지)

```text
온톨로지 v1.0 계약 8모듈 + 한국어 glossary + fixture 465건 (무결성 오류 0)
PostgreSQL 계층 / 결정론 서비스 + FastAPI / 한국어 frontend / LLM 3단 체인 + validator / Excel·CSV 반입
Stage 8 (2026-07-05): 위험 지도 홈 — backend/services/risk.py 정성 등급 룰(등급마다 근거 ref,
  수치 점수 금지), GET /api/v1/risk/heatmap, GET /api/v1/meta/labels,
  코크핏 내비(위험 지도 활성 / 변경 영향·이슈 분석·Ask SoC 비활성 placeholder),
  UI 공통 원칙(ID 숨김 useLabels / 색 의미 통일 / CollapsibleList 접기)
backend 87 테스트 / frontend 9 테스트 / ruff / mypy / lint 통과
```

### 알려진 문제 (승계)

- `test_converter_roundtrip` 1건 실패 — 56 참조 데이터가 2026-07-05에 갱신되어
  (variants+1건, Variant `source_basis` 필드 등) Stage 1 변환 스냅샷과 드리프트.
  재동기화는 온톨로지 계약+fixture 변경(변경 규율 6단계) → **사용자 결정 필요**.
  Stage 10 fixture 보강과 묶어 처리하는 것도 후보.

---

## Stage 9 목표

"이 IP/spec을 바꾸면 어디에 영향이 가나?"에 결정론으로 답하는 변경 영향 화면.
TAT 효과 1위 유스케이스. 상세 설계: `03_course_correction.md` §4.2.

## 기준 가정

- 온톨로지 저장 계약 변경 없음 — 기존 데이터 그래프(scenario_ip_requirements /
  ip_knobs / ip_dependency_rules / issues / events) 순회만으로 계산.
- LLM은 결정론 결과의 문장화/요약에만 선택 사용 (기존 체인 + validator 재사용).
- 수치 점수·자동 결정·쓰기 API 금지 유지.

## In-scope

```text
backend/services/change_impact.py — 그래프 순회 엔진 + 단위 테스트:
  선택 IP → scenario_ip_requirements → 영향 시나리오 → primary_kpis
  선택 IP → ip_dependency_rules → 연쇄 IP (조건 표시)
  선택 knob → ip_knobs.affected_kpis / related_scenarios / 방향성(전력·지연·대역폭·리스크)
  영향 시나리오 → 과거 이슈/이벤트 (같은 IP·KPI 조합) → 유사 사례
  영향 도메인 → 역할 책임 경계(CLAUDE.md §2.2) → 검토 관점 체크리스트
GET /api/v1/change-impact (IP/knob 파라미터)
frontend 변경 영향 화면: 내비 활성화, IP 선택 → knob/capability/모드 선택 → [분석 실행]
  → 4분면 출력(영향 시나리오/영향 KPI/연쇄 IP/역할별 검토 체크리스트) + 과거 유사 사례
  → 체크리스트 텍스트 복사 내보내기
openapi 재생성 + 타입 생성 + 테스트 (backend/frontend)
```

## Out-of-scope (Stage 9에서 구현 금지)

```text
RCA·Test 온톨로지 확장 (Stage 10) / Ask SoC 질의 (Stage 11) / 데모 스토리 모드 (Stage 12)
자유 서술 입력의 LLM 해석 (knob/capability 선택 입력만 — 자유 서술은 Stage 11 검토)
수치 영향 점수, owner 할당, 쓰기 API, JIRA/임베딩 (Stage 13+)
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
uv run python -m backend.cli.main validate-data
cd frontend && npm run build && npm run test && npm run lint
```

## 수용 기준 (roadmap Stage 9)

- [ ] ISP knob 변경 예시로 4분면 출력 완결 (영향 시나리오/KPI/연쇄 IP/검토 체크리스트)
- [ ] 체크리스트가 역할 책임 경계와 일치 (HW/SW는 feedback, Management는 트레이드오프 등)
- [ ] 모든 영향 항목이 근거 객체 ref 동반 (traceability drill-down 연결)
- [ ] 등급/영향 판정이 결정론 테스트로 고정
- [ ] backend/frontend 전체 회귀 통과

## Scope Lock

Stage 10 이후의 어떤 동작도 구현하지 않는다. Stage 9 완료 시: changelog 갱신 → commit/push →
Stage 10 scope lock 갱신 후 정지 (사용자 승인 후 진행).
