# 사내 핸드오버 킷 — 도입 준비 체크리스트 (D2)

> 대상: 사내 도입 담당(본인/운영 파트너). 사외에서 준비 가능한 것은 전부 끝난 상태이며
> (runbook.md 참조), 이 문서는 **사내에서만 할 수 있는 일**의 순서와 워크시트다.

## 0. 준비 완료 상태 (참고)

- 배포: `deploy/` compose 한 벌 — 리허설 검증 완료 (인증·시드·로그·복구)
- 커넥터: JIRA/Confluence mock 검증 완료 — 실 스키마 값만 비어 있음
- 데이터 품질: upsert 증분·품질 리포트·보류 풀 — "더러운 데이터" 대응 내장

## 1. 보안·계정 신청 체크리스트

| # | 항목 | 비고 |
|---|---|---|
| 1 | 서버 1대 (Docker 가능, 사내망) | 4C/8GB면 충분 — DB 포함 단일 호스트 |
| 2 | JIRA 서비스 계정 + API 토큰 (read-only) | 대상 프로젝트 조회 권한만 |
| 3 | Confluence 서비스 계정 (read-only, 선택) | 문서 후보 검색용 |
| 4 | 사내 on-prem LLM API 엔드포인트/키 (선택) | 없어도 결정론 모드로 동작 |
| 5 | 방화벽: 서버→JIRA/Confluence/LLM API | outbound만 필요 |
| 6 | 저장소 미러 (git) | 코드 반입 경로 |

## 2. JIRA 필드 매핑 워크시트

`backend/connectors/jira_field_map.yaml`의 값을 사내 스키마로 교체한다.
결정할 것은 아래 6개가 전부다:

| 매핑 대상 | 현재(임시 규약) | 사내 확정 값 기입 |
|---|---|---|
| 과제 구분 | `fields.labels.0` | ☐ (예: `fields.project.key` 또는 커스텀필드) |
| 영향 시나리오 | `fields.customfield_scenarios` | ☐ 커스텀필드 ID |
| 영향 IP | `fields.customfield_ips` | ☐ 커스텀필드 ID |
| 워크플로 상태 → 표준 상태 | Open/In Progress/… 기본 5종 | ☐ 사내 상태명 전수 나열 |
| 우선순위 → 심각도 | Highest~Lowest | ☐ 사내 우선순위 체계 |
| 관련 문서 링크 | (미설정) | ☐ remote link/커스텀필드 |

검증 절차: `sync-jira --jql '...' --since auto` (dry-run — 저장 없음) 실행 →
**라벨 미등재 값**과 **온톨로지 연결률**을 보고 value_maps를 보강 → 반복.
연결률이 도입 성패 지표다: 시나리오/IP에 연결 안 된 이슈는 화면에 나타나지 않는다.

## 2b. 마스터 온톨로지 구축 절차 (R9, 설계 21 — 트랜잭션 반입보다 먼저)

반입 센터(CSV/JIRA)는 **트랜잭션 데이터**(이슈·테스트·이벤트·근거·KPI 관측·결정)만
받는다. 위험 지도의 행과 열을 만드는 **마스터 온톨로지**는 의도적으로 큐레이션
경로(YAML 시드)만 존재한다 — 시나리오/IP 카탈로그는 리뷰 없이 바뀌면 안 되는 계약이다.

| 대상 | 파일 | 주의 |
|---|---|---|
| 프로젝트·마일스톤 구조 | `fixtures/project.yaml` | phase 값은 `VALUE_LABELS.project_phase` 등재 필수 |
| 시나리오·그룹·변형·KPI 정의 | `fixtures/scenario.yaml` | KPI id는 반입 `kpi_observations`의 참조 대상 |
| IP/시스템 블록·knob·의존 룰 | `fixtures/ip.yaml` | `aliases`가 커넥터 엔티티 해석의 기반 |
| 역할 7종 | `fixtures/role.yaml` | 명칭·구성 고정 (CLAUDE.md §2.2) — 통상 수정 불필요 |

**절차 (관리자, git 리뷰 경유):**

1. fixture YAML 수정 → `uv run python -m backend.cli.main validate-data` (계약 검증)
2. `uv run pytest -p no:cacheprovider` (glossary 커버리지·정합 게이트 — 새 enum 값은
   `VALUE_LABELS`에 라벨 추가)
3. PR 리뷰 → merge → 운영 DB에 `uv run python -m backend.cli.main db-seed` (멱등 upsert)
4. 화면 확인: 위험 지도 열/행, 시나리오 목록, 변경 영향 IP 선택지

> 사내 실물 카탈로그 작성 시작점: `56/docs/step1_synthetic_universe/`의 구조를
> 실제 과제명·IP 목록으로 치환한다. 시나리오는 "고객이 체감하는 동작 단위"로 자른다.

## 3. 도입 1~2주차 플랜

**1주차 — 리허설 (관리자만)**
1. compose 기동 + `SEED_FIXTURES=true`로 synthetic 데모 확인 (화면·토큰·데모 스토리)
2. §2 워크시트 확정 → dry-run 반복으로 연결률 ≥ 70% 달성
3. `down -v` 초기화 → `SEED_FIXTURES=false` → 실데이터 첫 `--execute` 반입
4. 위험 지도/이슈 분석이 실데이터로 채워지는지 확인, 백업 cron 등록

**2주차 — 파일럿 (3~5명)**
1. 파일럿 사용자에게 토큰 + `docs/` 가이드(특히 데모 스토리) 배포
2. 주간 리뷰 1회를 이 시스템 화면으로 진행 — 리뷰 팩 CSV 왕복(결정·액션)까지
3. Ask 질문 로그(FAQ 화면)를 보며 검색이 못 찾는 사내 용어를
   `_DOMAIN_TERM_GROUPS`(한↔영 브리지)에 추가
4. 피드백 수집: 화면별 "판단에 도움됐나 / 무엇이 비어 있나" 2문항

**성공 판정(파일럿 종료 시)**: ① 주간 리뷰 준비 시간 단축 체감 ② "검증 없는 종결"
류의 발견이 실제 액션으로 이어진 사례 ≥ 1건 ③ 연결률 유지 ≥ 70%.

## 4. 남은 사외 후속 (파일럿 피드백 반영용)

- D3 시맨틱 검색(임베딩) — Ask 개념 질문 보강, on-prem 임베딩 모델 확정 필요
- D4 검증 세션 자료(가설 판정 모드) — 확대 보고 일정이 잡히면 준비
- 다과제 공통 이슈(project_ids 복수화) — 파일럿에서 실제로 막히면 계약 확장
