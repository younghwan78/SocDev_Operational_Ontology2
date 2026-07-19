# 설계 25 — 리허설 유니버스 (가상 JIRA/Confluence + 주차 리플레이 + UX 판정)

> 목적: 사내 실데이터 연결 전에 **실제와 유사한 가상 JIRA/Confluence 데이터**로
> 코크핏 UX와 digital twin 표면(as-of·버전 로그·연결률·게이트·워터마크·링크
> 제안)이 "원하는 정보를 주는가"를 판정한다. 원천: 57 과제
> `E:\57_Claude_SoC_DigitalTwin\OperationalOntology\data\world.yaml`
> (U/V/W 1년 fixture, 이벤트 24 + activity_log 144 + missing_evidence 51 —
> **read-only 참조, 수정 금지**).

## 1. 원칙

1. **실 사내 전환이 payload 교체로 끝나야 한다** — 가상 데이터는 실 JIRA REST
   응답 형태(`fields.*`)와 Confluence 페이지 형태로 생성하고, 기존
   `FakeJiraClient`/`FakeConfluenceClient` + `jira_field_map.yaml` 경로를
   그대로 쓴다. 코드 경로는 실계정(Stage 19)과 100% 공유 — 리허설이 곧
   커넥터 사전 검증이다.
2. **JIRA/Confluence 역할 분담을 현실대로** (사용자 확정 2026-07-19):
   - **JIRA = 이슈·계획·진행사항** — 요약은 간결(한 줄 증상), 상태·심각도·
     일정(duedate)·담당 중심. 세부 서사를 넣지 않는다.
   - **Confluence = 세부 내용·기술 설명·공식 문서** — 배경/문제/목표 서사,
     역할별 검토 의견, 측정 리포트, **공식 architecture/design 문서**,
     결정 노트, 주간 회의록. 페이지는 `issue_keys`로 JIRA 키를 역참조
     (→ J4 doc_refs 후보).
3. **의도된 지저분함** — 리허설의 목적은 깨끗한 데모가 아니라 실데이터
   워크플로 검증이다: 링크 필드 대부분 비움(초기 연결률 저조 → 링크 제안
   검증), 미등재 상태값("In Review"/"백로그"), 심각도 일부 누락, 한/영 혼용,
   몰아서 갱신한 주차 1회(기록 규율 왜곡 데모), 검증 없는 종결 심기.
4. **감사 축 예외는 리허설 전용으로 격리** — `ingest_rows(recorded_at=...)`
   주입 시계는 리플레이 CLI만 사용, 배치 source_name에 `rehearsal:` 접두,
   **전용 DB(`soc_rehearsal`) 강제**: DSN에 "rehearsal"이 없으면 CLI가 거부
   (`--allow-any-dsn` 없이는). 운영/데모 DB의 transaction time은 계속 진실.

## 2. 변환 매핑 (57 world.yaml → 리허설 코퍼스)

| 57 원천 | 리허설 산출 | 비고 |
|---|---|---|
| events[24].trigger | JIRA 이슈 summary (간결) | 키 `SOCU-…/SOCV-…/SOCW-…` |
| events.situation(배경/문제/목표) | **Confluence 기술 노트** 본문 | JIRA description은 증상 한 줄만 |
| events.spans + activity_log(stage) | 주차 wave별 JIRA status 전이 | plan→Open, act→In Progress, judge→**In Review**(미등재 심기), result→Resolved/Closed |
| events.domains/trigger 토큰 | 이슈 제목 속 IP/시나리오 토큰 | 링크 필드는 비움 — 링크 제안(R1/R2)이 잡는다 |
| missing_evidence[51] | 근거 확보 이슈 (due=due_w, 다수 미해결) | J3 지연 신호·게이트 재료 |
| events.evidence | Confluence **측정 리포트** 페이지 | issue_keys 역참조 |
| events.decision + 주차 | 결정 CSV (decisions 매핑) | 리플레이 중간 wave에 반입 → 워터마크 검증 |
| role_positions(say/purpose/data_gap) | Confluence **주간 회의록**·검토 의견 페이지 | Ask SoC 검색 재료 |
| W 프로젝트 arch 이벤트(E-30x) | Confluence **공식 architecture/design 문서** | 공식 문서는 space `ARCH`, 라벨 [설계문서] |
| propagation | 연계 이슈 (제목에 원 키 언급) | |
| 프로젝트 U/V/W | project_u/v/w (labels.0) | 58 universe에 그대로 얹힘 |

상태 사전(값 정규화)은 기존 `jira_field_map.yaml` value_maps를 그대로 —
"In Review"/"백로그"는 의도적으로 사전 밖(경고 UX 검증).

## 3. 구성 요소

1. **`tools/build_rehearsal_from_57.py`** — world.yaml → `rehearsal/` 생성:
   - `jira_wave_W<주차>.json` (실 JIRA REST 형태, wave별 신규+갱신 이슈 전량 —
     upsert가 3분류), `confluence_pages.json`, `decisions_W<주차>.csv`,
     `replay_plan.json`(주차→날짜→파일 목록; base_date로 주차→실날짜 환산).
   - 결정론(같은 입력→같은 출력), 57 디렉토리 무수정.
2. **`ingest_rows(recorded_at: datetime | None = None)`** — additive 주입
   시계 (batch created_at·버전 recorded_at·source.ingested_at 단일 지점).
   JiraConnector/ConfluenceConnector `sync(recorded_at=...)` 관통.
3. **`rehearsal-replay` CLI** — replay_plan 순서대로 wave 반입. DSN 가드
   (§1.4), `--waves N`(부분 리플레이 — "N주차까지 상태" 재현), 요약 출력
   (wave별 신규/갱신/경고/보류).
4. **UX 판정 대본** `internal_docs/validation/03_rehearsal_ux_checklist.md` —
   실무 리더 질문 × [화면 경로 → 기대 답 → 판정] 표. 각 질문은 §2에서 심은
   발견 시나리오와 1:1 (답이 존재함을 데이터가 보장). 미발견=UX 백로그.

## 4. Out-of-scope

- 실 REST 호출(Stage 19), LLM 링크 제안(Stage 18), 리허설 데이터의 fixture
  승격(별도 결정), 57 도구/스키마 이식(참조만), 시나리오/IP 마스터 신규
  작성(58 기존 universe 재사용 — 57도 같은 U/V/W 세계관).

## 5. 수용 기준

- [ ] 변환 결정론 + 57 무수정 + 산출물 스키마 테스트 (jira payload가 field
  map으로 전량 해석, confluence가 semantic_chunks 매핑 통과)
- [ ] recorded_at 주입: 버전 로그가 wave 주차에 분포 (Memory+PG), 미주입
  경로(기존 반입) 동작 불변
- [ ] rehearsal-replay: DSN 가드 동작, 전량 리플레이 후 — 이슈 80건+,
  버전 로그 수백 행, 연결률 저조 시작, quarantine/경고 발생, 링크 제안
  다수, 게이트 미충족 존재, as-of 두 시점 diff 유의미
- [ ] UX 판정 대본 15문항+ 작성, 실서버(soc_rehearsal) 리플레이로 전 문항
  "기대 답 존재" 확인
- [ ] 전체 회귀 green, changelog, 실 전환 절차(payload/field map 교체)를
  handover에 1절 추가
