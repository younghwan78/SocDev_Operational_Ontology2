# JIRA/Confluence read-only 커넥터 — 사외 선행분 설계

> 상태: v1.0 (2026-07-11)
> 실현: 05 장기 계획 Stage 19의 **사외에서 가능한 부분을 앞당김** (백로그 §4 Phase 3).
> 사내 후속: 보안/계정 승인, 실 자격증명, 실 JIRA/Confluence 스키마 매핑 값, 주기 실행.
> 선행: Phase 1 반입 표면(매핑·중첩), Phase 2(ingest_rows 일반화 필요성 확인).

## 1. 원칙 — 커넥터는 ingest의 클라이언트일 뿐

1. **커넥터는 직접 저장하지 않는다.** JIRA 이슈 JSON → 행 정규화 → **기존 IngestService
   배치**로만 진입. rollback 의미론(배치 단위 삭제)이 그대로 동기화 취소가 된다.
2. **필드 매핑은 코드가 아니라 설정 YAML** (`backend/connectors/jira_field_map.yaml`):
   사내 JIRA 스키마 확정 시 코드 수정 없이 값만 교체. 컬럼 대상은 **기존 ingest 매핑의
   한국어 열 이름** — 매핑 로직 이중화 없음.
3. `source_origin=integrated`. `source_ref`는 rollback 계약(`import:<batch>:` 접두)을
   유지하면서 외부 키를 담는다: `import:<batch_id>:jira:<KEY>`.
   (05 Stage 19의 `jira:<key>` 단독 표기는 rollback 접두 계약과 충돌 — 합성으로 확정.)
4. 검색 후보 지위: Confluence 페이지는 `SemanticChunk` **후보**로만 반입 (§3 원칙 —
   supporting_basis 편입 전에는 증거가 아니다).
5. LLM/네트워크 없는 테스트: `JiraClientProtocol` + `FakeJiraClient`(fixture JSON).
   실 HTTP 클라이언트는 env 기반 얇은 구현만 두고 사내에서 검증.

## 2. 구조

```text
backend/connectors/
  jira.py         # JiraClientProtocol / FakeJiraClient / JiraHttpClient(얇음, env)
                  # JiraFieldMap(YAML 로드) / JiraConnector.sync(dry_run)
  confluence.py   # ConfluenceClientProtocol / Fake / ConfluenceConnector
  jira_field_map.yaml   # 기본 매핑 (사내 스키마 확정 시 교체 대상)
samples/sample_jira_issues.json       # JIRA REST /search 응답 형태 fixture
samples/sample_confluence_pages.json  # Confluence 페이지 fixture
```

### 2.1 IngestService 일반화 (전제 리팩터)

`ingest(filename, content, mapping)` = `parse_tabular` → **`ingest_rows(...)`** 위임.

```python
ingest_rows(source_name, rows, mapping_name, *,
            origin=SourceOrigin.IMPORTED, row_refs=None) -> IngestReport
```

- `row_refs[i]`가 있으면 `ref = import:<batch>:<row_refs[i]>` (예: `jira:PROJ-123`),
  없으면 기존 `import:<batch>:<source>#row<n>`. 둘 다 rollback 접두 유지.
- CSV 경로 동작 불변 (기존 테스트가 회귀 고정).

### 2.2 JiraFieldMap (YAML)

```yaml
issue_mapping: issues          # 사용할 ingest 매핑 이름
columns:                       # ingest 한국어 열 ← JIRA 응답 dotted 경로
  이슈 ID: key
  제목: fields.summary
  유형: fields.issuetype.name
  상태: fields.status.name
  심각도: fields.priority.name
  증상: fields.description
  프로젝트 ID: fields.labels.0    # 사내 스키마 확정 전 임시 — 교체 지점
  영향 시나리오: fields.customfield_scenarios   # 예시 placeholder
value_maps:                    # 열별 값 정규화 (JIRA 값 → 온톨로지 값)
  상태: {Open: open, "In Progress": open, Resolved: resolved, Closed: closed}
  심각도: {Highest: critical, High: high, Medium: medium, Low: low, Lowest: low}
constants:                     # 고정값 열
  확신도: medium
```

- dotted 경로는 dict/list 인덱스 접근(`fields.labels.0`). 누락 경로 → 빈 값(행 검증이 거부).
- `value_maps` 미등재 값은 원문 유지 — U1 값 라벨 커버리지 테스트(Phase 4)가 미번역을 드러냄.

### 2.3 JiraConnector / ConfluenceConnector

- `JiraConnector(client, field_map).rows()` — 정규화 행 + `row_refs=["jira:<KEY>", …]`.
- `.sync(ingest_service, dry_run)` — dry-run이면 저장 없이 정규화 결과·수락 예상만 보고,
  아니면 `ingest_rows(origin=INTEGRATED)`.
- Confluence: 페이지 → `semantic_chunks` 매핑 행(`청크 ID/본문/출처 ID/출처 유형` +
  기본값 `embedding_status=pending`, `evidence_confidence=low`), `row_refs=confluence:<id>`.
  → `semantic_chunks` IngestMapping 신설 (평면 필드만).

### 2.4 CLI

```bash
uv run python -m backend.cli.main sync-jira --payload samples/sample_jira_issues.json --dry-run
uv run python -m backend.cli.main sync-jira --payload ... --execute   # SOC_ONTOLOGY_DSN 필요
uv run python -m backend.cli.main sync-confluence --payload ... --dry-run
```

- `--payload`(fixture JSON) = FakeJiraClient — 사외 검증 경로. `--base-url/--token`은
  env(`JIRA_BASE_URL`/`JIRA_API_TOKEN`)로만 받는 실 클라이언트(사내 검증, 코드에 비밀 없음).
- `--execute`는 Postgres(DSN) 반입 — in-memory는 프로세스 종료로 무의미하므로 거부.

## 3. invariant 준수

- 쓰기 API 신설 없음 (CLI + ingest 배치). `test_no_write_endpoints` 무영향.
- 자격 증명은 env만 — 코드/저장소/설정 YAML에 비밀 미포함.
- 커넥터 장애와 무관하게 읽기 경로는 마지막 배치 데이터로 동작 (ingest 분리 구조 그대로).
- 수치 점수·자동 결정 없음. 동기화는 사람이 CLI로 실행 (주기 실행은 사내 후속).

## 4. 수용 기준

1. Fake payload → 정규화 행이 ingest 매핑 계약을 통과, `origin=integrated`,
   `ref=import:<batch>:jira:<KEY>` (테스트 고정).
2. 반입 이슈가 위험 지도/RCA에 반영되고 rollback으로 소멸 (기존 파생 뷰 통합 테스트 패턴).
3. Confluence 페이지가 semantic_chunks 후보로 반입 (증거 지위 아님 — 모델 기본 계약 유지).
4. dry-run은 저장 부작용 없음. CSV ingest 경로 회귀 없음 (기존 테스트 green).
5. 네트워크/실서버 없이 전 테스트 통과.

## 5. 구현 순서

1. 본 설계 문서. → 2. `ingest_rows` 리팩터(+origin/row_refs) + semantic_chunks 매핑. →
3. connectors(jira/confluence + YAML + Fake) + 테스트. → 4. CLI + E2E + CHANGELOG.
