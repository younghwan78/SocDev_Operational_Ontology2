# CURRENT_TASK.md

## 활성 Stage

**Stage 10 — 이슈 분석: RCA 체인 + Test 온톨로지 확장** (준비 완료 — **사용자 승인 대기, 착수 금지**)

> 새 세션 시작 시 이 파일과 함께 반드시 읽을 것:
> 1. `docs/design/03_course_correction.md` §4.3 — **교정 설계 (Stage 8~12의 기준 문서)**
> 2. `docs/design/02_implementation_roadmap.md` — Stage 10 수용 기준
> 3. 원점 문서(read-only, 특히 §7 issue archetype): `D:\YHJOO\100_SoC_Operational_Ontology\01_Brainstorming\26.06.18 SoC ontology (ChatGPT).md`

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

## Stage 1~9 완료 기준선 (기반 — 유지)

```text
온톨로지 v1.0 계약 8모듈 + 한국어 glossary + fixture 465건 (무결성 오류 0)
PostgreSQL 계층 / 결정론 서비스 + FastAPI / 한국어 frontend / LLM 3단 체인 + validator / Excel·CSV 반입
Stage 8 (2026-07-05): 위험 지도 홈 (risk.py 정성 등급 룰 + heatmap API + 코크핏 내비 + UI 공통 원칙)
Stage 9 (2026-07-05): 변경 영향 (change_impact.py 그래프 순회 + 4분면 화면 + 역할별 체크리스트
  + 체크리스트 복사, services/common.py BasisItem 공용화)
backend 103 테스트 / frontend 12 테스트 / ruff / mypy / lint 통과
```

### 알려진 문제 (승계 — Stage 10에서 처리 후보)

- `test_converter_roundtrip` 1건 실패 — 56 참조 데이터가 2026-07-05에 갱신되어
  (variants 5→6건, Variant `source_basis` 필드, scenarios/relations/measurement_requirements 변경)
  Stage 1 변환 스냅샷과 드리프트. **Stage 10의 온톨로지 확장 + fixture 보강과 묶어
  변경 규율 6단계로 재동기화하는 것을 권장** (사용자 확인 후).

---

## Stage 10 목표

"이 이슈의 원인은? 정말 해결됐나? 재발하나?"에 답하는 RCA 그래프 화면.
**"검증 테스트 없음"이 빨갛게 뜨는 것이 이 화면의 존재 이유** — close됐지만 검증되지 않은
이슈를 드러낸다. 상세 설계: `03_course_correction.md` §4.3.

## In-scope

```text
온톨로지 확장 (event 모듈) — 변경 규율 6단계 (설계→모델→schema→fixture→테스트→changelog):
  Test: id, scenario/issue 연결, test_type(regression/scenario/CTS·VTS/power), 결과, evidence 연결
  RootCause 구조화: 유형 enum 6종 — architecture_miss / spec_ambiguity / verification_gap /
    power_model_error / sw_workaround_dependency / customer_scenario_mismatch
  Issue 확장: root_causes(구조화), fix_type, workaround, verifying_test_ids,
    residual_risk, reusable_lesson
fixture 보강: 원점 문서 §7 issue archetype(ISP/DPU/Codec/Audio/DDR·NoC 계열) 기반
  이슈 30~50건 + 테스트 30건 + RCA 완결 체인 사례 (synthetic)
RCA 그래프 화면 (내비 '이슈 분석' 활성화): 이슈 선택 → 세로 흐름
  증상 → 영향 시나리오/IP → 원인 후보(유형 분류) → 조치(fix/workaround)
  → 검증 테스트 → 잔존 리스크 → 재사용 교훈
  각 노드에 근거 뱃지: 있음=초록 / 없음=빨강 / 미검증=노랑
API + openapi/schema 재생성 + 타입 생성 + 테스트 (backend/frontend)
```

## Out-of-scope (Stage 10에서 구현 금지)

```text
Ask SoC 질의 (Stage 11) / 데모 스토리 모드·TAT 측정 (Stage 12)
RCA 자동 추론(LLM 원인 판정) — 원인 후보는 데이터에 기록된 것만 표시
수치 점수, owner 할당, 쓰기 API(반입 제외), JIRA/임베딩 (Stage 13+)
```

## 필수 검증 명령

```bash
uv run pytest -p no:cacheprovider && uv run ruff check backend tests tools && uv run mypy
uv run python -m backend.cli.main validate-data
cd frontend && npm run build && npm run test && npm run lint
```

## 수용 기준 (roadmap Stage 10)

- [ ] "검증 테스트 없는 close 이슈"가 화면에서 시각적으로 드러남 (빨간 뱃지)
- [ ] RCA 완결 체인 사례 1건 이상이 증상→교훈까지 근거와 함께 표시
- [ ] 온톨로지 변경이 변경 규율 6단계를 준수 (schema/openapi 재생성 포함)
- [ ] fixture 보강 후 validate-data 무결성 오류 0건 유지
- [ ] backend/frontend 전체 회귀 통과

## Scope Lock

Stage 11 이후의 어떤 동작도 구현하지 않는다. Stage 10 완료 시: changelog 갱신 → commit/push →
Stage 11 scope lock 갱신 후 정지 (사용자 승인 후 진행).
