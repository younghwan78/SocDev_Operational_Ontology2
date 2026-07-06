# Stage 16 설계 — UI 정밀 감사와 개편 (파일럿 전 완성)

> 상태: v1.0 제안 (2026-07-06). 장기 계획 `05_long_term_improvement_plan.md`의 Stage 16.
> 근거: ① 사용자 확정 방향 "UI가 설득의 핵심 — 시스템이 좋아도 정보를 찾기 어려우면
> 의미가 없다" (`03_course_correction.md` §1), ② Web Interface Guidelines
> (vercel-labs/web-interface-guidelines, 2026-07-06 fetch) 대조 감사,
> ③ Stage 8~12 실구동 E2E에서 직접 관찰한 사실.
> **위치 근거**: 워크숍(13)의 UX 피드백과 실데이터 반입(15)의 규모 변화를 반영한 뒤,
> 운영 파일럿(17) 전에 완성한다.

---

## 1. 감사 방법

1. 자체 UI 공통 원칙 6종(`03_course_correction.md` §3) 준수 여부 화면별 점검.
2. Web Interface Guidelines 전 규칙 대조 (접근성/포커스/폼/타이포/콘텐츠/성능/URL 상태/
   터치/다크모드/i18n) — 코드 grep + 실구동 확인.
3. E2E 세션(1568px, Chrome)에서 관찰된 실사용 마찰 기록.

## 2. 화면별 현황 분석

### 2.1 위험 지도 (홈, `RiskMapPage.tsx`)

**강점**: 첫 화면에서 위험 식별(정렬·기호·색), 근거 패널 drill-down 3클릭 경로,
열 고정으로 탭 전환 시 구조 유지, hover에만 ID.

**문제 (관찰 사실)**:
- R1. 10열 heatmap이 1500px에서도 가로 스크롤 필요 — **시나리오 열이 sticky가 아니라**
  스크롤하면 행 이름이 사라진다 (E2E에서 종합 열 확인 시 이름 소실 확인).
- R2. 프로젝트 탭이 `useState`만 — **URL에 없어** 새로고침/공유 시 초기화 (가이드라인:
  URL reflects state). 근거 패널 선택도 동일.
- R3. 종합 열이 다른 셀과 시각적으로 구분되지 않는다 (마지막 열임을 알기 어려움).
- R4. 범례가 우상단 구석 — 표와 시선 동선이 끊긴다. 등급 필터(예: 높음만 보기)가 없어
  실데이터 규모(시나리오 수십 개)에서 훑기 어려워질 것.
- R5. "이번 주 주목" 설명문에 근거 ID성 문자열(예: `mitigation_margin_trace`)이 본문으로
  노출 — ID 숨김 원칙의 회색지대 (backend description 조립 시 제목 대신 코드 사용).
- R6. 셀 버튼에 시각적 focus-visible 링 없음(브라우저 기본 outline 의존, 스타일 불일치).

### 2.2 변경 영향 (`ChangeImpactPage.tsx`)

**강점**: 딥링크 자동 실행(`?ip=&knob=`), knob 방향성 뱃지 색 의미 일관, 체크리스트 복사.

**문제**:
- C1. `<select>` 4개가 인접 `<span>` 라벨만 있고 `htmlFor/id` 연결 없음
  (`ChangeImpactPage.tsx:76-107`) — 스크린리더가 라벨을 못 읽는다 (가이드라인: form controls
  need label). 사용자가 폼을 조작해도 URL이 갱신되지 않아 결과 공유 불가(읽기만 지원).
- C2. 영향 KPI 칩이 원문 코드(`ddr_bw_peak` 등) — KPI는 표시명이 없는 계약이라 불가피하나
  단위/방향 tooltip 외 설명 부재.
- C3. 4분면 카드 높이 편차로 시선 동선이 불규칙 (KPI 칩 카드가 짧아 공백 큼).
- C4. 분석 실행 중 로딩이 텍스트 한 줄 — 버튼 상태 변화(스피너/비활성) 없음.

### 2.3 이슈 분석 (`IssueAnalysisPage.tsx`)

**강점**: 경고 이슈 선두+빨간 강조, 7단 체인 색 보더, `?issue=` 딥링크.

**문제**:
- I1. **텍스트 검색이 없다** — 이슈 36건은 버티지만 Stage 15 실반입(수백 건) 후 파산.
  필터도 URL 미반영 (project/verification이 useState만).
- I2. 목록이 전량 DOM 렌더 (CollapsibleList limit 12 후 "더 보기"로 한 번에 전부) —
  대량 데이터 시 성능 저하 (가이드라인: >50 items virtualize).
- I3. status/issue_type이 원문 코드 노출 (`closed`, `latency_regression`) — 한국어 1급 위반의
  잔존 영역. severity/priority/availability/result 등 **값 도메인 전반의 공통 문제** (→ §4 U1).

### 2.4 Ask SoC (`AskPage.tsx`)

**강점**: `?q=` URL 상태, 인용 칩→카드 스크롤, 인용 카드 하이라이트, 검증 기록 접기.

**문제**:
- A1. 답변 본문이 컨테이너 전폭(~1400px) — 장문 한국어 가독 한계 (권장 measure 초과).
- A2. LLM 응답 ~20초 동안 텍스트 한 줄뿐 — 진행감 부재, 제출 버튼 스피너 없음,
  완료 시 `aria-live` 알림 없음 (가이드라인: async updates aria-live).
- A3. 검색 입력에 `aria-label`/`autoComplete="off"`/`spellCheck={false}` 부재.
- A4. matched_terms(영문 토큰)가 카드마다 노출 — 디버그성 정보라 기본 접기가 적절.

### 2.5 데이터 탐색 4화면 + 상세

- D1. **EvidencePage 가용성 필터 칩이 영어 하드코딩** (`EvidencePage.tsx:18`
  `AVAILABILITY_OPTIONS = ["available", ...]`가 그대로 버튼 라벨) — 한국어 1급 위반.
  korean_only 가드가 JSX 텍스트 노드만 검사해 `{expression}`을 못 잡는 구조적 허점.
- D2. AdvisoryTab 생성 시각이 ISO 원문 노출 (`AdvisoryTab.tsx:55`) —
  `Intl.DateTimeFormat("ko-KR")` 미사용.
- D3. 포트폴리오 주의 lane 44건이 접기로 완화됐지만 lane 내 정렬 기준(최근/우선순위)이 없음.
- D4. 시나리오 상세 개요의 KPI/변형 칩 원문 코드 — 상세 화면 예외로 허용 중이나
  단위·방향 tooltip은 부재.

### 2.6 공통 (레이아웃/스타일, `styles.css`, `App.tsx`)

- G1. focus-visible 공통 토큰 부재 — `.ask-input:focus`(styles.css:220)만 존재.
- G2. DemoStoryBar sticky top이 `49px` 하드코딩(styles.css:231) — 헤더가 줄바꿈되는
  좁은 폭에서 겹침.
- G3. 반응형: 1100px 분기 1개뿐. 1280px 노트북/프로젝터 확대(125%)에서 heatmap+패널이
  화면 밖으로 밀림 (E2E에서 페이지 수평 스크롤 발생 관찰).
- G4. 다크 모드/`color-scheme` 미설정 (사내 요구 시 대응 필요, 현재는 P2).
- G5. `prefers-reduced-motion` 미고려 (현재 애니메이션 미미 — 스토리바 타이머는 무관).
- G6. 숫자 표기에 `font-variant-numeric: tabular-nums` 미적용 (카운트/TAT 시간 열).
- G7. 내비 링크와 데모 링크 구분이 색뿐 — 그룹 시각 구조(질문 메뉴 vs 탐색 메뉴) 약함.

## 3. 원칙 대조 요약표

| UI 공통 원칙 (§3, 03_course_correction) | 판정 | 비고 |
|---|---|---|
| 1 질문→답→근거 3단 구조 | 충족 | 4개 질문 화면 모두 |
| 2 내부 ID 숨김 (hover/상세만) | 대체로 충족 | R5(설명문 내 코드), I3/D1(값 도메인 코드)이 잔존 |
| 3 색 의미 통일 | 충족 | 빨강/노랑/초록 일관, 기호 병용으로 색각 보완 |
| 4 클릭 3번 규칙 | 충족 | E2E로 확인 |
| 5 접기 기본 | 충족 | CollapsibleList 전면 적용 |
| 6 데모 스토리 모드 | 충족 | Stage 12 |
| (신규 필요) URL=상태 | **미충족** | R2, C1, I1 |
| (신규 필요) 로딩·진행 피드백 규약 | **미충족** | A2, C4 |
| (신규 필요) 접근성 기준선 | **미충족** | C1, A3, G1 |
| (신규 필요) 스케일 규약 (수백 건) | **미충족** | I1, I2, R4 |

## 4. 개선안 — 실행 패키지

### P0 — 파일럿 전 필수 (수용 기준에 직결)

**U1. 값 도메인 한국어화 체계 (I3·D1·D4의 근본 해결)** — 최대 항목.
- backend: `backend/ontology/glossary.py`에 `VALUE_LABELS: dict[str, dict[str, str]]`
  신설 — 값 도메인(문자열 코드)별 라벨 사전: `status`(이슈/요청/이벤트), `priority`,
  `severity`, `availability`, `schedule_signal`, `test_result`, `fix_type`, `issue_type`,
  `requirement_level`, `direction`(knob) 등. **fixture에 등장하는 전 값의 커버리지를
  테스트로 강제** (신규 값 반입 시 누락이 테스트로 드러남 — 반입 확대(15)와 맞물림).
- API: `GET /api/v1/meta/glossary` 응답에 `value_labels` 포함 (계약 재생성 3종 수행).
- frontend: `useValueLabels(domain)` 훅 — 표시는 한국어, hover title에 원문 코드
  (ID 숨김 원칙과 동일 패턴). 적용 지점: 이슈 목록/RCA 헤더, 요청 status/priority,
  이벤트 severity/schedule_signal, 근거 availability, 테스트 result, EvidencePage 필터 칩.
- EvidencePage `AVAILABILITY_OPTIONS`를 값+라벨 구조로 교체 (D1 해소).

**U2. URL=상태 원칙 도입 (R2·C1·I1)**
- 위험 지도: `?project=` (탭), `?cell=<scenario>:<ip>`(근거 패널 선택 — 공유 가능).
- 이슈 분석: `?project=&verification=&q=` (+기존 `?issue=`).
- 변경 영향: 사용자가 폼 실행 시 `setSearchParams`로 역동기화 (읽기는 기존 구현).
- 원칙 문구를 §3 공통 원칙 7번으로 승격: "탭/필터/선택은 URL에 반영 — 새로고침과 공유가
  화면을 재현한다."
- 테스트: 각 페이지 "URL로 진입 시 상태 재현" 컴포넌트 테스트.

**U3. 접근성 기준선 (C1·A3·G1·기타)**
- 모든 `<select>`/`<input>`에 `id` + `<label htmlFor>` (기존 span 라벨을 label로 교체).
- ask 입력: `aria-label`, `autoComplete="off"`, `spellCheck={false}`, `name="question"`.
- 공통 포커스 토큰: `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }`
  을 버튼/링크/셀 전반에 (기존 outline 제거 없이 일관화).
- 답변/분석 완료 영역에 `aria-live="polite"` (A2와 연동).
- 아이콘성 버튼(heatmap 셀 ●◐○)은 title 유지 + `aria-label="{시나리오}×{IP} {등급}"`.
- 검증: **axe-core smoke 테스트** 도입 — vitest에서 4개 질문 화면 렌더 후
  serious/critical 위반 0을 게이트로 (`npm i -D axe-core`; jsdom 한계는 문서화).

**U4. 로딩·진행 피드백 규약 (A2·C4)**
- 공통 `<Busy>` 컴포넌트: 스피너 + 경과 초 + 취소 여지(react-query cancel) —
  ask(최대 120s)와 advisory에 적용. 제출 버튼은 요청 시작 시 비활성+스피너
  (가이드라인: submit stays enabled until request starts; show spinner during).
- 목록 화면 최초 로드는 스켈레톤 3~5행 (텍스트 "불러오는 중…"보다 위치 안정).

**U5. 위험 지도 스케일·가독 (R1·R3·R4)**
- 시나리오 열 + 헤더 행 sticky (`position: sticky; left: 0 / top: 0` — 표 내부 스크롤 유지).
- 종합 열 배경 구분(`--accent-soft`) + 좌측 굵은 경계선.
- 등급 필터 칩(전체/높음만/중간 이상) — URL 반영(U2), 룰 아님·표시 필터임을 주석.
- 범례를 heatmap 카드 헤더로 이동.
- R5: backend 조립 문자열에서 근거 코드 대신 제목 사용 (`risk.py` focus description —
  `missing_evidence` 원문 나열을 "누락 근거 N건"으로 축약, 상세는 hover/패널).

**U6. 이슈 목록 검색+스케일 (I1·I2)**
- 클라이언트 텍스트 필터 입력(제목/유형/증상, 300ms debounce) + `?q=` URL 반영.
- 목록에 `content-visibility: auto` + `contain-intrinsic-size` 우선 적용, 500건+에서
  부족하면 가상화 라이브러리(virtua) 검토 (P1로 이월 가능).
- EvidencePage 카탈로그 목록에도 동일 적용.

### P1 — 품질 향상 (파일럿 중 병행 가능)

- U7. Ask 답변 가독: 본문 `max-width: 72ch`, 인용 칩 hover에 카드 미리보기 1줄,
  matched_terms 기본 접기 (A1·A4).
- U8. 타이포: 카운트/시간 열 `tabular-nums`(G6), `created_at` 등 시각을
  `Intl.DateTimeFormat("ko-KR", {dateStyle:"medium", timeStyle:"short"})`로 (D2),
  로딩 문자열 "…" 일관 재점검.
- U9. 레이아웃 견고화: `--header-h` CSS 변수로 story-bar top 산출(G2), 1280px 분기 추가 —
  위험 지도 패널을 슬라이드오버(우측 오버레이, ESC 닫기)로 전환하는 분기(G3),
  전 페이지 body 수평 스크롤 0 보증 테스트(뷰포트 1280/1500 스냅샷).
- U10. 포트폴리오 lane 정렬 기준 명시(P0/P1 → 최근 주차순) + lane별 근거 축약(D3).
- U11. 4분면 카드 균형: KPI 카드에 단위/방향 서브라인, grid `grid-auto-rows: 1fr` 검토(C3).
- U12. 내비 구조 강화(G7): 질문 메뉴 4개를 시각적 그룹(배경 캡슐)으로, 데모 스토리는
  우측 분리 버튼형.

### P2 — 선택 (사내 요구 발생 시)

- U13. 다크 모드: CSS 변수 이중화 + `color-scheme` + `prefers-color-scheme` (G4·G5 동시).
- U14. `Cmd/Ctrl+K` 글로벌 Ask 포커스 단축키.
- U15. 프린트 스타일시트 (주간 리뷰 인쇄/PDF 공유).

## 5. In-scope / Out-of-scope

**In-scope**: §4의 P0 전부 + P1 중 U7~U9 (나머지 P1은 시간 여유 시), glossary 계약 확장
(변경 규율 6단계 — value_labels는 모델이 아닌 라벨 사전이므로 schema 영향은 openapi만),
docs/ 가이드 스크린샷 재캡처(변경 화면), axe smoke 테스트 도입.

**Out-of-scope**: 신규 질문 화면, 온톨로지 저장 계약 변경, 모바일 전용 레이아웃(태블릿 이하),
디자인 시스템 라이브러리 도입(현행 수제 CSS 유지 — 56 재복잡화 전철 방지), 다국어(영어) UI.

## 6. 수용 기준

- [ ] 화면 표시 문자열 중 원문 코드 노출이 hover/상세로 한정 — **fixture 전 값 도메인
  라벨 커버리지 테스트 green** (U1)
- [ ] 4개 질문 화면: 새로고침/URL 공유로 탭·필터·선택 상태 재현 (U2, 테스트 고정)
- [ ] axe-core smoke: 4개 질문 화면 serious/critical 0 (U3)
- [ ] ask/advisory 실행 중 버튼 스피너+비활성, 완료 aria-live 알림 (U4)
- [ ] 위험 지도: 가로 스크롤 시 시나리오 이름 고정 표시, 등급 필터 동작 (U5)
- [ ] 이슈 500건 합성 데이터로 목록 필터 응답 <100ms 체감 확인 (U6 — 테스트용 대량
  fixture는 커밋하지 않고 생성 스크립트로)
- [ ] 1280px 뷰포트에서 전 화면 body 수평 스크롤 없음 (U9)
- [ ] 전체 회귀 green (기준선 §1.2 of 05 문서) + korean_only/ID 가드 유지

## 7. 검증 방법

```bash
# 기존 전체 회귀 + 신규:
cd frontend && npm run test          # axe smoke, URL 상태 재현, value_labels 렌더 테스트 포함
uv run pytest tests/test_glossary.py # value_labels 커버리지 (fixture 값 전수 대조)
# E2E: 1280px/1500px 두 뷰포트로 puppeteer 스크린샷 재캡처 → docs/assets 갱신
```

## 8. 위험과 대응

| 위험 | 대응 |
|---|---|
| 값 라벨 사전이 실데이터 신규 값에서 계속 누락 | 커버리지 테스트가 누락을 CI에서 강제 노출 (15의 반입 테스트와 연동) |
| URL 파라미터 난립으로 딥링크 호환 파손 | 파라미터 명세를 본 문서 부록으로 고정 (`project/cell/issue/verification/q/ip/knob/story/review`) — 변경 시 리다이렉트 유지 |
| axe가 jsdom에서 잡지 못하는 항목(색 대비 등) | 대비는 수동 체크리스트(P1 U9)로 보완, 한계를 테스트 주석에 명시 |
| CSS 개편이 기존 스크린샷 기반 문서와 어긋남 | 수용 기준에 docs 스크린샷 재캡처 포함 |
