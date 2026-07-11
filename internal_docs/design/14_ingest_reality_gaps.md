# 14. 반입 현실 갭 — 사내 JIRA/Confluence 데이터 품질과 증분 동기화

> 2026-07-11 사용자 관찰(사내 JIRA 취합 경험)을 현재 구현에 대조한 갭 분석과 교정 설계.
> 선행: `12_jira_connector.md` (커넥터 골격), `05_long_term_improvement_plan.md` Stage 15.

## 1. 관찰된 사내 현실 (사용자 보고)

| # | 현실 | 현재 구현의 반응 |
|---|---|---|
| R1 | 라벨/과제 미지정·오지정 | 미지정 행 거부(소실), 오지정·미존재 과제 ID는 무검증 수용 |
| R2 | 상태 미갱신 방치 | JIRA 상태 그대로 신뢰, `updated` 미반입 → 정체 감지 불가 |
| R3 | 상세는 Confluence 등 외부 | 이슈↔문서 링크 미수집 (chunk는 별도 반입) |
| R4 | 다과제 공통 이슈 | `Issue.project_id` 단수 — 시나리오 연결 없으면 한 과제에 갇힘 |
| R5 | 그룹별 JIRA 상이 + 대량 | 단일 field map/env, pagination 없음, upsert 없음 |
| R6 | 완료 일정 미준수 | duedate 미반입, 일정 신호는 수동 |
| R7 | **같은 키/URL이 주기적으로 갱신됨** | 재반입 = 새 배치 추가. Postgres는 id upsert로 덮어쓰나 in-memory는 중복 축적(경로 불일치), "변경 없음" 감지 없음 → 전량 재쓰기 |

구조적 진단 두 가지:

1. **수용/거부 이분법**: 사내 데이터 대부분은 "쓸 수 있지만 불완전" — 중간 지대(보류·큐레이션)가 없다.
2. **연결률이 진짜 지표**: 반입에 성공해도 시나리오/IP에 연결되지 않은 이슈는 위험
   지도·RCA·변경 영향 어디에도 나타나지 않는 죽은 데이터다. 현재 이 측정 자체가 없다.

## 2. 교정 패키지

### J1. 반입 품질 리포트 + 큐레이션 루프 (R1·R2·연결률)

`IngestReport`에 결정론 `quality` 섹션 추가:

- **라벨 미등재 값**: 수용된 객체의 값 도메인 필드(status/severity/issue_type/…)를
  `VALUE_LABELS`와 대조, 미등재 값 목록. (사내 워크플로 상태가 value_maps에 없으면
  지금은 원문이 조용히 저장됨 — 이를 드러낸다.)
- **참조 무결성 경고**: project/scenario/IP 참조가 저장소에 실재하는지 대조.
  경고이지 거부가 아니다 — 선반입 후 교정 허용.
- **온톨로지 연결률**: 시나리오/IP에 1건 이상 연결된 행 비율. 도입 성패 지표.
- 매핑에 검사 메타데이터를 선언적으로 부착: `label_domains`(필드→값 도메인),
  `ref_checks`(필드 경로→컬렉션), `linkage_fields`(연결 판단 경로).

큐레이션 루프(1단계): 거부/미연결 행을 **수정용 CSV로 내려받기** → 사람이 채워
재반입.

큐레이션 루프(2단계, **구현 완료 2026-07-11**): **quarantine 보류 풀** —
거부 행을 원본 열 값 그대로 저장(`ingest_quarantine` 테이블, 온톨로지 컬렉션이
아니라 ingest 스테이징). 반입 센터의 "큐레이션 대기열" 카드에서 매핑별로
수정용 CSV(원본 값+사유 열)로 내려받아 고쳐 재반입하면, **같은 id의 보류 행이
자동 해소(resolved)** 된다. 원 배치 rollback 시 보류 행도 함께 제거.
`GET /ingest/quarantine` (읽기 전용 — 쓰기는 여전히 ingest 배치뿐).

### J2. 증분 동기화 — upsert·변경 없음 건너뛰기·페이지 순회 (R5·R7, 이번 구현의 중심)

**반입 의미론을 append에서 id-upsert로 통일한다.**

- `ingest_rows`가 대상 컬렉션의 기존 id/payload를 조회해 행을 3분류:
  - **신규**: 저장. **갱신**: 내용이 다르면 교체(기존 객체 제거 후 저장).
  - **변동 없음**: `source` 메타를 제외한 payload가 동일하면 **쓰지 않고 건너뜀**
    — 기존 객체·계보 유지. R7의 "update되는 부분만" 요구의 핵심.
- 배치 기록에 `updated_count`/`unchanged_count` 추가 (기존 필드 불변, 하위 호환).
- **rollback 의미론 재정의(문서화)**: rollback은 "그 배치가 현재 소유한 객체 제거"다.
  갱신된 객체의 계보는 최신 배치로 이전되므로, 이전 배치 rollback은 그 객체를
  건드리지 않는다. 버전 이력·복원은 하지 않는다 (이력이 필요하면 별도 Stage).
- in-memory 경로에 `remove_by_ids` 추가 — Postgres UPSERT와 의미 일치(패리티 복원).
- JIRA fetch 측 증분: `sync-jira --since auto|<ISO>` → `updated >= <ts>` JQL 결합.
  `auto`는 배치 이력에서 같은 소스의 마지막 완료 시각을 찾는다(별도 상태 저장 없음).
- `JiraHttpClient` pagination(`startAt` 순회) + `env_prefix`(그룹별 인스턴스:
  `CAMERA_JIRA_BASE_URL` 등) — 사내 검증 대상, 테스트는 Fake 경로.
- Confluence: 동일 upsert 경로라 같은 URL 페이지의 재반입은 본문이 같으면 건너뛰고
  다르면 교체된다 — 커넥터 코드 변경 불필요.

### J3. 신선도·일정 신호 (R2·R6) — **구현 완료 (2026-07-11 승인)**

`Issue.updated_week`/`due_week`(optional — 56 유래 무변경 통과). field map
`week_columns`가 JIRA `updated`/`duedate`를 ISO 주차로 변환. 결정론 룰:
**기준 주차 = 데이터의 최신 활동 주차**(벽시계 없음 — fixture 우주에서도 성립),
미해결 + 4주(`_STALE_WEEKS`) 무활동 = 정체, 목표 주차 경과 = 지연. 판정 근거
주차를 문구에 명시 (수치 점수 아님). 이슈 목록에 배지 노출.

### J4. 이슈↔Confluence 연결 (R3) — **구현 완료 (2026-07-11 승인)**

`Issue.doc_refs`(외부 문서 URL/키 — remote link 유래, 사내 필드 확정 시 field map
columns에 추가), `SemanticChunk.related_issue_ids`(Confluence `issue_keys` 반입).
RCA 상세에 "관련 문서 후보 — 증거 아님" 섹션. 증거 승격은 큐레이션(§3 원칙 불변).

R4(다과제)는 J1 큐레이션(시나리오 연결)으로 흡수 시도 후, 부족하면 `project_ids`
복수화를 그때 결정한다 — 계약 변경은 마지막 수단.

## 3. 불변 원칙 확인

- 쓰기는 여전히 ingest 배치 경로만. upsert도 배치 안에서만 일어난다.
- 품질 리포트·연결률·정체/지연 신호는 전부 결정론 + 근거(날짜·id 대조) — 수치 점수 없음.
- 자동 배정 금지 유지: 큐레이션은 후보 제시까지, 확정은 사람.

## 4. 구현 상태 (2026-07-11 — 전 패키지 완료)

- J1 품질 리포트 + 큐레이션 루프 1·2단계(quarantine 보류 풀 포함) ✔
- J2 upsert/unchanged/counts/rollback 의미론/--since/pagination/env_prefix ✔
- J3 신선도·일정 신호(updated_week/due_week·week_columns·정체/지연 룰) ✔
- J4 이슈↔문서 연결(doc_refs·related_issue_ids·RCA 관련 문서 후보) ✔
- **범위 외(미착수)**: upsert 버전 이력(rollback을 "이전 상태 복원"으로 확장),
  R4 다과제 `project_ids` 복수화(큐레이션으로 부족할 때만)
