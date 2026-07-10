# UI 실사용자 재설계 — 운영 루프 완결 + 신뢰 품질 (설계)

> 상태: v1.0 (2026-07-11, 사용자 승인 — goal 실행)
> 근거: 실구동 관찰(PostgreSQL 풀스택, 화면 9종 E2E) + `06_stage16_ui_overhaul.md` 감사.
> 관계: 06의 U1은 완료(Phase 4). 본 문서는 06의 U2~U6를 채택·보강하고,
> **운영 루프(반입→결정 재진입)의 UI 부재**라는 신규 갭을 추가한다.
> U7~U15 중 일부는 P1/P2로 흡수. 06은 감사 기록으로 유지.

## 0. 문제 재정의

Phase 1~3에서 백엔드 데이터 경로(반입 매핑 6종·결정 재진입·커넥터)가 완성됐으나
UI는 조회 전용 대시보드에 머물러 있다. 실사용자(실무 리더/회의 주재자/엔지니어/
데이터 관리자)의 반복 과업 기준으로 다음 갭이 관찰됐다:

1. **치명(신뢰)**: 실행 초안 전 항목이 같은 문장 2회 출력 / backend 조립 문장에
   원문 코드·ID·영어 역할명 임베딩(주목 카드·포트폴리오·초안) / 태세 배지가
   위험색과 같은 시각 언어.
2. **높음(파산 지점)**: 반입·결정 재진입 UI 부재(CLI뿐) / 이슈 검색 없음 /
   리뷰 센터 기본 W1(빈 주) / heatmap sticky 없음 / URL 미반영(공유 불가) /
   Ask 20s 로딩 한 줄.
3. **중간**: 접근성 기준선, 1280px, 다크모드, badge 맵 중복, 무언 실패 보조 쿼리.

## 1. 패키지와 순서 (각 단계 commit)

### P0-1. 신뢰 품질 (B1·B2·B3)

- **B1 실행 초안 중복 제거**: `DraftItem.statement == basis.description`이면 프론트에서
  설명 생략(참조 칩만). ReviewPack 상세 동일.
- **B2 backend 조립 문자열 규약** — "서술에는 제목/라벨, 코드는 hover/패널":
  - `risk.py` 주목 카드·셀 근거: 상태/유형 코드에 `value_label` 적용, 누락 근거
    id 나열 → "누락 근거 N건" 축약(id는 `source_refs` 유지 — 패널에서 열람).
  - `portfolio.py` 주의 항목: 누락 근거 id → 건수 축약, 역할 영어명 → 한국어 라벨.
  - `action_draft.py` 항목 서술: 동일 규약.
  - 역할 한국어: `glossary.ROLE_LABELS`(7 role id → 한국어) 신설 — 온톨로지 무변경,
    표시 라벨 사전(VALUE_LABELS와 동일 지위).
- **B3 태세 배지 시각 분리**: 위험 원형(●◐○ 빨/노/초)과 다른 시각 언어 —
  중립(아웃라인) 칩 + 실측 0건일 때만 텍스트 강조. "위험"과 "근거 강도" 축 분리.

### P0-2. 운영 루프 UI (A1·A2)

- **A1 반입 센터** `/ingest` (데이터 탐색 그룹): 파일 선택 + 매핑 선택 → 기존
  `POST /api/v1/ingest/file` 호출 → 수용/거부(행·사유 한국어) 표시. 템플릿 CSV
  다운로드(매핑 헤더 프리필). 반입 이력 + rollback 버튼(기존 API). 근거 탐색의
  배치 이력 카드는 이 화면으로 이동. **신규 쓰기 API 없음** — 기존 경로의 화면화.
  - 매핑 목록은 `GET /api/v1/ingest/mappings` 신설(읽기, IngestService.mappings()
    노출 — 헤더/필수 열 포함)로 동적 제공.
- **A2 결정 루프 일원화**: 리뷰 팩 상세에 "채운 결정 CSV 반입" 업로드(→ `decisions`
  매핑) + "이 팩에서 나온 결정 N건" 목록(decisions를 event/pack 시나리오로 필터).

### P0-3. URL=상태 + 스케일 (C1·C2)

- **C1**: 위험 지도 `?project=&cell=<scenario>:<ip|overall>`, 이슈
  `?project=&verification=&q=`, 리뷰 `/review/:week`(기존)+팩 `?pack=`,
  변경 영향 실행 시 `setSearchParams` 역동기화 + 딥링크 불일치 시 명시 피드백.
- **C2**: 이슈/근거 목록 텍스트 필터(300ms debounce, `?q=`), heatmap 시나리오
  열+헤더 sticky, 등급 필터 칩(전체/높음만/중간 이상 — 표시 필터), 종합 열 배경
  구분, 범례를 heatmap 카드 헤더로.

### P1. 사용성 완성 (A3·C3·C4·D)

- **A3 리뷰 센터 재편**: 기본 선택 = 데이터 있는 최신 주, 주차 칩에 건수 병기,
  최근 8주 + "전체 보기" 접기.
- **C3 로딩 규약**: 공통 `<Busy>`(스피너+경과 초) — Ask/advisory 적용, 제출 버튼
  비활성+스피너, 완료 `aria-live`. 목록 스켈레톤은 P2 이월 가능.
- **C4 폼 언어**: knob→제어 항목, capability→기능 (i18n).
- **D 접근성·견고성**: select/input 라벨 연결, `:focus-visible` 공통 토큰,
  heatmap 셀 aria-label, axe-core smoke(질문 4화면, serious/critical 0),
  공통 `<StatusBadge>`/`<AsyncSection>`으로 badge 맵·무언 실패 정리,
  한국어 substring 매칭 제거.

### P2. 마감 (여력 시)

다크모드(변수 이중화+`color-scheme`), `Ctrl+K` Ask 포커스, `tabular-nums`,
프린트 스타일, 1280px 분기.

## 2. invariant 준수

- 쓰기는 기존 ingest POST/rollback만 — 신규 쓰기 API 없음(`/ingest/mappings`는 GET).
  `test_no_write_endpoints` 허용 목록 불변.
- 수치 점수 없음 · 한국어 1급(i18n/ko.ts, glossary 라벨) · 내부 ID hover만.
- B2는 표시 서술 개선 — BasisItem `ref_id`/`source_refs` 계약 불변(추적성 유지).

## 3. 수용 기준 (패키지별)

- P0-1: 실행 초안에 동일 문장 중복 0. 주목 카드·포트폴리오·초안 서술에
  원문 코드/ID/영어 역할명 노출 0(hover·패널 제외, 테스트 고정). 태세 칩이
  위험 원형과 다른 시각 언어.
- P0-2: 반입 센터에서 샘플 CSV 업로드→수용/거부 표시→rollback 왕복.
  리뷰 팩에서 CSV 내보내기→반입→결정 목록 표시 왕복. 신규 쓰기 API 없음.
- P0-3: 새로고침/URL 공유로 탭·필터·선택 재현(테스트). 시나리오 열 sticky.
  이슈 텍스트 검색 동작.
- P1: axe smoke serious/critical 0. Ask 실행 중 버튼 비활성+경과 표시.
- 공통: 전체 회귀 green(backend+frontend), validate-data 오류 0.

## 4. 검증

회귀 명령 전체 + 실구동 E2E(8155/5275) 각 패키지 후. 스크린샷 재캡처는
docs 갱신 시점(P1 완료 후)에 일괄.
