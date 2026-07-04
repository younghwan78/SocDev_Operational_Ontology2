# 교정 설계: 질문에 답하는 개발 코크핏 (원점 목표 복원)

> 상태: v1.0 확정 (2026-07-05, 사용자 승인)
> 원점 문서: `D:\YHJOO\100_SoC_Operational_Ontology\01_Brainstorming\26.06.18 SoC ontology (ChatGPT).md`
> 이 문서는 Stage 8~12의 설계 기준이다. `02_implementation_roadmap.md`의 Stage 8+ 구간을 대체한다.

## 1. 배경 — 왜 교정하는가

Stage 1~7 구축물은 원점 문서와 대조 검증한 결과 **절반만 정합**했다:

- ✅ 정합: scenario 중심 온톨로지, fixture-first, evidence confidence 모델, "LLM은 온톨로지·근거 다음" 원칙, 시나리오 상세(Scenario Cockpit).
- ❌ 괴리: 원점의 **TAT 단축 유스케이스 4종이 부재** — ① Architecture Query(Ask SoC), ② Change Impact, ③ Milestone Risk Heatmap, ④ Issue RCA Evidence Graph. 그리고 TAT/품질 효과 측정 체계 부재.

괴리의 구조적 원인: 56의 guardrail(수치 점수 금지·결정 자동화 금지·읽기 전용)이 만들 수 있는 것을 "근거 상태 감시"로 좁혔고, 58이 그 편향을 승계했다.

**사용자 확정 방향 (2026-07-05):**

1. Stage 1~7은 기반(foundation)으로 유지한다.
2. 원점 목표(5대 유스케이스) 복원에 우선 초점을 맞춘다.
3. **UI가 설득의 핵심** — 시스템이 좋아도 정보를 찾기 어려우면 의미가 없다. UI 재설계를 포함한다.
4. 기존 roadmap(구 Stage 8: JIRA 커넥터·임베딩)은 고수하지 않는다 → Stage 13+로 이연.

## 2. 목표 재정의

> 데이터 종류별 화면(포트폴리오/시나리오/리뷰/근거)이 아니라,
> **원점 문서의 5대 질문이 곧 메뉴가 되는 코크핏**을 만든다.

| 원점 데모 질문 | 새 최상위 메뉴 | Stage |
|---|---|---|
| 지금 어떤 시나리오/IP가 위험한가? 근거는? | **위험 지도** (Risk Heatmap) | 8 |
| 이 IP/spec을 바꾸면 어디에 영향이 가나? | **변경 영향** (Change Impact) | 9 |
| 이 이슈의 원인은? 정말 해결됐나? 재발하나? | **이슈 분석** (RCA Graph) | 10 |
| 과거 과제에서 비슷한 문제가 있었나? | **Ask SoC** (질의) | 11 |
| 이 시나리오의 전체 상황은? | 시나리오 상세 (기존, 드릴다운 층으로 강등) | — |

기존 화면(포트폴리오 lane/리뷰 센터/근거 탐색)은 삭제하지 않고 **답의 근거를 보여주는 하위 층**으로 재배치한다.

## 3. UI 공통 원칙 (전 화면 적용, Stage 8에서 도입)

1. **질문 → 답 → 근거 3단 구조**: 모든 화면이 이 순서로 정보를 배치한다. 근거 없는 답은 화면에 존재할 수 없다(기존 validator 재사용).
2. **내부 ID 숨김**: `req_uhd60_eis_u_w12` 같은 ID는 hover/상세 패널에서만 노출. 화면에는 한국어 제목.
3. **색 의미 통일**: 빨강=위험/누락, 노랑=주의/부분, 초록=정상/검증됨. lane별 임의 색 폐지.
4. **클릭 3번 규칙**: 어떤 주장이든 3클릭 안에 원본 근거 도달.
5. **접기 기본**: 목록은 상위 3~5건만 펼치고 나머지 접기 (기존 44건 나열 문제 해소).
6. **데모 스토리 모드** (Stage 12): "위험 발견 → 원인 → 변경 영향 → 결정 근거" 4장면 안내 경로.

## 4. 유스케이스 상세 설계

### 4.1 위험 지도 — 새 홈 (Stage 8)

첫 10초에 상황이 보여야 한다. 홈 구성 (위→아래):

1. **Ask SoC 검색창** (Stage 11 전까지는 비활성 placeholder 또는 숨김).
2. **위험 heatmap**: 행=시나리오, 열=주요 IP(ISP/MFC/DPU/ABOX/MIF·NoC), 셀=정성 위험 등급(높음●/중간◐/낮음○), 마지막 열=시나리오 종합 등급. 프로젝트 탭(U/V/W).
3. 셀/행 클릭 → **근거 패널**: 등급 판정에 사용된 근거 목록(공백/이슈/일정 신호/과거 유사 패턴) → 클릭 시 기존 시나리오 상세로.
4. **이번 주 주목 3~5건**: P1 요청·새 근거 공백·확신도 차단 중 우선순위 상위.

**위험 판정 룰 (결정론, `backend/services/risk.py`):**

- 입력(시나리오×IP 단위): 미해결 근거 공백 수와 종류(확신도 차단 가중), 관련 이슈 심각도, 이벤트 schedule_signal(at_risk/delayed), 요청 priority(P1)와 status, 과거 유사 패턴(같은 시나리오·IP 조합의 과거 이슈 존재).
- 출력: `높음/중간/낮음` **정성 등급 + 판정 근거 목록**(각 근거는 원본 객체 ref). 수치 점수는 산출·표시하지 않는다.
- **Guardrail 조정(승인됨)**: "수치 리스크 스코어 금지"는 유지. 단 **정성 위험 등급 + 근거 명시**는 허용한다 — 원점 문서가 요구하는 Milestone Risk Early Warning이 바로 이것이다. CLAUDE.md §6.3 갱신 필요.

### 4.2 변경 영향 (Stage 9) — TAT 효과 1위

**화면**: "무엇을 바꾸나요?" 입력(IP 선택 → 변경 항목: knob/capability/모드 또는 자유 서술) → [분석 실행] → 4분면 출력:

- 영향 시나리오 / 영향 KPI / 연쇄 IP / **필요한 검토 체크리스트(역할 관점)** + 과거 유사 사례.
- 체크리스트 내보내기(텍스트 복사).

**엔진 (결정론, `backend/services/change_impact.py`):** 기존 데이터 그래프 순회 —

```text
선택 IP → scenario_ip_requirements → 영향 시나리오 → primary_kpis
선택 IP → ip_dependency_rules → 연쇄 IP (조건 표시)
선택 knob → ip_knobs.affected_kpis / related_scenarios / 방향성(전력·지연·대역폭·리스크)
영향 시나리오 → 과거 이슈/이벤트 (같은 IP·KPI 조합) → 유사 사례
영향 도메인 → 역할 책임 경계(CLAUDE.md §2.2) → 검토 관점 체크리스트
```

LLM은 결정론 결과의 **문장화/요약에만** 선택적으로 사용(기존 체인 재사용, validator 통과 필수).

### 4.3 이슈 분석 — RCA 그래프 (Stage 10)

**화면**: 이슈 선택 → 세로 흐름 시각화:

```text
증상 → 영향 시나리오/IP → 원인 후보(유형 분류) → 조치(fix/workaround)
  → 검증 테스트 → 잔존 리스크 → 재사용 교훈
```

각 노드에 근거 뱃지(있음=초록/없음=빨강/미검증=노랑). **"검증 테스트 없음"이 빨갛게 뜨는 것이 이 화면의 존재 이유** — "close됐지만 정말 검증됐나?"에 답한다.

**온톨로지 확장 (event 모듈):**

- `Test`: id, scenario/issue 연결, test_type(regression/scenario/CTS·VTS/power), 결과, evidence 연결.
- `RootCause` 구조화: 유형 enum — 원점 문서 분류 승계: `architecture_miss / spec_ambiguity / verification_gap / power_model_error / sw_workaround_dependency / customer_scenario_mismatch`.
- `Issue` 확장: root_causes(구조화), fix_type, workaround, verifying_test_ids, residual_risk, reusable_lesson.

**Fixture 보강**: 현재 이슈 4건으로는 데모 불가. 원점 문서 §7 issue archetype(ISP/DPU/Codec/Audio/DDR·NoC 계열)을 기반으로 이슈 30~50건 + 테스트 30건 + RCA 완결 체인 사례를 synthetic으로 확충한다. 변경 규율(설계→모델→schema→fixture→테스트→changelog) 준수.

### 4.4 Ask SoC (Stage 11)

**화면**: 검색창 + 프리셋 질문 5종(원점 데모 질문). 답변 = 근거 ID 인용 한국어 문단 + 인용 클릭 시 해당 객체로 이동 + 관련 객체 카드.

**흐름**: 질의 → 온톨로지 검색(ObjectIndex + 키워드; semantic chunk는 후보로만) → 관련 객체 수집(결정론) → LLM이 근거 인용 답변 생성(기존 advisory 체인 재사용: claude_cli→on-prem→결정론 요약) → validator 통과분만 표시.

### 4.5 효과 측정 + 데모 패키지 (Stage 12)

- 데모 스토리 모드(4장면 안내).
- TAT 측정: 데모 질문별 "질문→근거 도달 시간" 기록(수동 스톱워치 기준표 + 앱 내 로그), 기존 수작업 대비 비교표.
- 사내 검증 워크숍 자료: 원점 문서 Phase 0D 대응 — "이 관계가 실제와 맞나?"를 물을 fixture 가설 목록.

## 5. 새 Stage 정의 (요약 — 상세 수용 기준은 roadmap 참조)

| Stage | 이름 | 규모 | 핵심 산출물 |
|---|---|---|---|
| 8 | 홈 개편 + 위험 지도 | L | risk 판정 룰+테스트, heatmap 홈, 근거 패널, 이번 주 주목, UI 공통 원칙 적용 |
| 9 | 변경 영향 | M | change_impact 서비스+API, 변경 영향 화면, 검토 체크리스트 |
| 10 | RCA 체인 | L | Test/RootCause 온톨로지 확장, fixture 보강, RCA 그래프 화면 |
| 11 | Ask SoC | M | 질의 서비스+API, 검색창/프리셋, 근거 인용 답변 |
| 12 | 데모 + 효과 측정 | M | 스토리 모드, TAT 측정 체계, 워크숍 자료 |
| 13+ | (이연) JIRA/Confluence 커넥터, 한국어 임베딩 검색, 운영 파일럿 | — | 원점 문서도 "ingestion 자동화보다 연결 모델 검증이 먼저" |

## 6. 변하지 않는 것

- 온톨로지 v1.0 계약, evidence-grounded validator, LLM 3단 체인, PostgreSQL 계층, 반입 파이프라인 — 전부 그대로 기반으로 사용.
- 결정 자동화 금지, owner 할당 금지, 쓰기 API 금지(반입 제외), 근거 없는 high confidence 금지.
- Stage scope lock 규율, 한국어 1급, 포트 규칙(5275/8155).
