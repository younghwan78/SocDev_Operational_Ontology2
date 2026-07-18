# 설계 21 — 사내 실데이터 구축 전 준비 (P0/P1 개선 묶음)

> 2026-07-18 전체 코드 검토(UX 포함)에서 도출된 개선안 중 사용자가 전부 승인한 범위.
> 목표: **사내 데이터가 처음 들어오는 날의 경험**을 깨는 결함 제거 + 코크핏 첫 질문의
> 답 품질 개선. 기존 계약은 additive로만 확장한다 (파괴적 변경 없음).

## 1. 범위 (패키지)

| # | 패키지 | 층 | 근거 |
|---|---|---|---|
| R1 | 빈 DB 온보딩 | FE | 빈 PostgreSQL에서 홈이 무한 로딩 (projects=[] → heatmap enabled=false → isPending 영원) |
| R2 | 반입 열 스펙 표면 | BE+FE | 허용값/형식을 화면에서 알 수 없어 거부-루프 유발 |
| R3 | 반입 dry-run | BE+FE | 대량 갱신 반입은 사실상 비가역 — 검사만 실행 후 확정 반입 2단계 |
| R4 | 행위자(actor) 기록 | BE+FE | 단일 공유 토큰 체제에서 배치/질의/가정 세트에 "누가"가 없음. 지금 안 넣으면 초기 기록이 전부 익명 |
| R5 | 위험 지도 등급 정렬 + 시점 비교 프리셋 | FE | "가장 위험한 것"이 첫 줄이 아님 / as-of diff는 시각 2개 타이핑 필요 — 발견가능성 낮음 |
| R6 | 오류 detail 표면 + 재시도 | FE | 백엔드 한국어 detail을 프론트가 버리고 일반 오류 한 줄만 표시 |
| R7 | 시나리오 상세 정합 | FE | 위험 맥락 단절(등급 요약 부재), Advisory 역할 선택 미노출(API는 지원), 시간 표기 원시 |
| R8 | 마감(P2) | FE | StatStrip 앵커 중복, 시간 포맷 혼재, 위험 지도 "전체" 칩, 확신도 라벨 분리, 워크벤치 섹션 접기 |
| R9 | 마스터 데이터 구축 절차 문서화 | docs | Project/Scenario/IPBlock은 YAML seed 경로뿐 — 워크플로가 어디에도 명문화 안 됨 |

범위 외 (기존 백로그 유지): 목록 가상화·서버 필터(실규모 측정 후), 인증 고도화(Stage 14),
동기화 상태 UI(Stage 19와 함께), 시맨틱 검색(Stage 18), 다과제 복수화(설계 14 §4).

## 2. 계약 변경 (전부 additive)

### 2.1 반입 열 스펙 (R2)

`GET /ingest/mappings`의 `IngestMappingInfo`에 `column_specs` 추가:

```text
IngestColumnSpec:
  column: str            # 한국어 열 이름 (계약)
  field_path: str        # 모델 필드 경로 (hover 참고용)
  required: bool
  kind: "text" | "int" | "bool" | "list"
  separator: str | None  # list일 때 구분자 (';')
  allowed_values: list[str]   # 값 도메인이 있으면 "code (라벨)" 목록, 없으면 []
  ref_collection: str | None  # 참조 무결성 검사 대상 컬렉션
```

도출은 `IngestMapping` 정의(column_map/int/bool/list/required/label_domains/ref_checks)
+ `VALUE_LABELS`에서 결정론으로 계산 — 새 저장 없음. 매핑 정의가 곧 단일 소스 유지.

### 2.2 dry-run (R3)

`POST /ingest/file?dry_run=true` → `IngestService.ingest_rows(..., dry_run=True)`:
파싱→검증→upsert 3분류→품질 리포트까지 전부 계산하되 **쓰기 4종을 모두 생략**
(add/remove, 버전 로그, 보류 풀, 배치 기록). `IngestReport.dry_run: bool` 에코,
배치 status는 `"dry_run"`(기록되지 않으므로 이력에 나타나지 않음). 커넥터 CLI의
기존 dry-run과 의미 동일 — UI가 같은 능력을 얻는다.

### 2.3 행위자 (R4)

- 헤더 `X-SOC-Actor` (프론트가 `encodeURIComponent`로 인코딩, 백엔드 `unquote` 디코딩 —
  HTTP 헤더 latin-1 제약 대응). 미설정 시 None — 강제 아님(단일 토큰 체제의 한계 명시).
- 기록 지점: `IngestBatch.actor` / `AskLogEntry.actor` / `WhatIfSet.created_by`.
  세 저장소 모두 payload jsonb 복원 방식 → **DB 마이그레이션 불필요** (additive).
- 프론트: localStorage `soc-actor`, 반입 센터에 작성자 입력 1곳. 모든 요청 미들웨어에서
  헤더 자동 첨부.

### 2.4 위험 지도 UI 상태 (R5)

URL 파라미터 추가: `sort=base`(기본 정렬 유지 시) — 기본은 등급 내림차순(높음 우선,
동률은 근거 수). `project=all` = 전체 프로젝트(API의 project_id 생략과 동일).
"최근 1주 변화" 프리셋 = `asof(now-7d)+asofb(now)` 설정 숏컷 — 기존 diff 계약 그대로.

## 3. 수용 기준

1. 빈 저장소(InMemoryRepository({}))로 만든 앱에서 홈이 로딩이 아니라 온보딩 안내를 렌더.
2. `dry_run=true` 반입 후: 저장소 객체 수/배치 이력/보류 풀/버전 로그 전부 불변,
   리포트 카운트는 실제 반입과 동일.
3. `X-SOC-Actor: %EC%9E%A5%EA%B8%B8%EB%8F%99` 헤더로 반입 시 배치 actor == "장길동".
4. `/ingest/mappings` 응답의 issues 매핑에 `상태` 열 spec: required, allowed_values에
   `open (미해결)` 포함.
5. 위험 지도 기본 렌더에서 첫 행의 overall_grade ≥ 마지막 행 (등급 순).
6. 조회 실패 시 서버 detail(있으면)이 화면에 표시되고 재시도 버튼이 refetch를 호출.
7. 기존 회귀 전부 green: backend pytest / ruff / mypy / validate-data / frontend build·test·lint.

## 4. 구현 순서

BE(R2→R3→R4) → openapi 재생성 → FE 공통(R6, 포맷터, actor) → 화면(R1, R5, R7, R8)
→ 문서(R9) → 회귀 → CHANGELOG.
