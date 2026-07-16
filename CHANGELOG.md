# CHANGELOG

## what-if 워크벤치 — 위험 지도 가정 실험 모드 (2026-07-17)

> 설계: `internal_docs/design/18_whatif_workbench.md`. 배경: 사용자 지적 —
> 엔진은 가정 4종·복합 10개를 지원하는데 UI는 이슈 상세 1클릭 2종뿐(반응형).
> "선택지를 미리 보여주고 결정 scope을 넓히는" 탐색형 표면으로 확장.

- **W1 가정 후보 제안**: `GET /what-if/candidates?project_id=` —
  기존 신호에서 결정론 도출 4룰 (검증 없는 종결→다시 열리면? / 미해결
  고심각→해결되면? / 목표 주차 보유→당겨지면?(기본 −2주, 조정 가능) /
  at_risk·window_closing 이벤트→정상 진행되면?). 후보 좌표는 그대로
  `POST /what-if`에 투입 가능(테스트로 보증). 룰 순서+id 정렬 —
  우선순위 점수 없음, 제안이지 결정이 아니다.
- **W2 위험 지도 가정 실험 모드**: URL `whatif`=가정 세트 JSON 직렬화
  (링크 공유 = 가정 세트 재사용 — 저장 계약 없이). 워크벤치 패널 =
  적용 중 가정 바스켓(≤10, 개별 제거·모두 해제) + 후보 목록([추가],
  week-delta 입력) + 신규 이슈 주입 폼(제목/시나리오·IP 칩/심각도 —
  지도 행·열 재사용). 지도 오버레이: 변경 셀·종합만 투영 등급 + 점선
  링(`--warn`) + "기준→투영 (가정)" title. 배너 "N개 가정 적용 중 —
  실데이터 아님". as-of와 상호 배타(설계 18 §4).
- 검증: backend 273 / ruff / mypy / validate-data 오류 0 / frontend
  build·34 tests·lint / 실서버 확인(후보 15건 도출, 2가정 조합 오버레이,
  URL 재현). 판정 룰·저장 계약 무변경.

## 디지털 트윈 데모 가이드 — 시간·프로세스·가정 실험 (2026-07-16)

> 코드 무변경 — 문서·샘플 데이터만. 설계 16·17 기능 전체를 실사용 흐름으로
> 시연하는 재현 가능한 데모.

- **`docs/demo-digital-twin.md`**: 2주 반입 스토리(수상한 종결 + 무효가 된
  해결) 위에서 프로세스 신호 → 시점 재구성 → 가정 실험 → KPI 시계열 4장면
  진행 대본. 배너/배지/판정 문구는 전부 실서버 실행 값으로 검증해 기록.
- **`samples/demo_twin_w52_issues.csv` / `demo_twin_w52_kpi.csv` /
  `demo_twin_w53_issues.csv`**: 데모 반입 배치 2주치 — 재개(역행)·단계 건너뜀
  전이, 검증 없는 종결, dou_power W26/W20 관측을 만든다.
- 검증: 데모 전용 DB(soc_demo, db-init+db-seed 559건)에서 전 장면 실행 —
  P1 재개 신호/Q1 전이 판정(건너뜀·역행)/P2·Q3 as-of 3시점(중간→높음→중간,
  당시 없음 4건 배너)/P4·Q2 what-if 4종 delta/P3·Q4 KPI 차트 2시리즈(반입
  점 포함) 모두 API·실브라우저 UI에서 확인. 운영 DB(soc_ontology) 무변경.

## Digital Twin 후속 2라운드 — 프로세스 전이 모델·what-if 확장·as-of 확대·KPI 차트 (2026-07-16)

> 설계: `internal_docs/design/17_digital_twin_round2.md`. 설계 16의 잔여 갭 4건 —
> 공통 원칙(결정론/쓰기 경로 신설 없음/수치 점수 금지/가정 상한) 승계. Q1~Q4 커밋.

- **Q1 프로세스 전이 모델** (`0bb9f04`): `process_model.py` — issue_status 전 값을
  5단계(접수/분석/우회/해결/종결)로 사상하는 명시 계약 + 전이 판정
  (2단계 이상 전진=**단계 건너뜀**, 후퇴=**역행**(종결발은 재개 참조), 모델 밖
  상태=**미등재** — 침묵 금지). `RCAChain.transition_findings` + 전이 타임라인
  판정 배지. normal은 미포함(잡음 방지), 이력 없으면 빈 목록(하위 호환).
- **Q2 what-if 가정 확장** (`b539b2d`): 가정 4종 — 기존 2종 + **new_issue**
  (미존재 id 강제, 시나리오/IP 실재 검증, confidence=low 주입, overlay에만 존재)
  + **issue_week_shift**(due_week 이동, 없으면 400). 신규
  `changed_issue_signals` delta — 주차 기반 신호(상태/정체/지연/검증) 변화 +
  가정 이슈 등장 표시 (룰은 RCAService 재사용). UI 패널에 이슈 신호 변화 섹션.
- **Q3 as-of 확대** (`ba53c16`): `GET /as-of/portfolio/overview`,
  `GET /as-of/change-impact` — snapshot 재사용 + 기존 서비스 재계산, 오류 계약
  동일. UI는 포트폴리오에 시점 재구성 컨트롤+배너 (변경 영향 as-of는 API만 —
  범위 결정).
- **Q4 KPI 시계열 차트** (`1642cd1`): 라이브러리 없는 inline SVG 멀티시리즈
  라인 — dataviz 검증 팔레트(`--chart-1..4`, 라이트/다크 surface 각각
  validate_palette.js PASS), 범례+끝점 직접 라벨+title 툴팁+한국어 aria-label,
  표 유지(표가 계약). KPI 선택기 = primary ∪ 관측 존재 KPI(건수 병기, 관측
  우선 기본 선택). 실서버 렌더 확인 (라이트/다크, 1·2시리즈).
- 검증: backend 269 passed(신규 test_process_model 4 / what-if +4 / API +1) /
  PG soc_test 16/16 / ruff / mypy / validate-data 오류 0 / frontend 34 tests ·
  build · lint / openapi+gen:api 재생성. 한국어 전용 게이트의 화살표 함수
  오탐 1건은 식 재배열로 해소.

## Digital Twin 갭 후속 4패키지 — as-of·프로세스 신호·KPI 시계열·what-if (2026-07-15)

> 설계: `internal_docs/design/16_digital_twin_followups.md`. 시간 모델 T1+T2가 놓은
> 시간축 위의 4개 능력 — 전부 결정론, 쓰기 경로 신설 없음, 수치 점수 금지,
> 가정은 assumption+confidence≤medium. 패키지별 커밋 (P1~P4).

- **P1 프로세스 신호** (`eed9c2e`): `IngestWriterProtocol.collection_versions`
  (컬렉션 단위 1회 조회 — N+1 금지, P2와 공유) + `RCAService(versions=)` —
  **재개**(closed→open 전이, 전이 근거 문구) / **전이 기반 정체**(28일 무활동,
  기준=로그 최신 recorded_at — 벽시계 불사용). 버전 소스 없는 fixture 환경은
  주차 기반 판정으로 폴백. UI: 이슈 목록 재개 배지 + RCA 재개 배너.
- **P2 T3 as-of 재구성** (`9af20d9`, 설계 15 §4.4 잔여 해소): `AsOfService.snapshot(ts)`
  — transaction time 재생 규칙 4종(버전 없음=캡처 이전 가정 / ts 이전 최신 적용 /
  created 이후=제외 / updated 첫 버전=근사) + `AsOfMeta` 정직성 메타(가정·근사·제외
  건수 명시). `GET /as-of/risk/heatmap?ts=` — 판정 룰은 RiskService 재사용
  (기존 읽기 경로 무변경). UI: 위험 지도 시점 재구성 컨트롤 + 배너.
- **P3 KPI 시계열** (`12902b6`): **`KPIObservation` 계약 신설** (event 모듈 —
  CLAUDE.md §2.3 계약 드리프트 해소, JSON Schema 재생성) + glossary/무결성 검사/
  U1 값 커버리지 게이트. fixture: U(실리콘 실측) vs V(에뮬레이터 예측)
  dou_power·ddr_bw 10점. 반입 매핑 `kpi_observations`(왕복·rollback 검증).
  `KPISeriesService`: 마일스톤 상대 주차 정렬(비정렬 사유 명시) + direction 기준
  추세 **사실 서술**. `GET /kpi/catalog`·`/kpi/series` + 시나리오 상세
  주차×프로젝트 표. 운영 DB 재시드로 반영(시드 멱등 — 신규 10건만 버전 기록).
- **P4 what-if 주입** (`383c1f8`): `POST /what-if` — 가정 2종(issue_status/
  event_schedule_signal, VALUE_LABELS 등재 값만)을 **ephemeral overlay**에 적용해
  RiskService로 재계산, baseline 대비 등급 변화만 반환 (저장소 절대 불변,
  SimulationRun 미사용). 모든 가정은 assumption 지위+confidence medium 상한 에코,
  변화 없음도 명시. UI: 이슈 상세 1클릭 "해결되면?/다시 열리면?" 가정 실험 패널.
- 부수 교정: PG 패리티 테스트의 고정 id가 append-only 로그 누적으로 재실행 시
  실패하던 결함 → 실행별 고유 id로 수정 + collection_versions PG 패리티 단언 추가.
- 검증: backend 260 passed(신규 test_process_signals 5 / test_as_of 5 /
  test_kpi_series 5 / test_what_if 6 + API 5건) / PG 게이트 soc_test 16/16 /
  ruff / mypy / validate-data 오류 0 / frontend 34 tests · build · lint /
  openapi+gen:api 재생성. `test_no_write_endpoints`에 what-if 연산 예외 등재.

## 시간 모델 T1+T2 — append-only 버전 로그 + 전이 조회 (2026-07-14)

> 설계: `internal_docs/design/15_temporal_model.md` (digital twin 갭 분석에서 도출).
> J2 upsert가 갱신 시 이전 상태를 파괴하는 문제의 비가역성 때문에 Stage 19
> (JIRA 실동기화) 전에 캡처 계층을 선행 배치.

- **`object_versions` append-only 로그 (마이그레이션 0006)**: 쓰기 관문에서 변경
  시점마다 전체 payload 스냅샷 + `changed_fields`를 적재. 온톨로지 컬렉션이 아니라
  감사 인프라(agent_runs 지위) — UPDATE/DELETE 없음, rollback도 로그를 지우지 않는다.
  시간 축 분리: `recorded_at`=transaction time(twin이 알게 된 시각),
  `source_updated_at`=원천 주장 시각(optional) — domain time(week)과 합치지 않는다.
- **캡처 3관문**: `ingest_rows`(신규→created/갱신→updated, **변동 없음은 기록 안 함**
  — 로그가 실제 변경량에 비례) / `rollback`(제거 객체마다 retracted, payload 없음 —
  rollback 의미론 자체는 불변) / `db-seed`(payload가 기존과 다를 때만 — 재시드 멱등).
  changed_fields는 upsert가 이미 갖고 있는 신구 payload 비교의 부산물(추가 조회 0).
- **`IngestWriterProtocol` 확장**: append_versions / latest_version_numbers /
  list_versions / owned_object_keys — Memory·Postgres 패리티 (rollback 후 재반입은
  버전 번호를 이어감: created v1 → retracted v2 → created v3).
- **전이 조회 (T2)**: `GET /api/v1/history/{collection}/{id}` (읽기 전용 — 버전 목록 +
  status 전이를 조회 시점에 결정론 추출, retracted 이후 재생성의 from_status 미승계) /
  CLI `history` / 이슈 상세(RCA)에 "상태 전이 타임라인" 섹션(이력 없으면 숨김) /
  `VALUE_LABELS.change_kind`(생성/갱신/철회).
- **범위 외(별도 승인)**: T3 as-of 파생 뷰 재구성, rollback→이전 상태 복원,
  JIRA changelog 백필, relations/semantic_chunks 투영 버전.
- 검증: backend 235 passed(신규 test_history.py 9건 + API 3건 + PG 게이트 2건 —
  soc_test DB에서 11/11) / ruff / mypy / validate-data 오류 0 / frontend 34 tests ·
  build · lint / openapi+gen:api 재생성. 운영 DB에 0006 적용 완료.

## 데모 스토리 8K30 재앵커 (2026-07-13)

- **데모 스토리 4장면을 8K30 Recording KPI 스토리라인으로 재작성**: 기존 장면 1이
  "최상단 붉은 행 = UHD60"이라 안내했으나 실제 U 과제 heatmap 최상단은 8K30
  (등급 동률 시 이름순 정렬 — Stage 12 작성 시점부터 불일치, 커밋 `8d27c2c`에서
  재계산으로 확인). 장면 2=`issue_mfc_8k30_bitrate_latency_u` RCA(검증 노드 red),
  장면 3=MFC `NAL Queue mode` 변경 영향(장면 2 원인 후보와 직결, 시나리오 3/KPI 12),
  장면 4=8K30 thermal evidence 질문(인용 5건 전부 8K30 관련, unmatched 0).
- **장면 연결 고리 문구 보강**: 장면 1 "MFC 셀 클릭 → 미해결 인코딩 이슈",
  장면 2 "원인 노드 후보 NAL queue batching 확인", 장면 4 "thermal soak 실패 +
  미확보 근거 → '아직 해결로 판단할 수 없다'는 결론까지 근거로" — 장면 간
  인과가 배너 문구만으로 이어지도록.
- **`docs/demo-story.md` 신설**: 진행자용 4장면 대본(보이는 것/할 것/전달 포인트/
  진행 팁) — index 링크 추가. 이번 주 주목의 8K30 thermal P1 요청 노출을 fixture로
  검증하고 기재.
- Ask 프리셋 5종(원점 TAT 기준 질문)은 데모 경로와 독립이라 무변경.

- **임베딩 provider 계약**: Fake(결정론 해시 bag-of-tokens — 사외/테스트) /
  OnPrem(OpenAI 호환 /embeddings — 사내 검증 대상). 기본 비활성(SOC_EMBED_PROVIDER).
- **인덱스**: `embed-chunks` CLI(멱등 — 같은 모델 재실행 시 유지), 저장은 기존
  `semantic_vectors` 계약(JSONB). pgvector 네이티브 인덱스는 사내 규모 확인 후.
- **Ask 하이브리드**: 키워드 카드에 벡터 후보 청크 최대 3장 합류 — 상태에
  "문서 후보 · 증거 아님(유사도)" 명시, 인용 관문·검증 규칙 불변, 임베딩
  미구성/실패 시 완전 하위 호환(키워드만).
- compose/.env/runbook에 임베딩 설정 반영. 사내 후속: 임베딩 모델 지정만.

## D2 문서 재정비 + 사내 핸드오버 킷 (2026-07-12)

- **스크린샷 전면 재캡처(9장)**: 재설계된 화면 기준 — 위험 지도(타일·카테고리·근거
  패널)/변경 영향(전파 지도·체크리스트)/이슈 분석(상황판·미니맵·검증 케이스)/
  Ask(각주·캐시·FAQ 신규)/반입 센터 신규. URL=상태 설계 덕에 headless Chrome으로
  전 장면 재현·캡처(재캡처 자동화 가능해짐).
- **가이드 갱신**: `docs/ingest.md` 신설(4단계 흐름·품질 3지표·보류 풀·롤백),
  ask.md(각주/프리뷰/FAQ/캐시), risk-map.md(카테고리 그룹·스플리터·URL 공유),
  issues.md(상황판·미니맵·정체/지연), index 링크.
- **사내 핸드오버 킷**: `internal_docs/ops/handover.md` — 보안·계정 체크리스트,
  JIRA 필드 매핑 워크시트(6항목), 도입 1~2주차 플랜과 성공 판정 기준.

## D1 운영 배포 패키지 — Stage 14 잔여 (2026-07-12)

> 사내 도입의 마지막 기술 관문: 인증/로깅/배포 정의/동기화 운영/runbook.
> 커밋 단위: D1-1 / D1-2 / D1-3+4 / D1-5.

- **D1-1 API 토큰 인증**: `SOC_API_TOKEN` 설정 시 /health 제외 전 API Bearer 관문
  (hmac 상수시간, env 요청 시점 읽기). 프론트 openapi-fetch 미들웨어 자동 주입 +
  401 토큰 게이트 오버레이. 미설정=개발 모드(기존 무변경).
- **D1-2 구조화 로깅**: `soc.access`/`soc.error` JSON 라인(stdout) — 경로/상태/
  소요 ms, 토큰·본문 비기록. 감사 3종과 역할 분리.
- **D1-3 배포 정의**: `deploy/` compose(pgvector+api+nginx)·Dockerfile 2종·
  .env 템플릿 — 보안 기본값(외부 LLM 차단, API 미노출). 기동=마이그레이션 자동.
  클린 스택 리허설 통과(빌드→기동→인증/시드/로그 검증→철거).
- **D1-4 동기화 운영**: `sync-status` CLI — 소스별 마지막 완료·카운트·보류 건수.
- **D1-5 runbook**: `internal_docs/ops/runbook.md` — 설치/LLM 정책/주기 동기화
  (cron)/백업/복구·rollback/업그레이드/트러블슈팅.

## Backend B1~B5 — 사내 실운영 갭 교정 (2026-07-12)

> 목적 대비 재검토 결과: 분석 계약(4질문)·evidence-grounded는 충실하나 운영 축에
> 차단급 갭. 커밋 단위: B1~B5.

- **B1 정책 준수**: Ask 경로가 `allow_external_llm`을 우회하던 문제 수정 —
  `apply_external_policy` 공용 관문으로 Advisory와 통일 (확정 결정사항 1).
- **B2 DB 연결 계층**: 단일 공유 커넥션 → `psycopg_pool`. ConnectionSource 계약
  (Pooled/Single 어댑터), 4개 스토어 호출 단위 대여/commit/반납. 해소: 동시 요청
  직렬화·DB 재시작 전면 장애·idle-in-transaction. 실검증: 8병렬 균일 응답,
  docker restart 자동 복구, idle-in-tx 0건.
- **B3 행동·피드백 재진입**: action_items 매핑+GET+리뷰 센터 왕복(액션 CSV) —
  4질문의 '행동' 완결. §2.2 피드백 루프 배선: `RoleAdvisory.feedback_items`
  (프롬프트 지시 + validator 강제: HW/SW 발신·SE/Arch 수신·근거 필수) + 화면 노출.
- **B4 LLM 캐시**: 캐시 키=정규화 질문+카드 지문(id+상태 해시) — 데이터 변경 시
  자동 무효화. cached=True·원 질의 시각 명시(감사), FAQ 횟수 포함,
  `SOC_ASK_CACHE=false` 비활성.
- **B5 스케일·CI**: 목록 6종 limit/offset(하위 호환), CI postgres-integration job
  (pgvector 컨테이너) — PG 게이트 테스트 상시 실행.

## UI E1~E6 — 탐색 화면 6종 폴리싱 (2026-07-12)

> 확립된 문법(상황판 숫자 카드=필터, 세그먼트 막대, URL=상태, 값 한국어화,
> 화면 간 연동)을 탐색 계열 전 화면에 일관 적용. 커밋 단위: E1~E6.

- **E1 포트폴리오**: 주의 항목 106건 레인 상황판(클릭=필터)·과제 카드=필터·
  `project_phase` 한국어화·매트릭스 근거 공백 우선 정렬.
- **E2 시나리오 목록**: `scenario_domain` 한국어 칩(건수)·검색·위험 지도 종합
  등급 배지 + IP/시스템 수 — 목록 단계 우선순위 판단.
- **E3 리뷰 센터**: 주간 상황판(이벤트/활동/요청)·일정 위험 신호 배지·리뷰 팩
  섹션 전 항목 열람(details)·결정 CSV 파일 다운로드·업로드 4카운트.
- **E4 근거 탐색**: 신뢰 사다리 구간/범례 클릭=강도 필터(시각화가 곧 필터)·
  가용성 칩 건수·제목 검색·URL=상태.
- **E5 출처 지도**: 상황판·컬렉션 32행을 한 줄(제목|막대|건수) 밀도로(범례 1회,
  건수순)·`ip_domain` 한국어화(11종).
- **E6 데이터 반입**: 이력 4카운트+반입 시각·매핑 한국어 라벨·①~④ 진행 안내.
- VALUE_LABELS 신규 3도메인(project_phase/scenario_domain/ip_domain) 전부
  커버리지 게이트 편입.

## Ask SoC A1~A5 — 한국어 검색·인라인 인용·즉시 프리뷰·Q&A 로그 (2026-07-12)

> 진단: 한국어 도메인 용어 질문이 검색을 통과하지 못함(실측 — "전력 문제 IP" →
> 무관한 면적 카드), 인용이 문장과 분리, 20초 빈 대기, 질문 기록 부재.

- **A1 한↔영 도메인 브리지**: 큐레이션 용어 그룹 24종(전력↔power, 발열↔thermal…)
  전 방향 확장 + 범용 토큰(ip/scenario 등) 가중 하향·단독 매치 배제 +
  미매치 의미 토큰 보고(질문 개선 힌트).
- **A2 인라인 인용**: 답변 문장 끝 `[id]` 마커 계약 — 검증 관문이 카드 밖 마커를
  거부, 본문 마커는 citations에 합류. 프론트는 각주 번호 칩으로 렌더링,
  클릭=우측 카드 하이라이트 (실서버 검증: claude_cli 답변에 마커 포함 확인).
- **A3 즉시 프리뷰**: `GET /ask/preview`(결정론 카드) — 제출 즉시 카드 표시,
  답변은 스켈레톤 후 교체. confidence 한국어 라벨(B2 잔존 정리), 결정론 폴백
  배지 노랑 구분, 소요 시간 표기.
- **A5 Q&A 로그 + FAQ** (사용자 요청): `ask_log`(마이그레이션 0005 —
  AgentRun과 같은 감사 기록 지위, POST /ask 내부 기록·신규 쓰기 API 없음).
  `GET /ask/history`/`GET /ask/faq`(정규화 질문 집계). 대기 화면에
  자주 묻는 질문(횟수·답변 미리보기)·최근 질문 — 클릭=재질의, 좋은 예제 목록의 원천.
- **A4 레이아웃**: 답변(좌)|근거 카드(우) 스플리터 — 위험 지도·변경 영향과 동일
  문법. (수정) I2의 effect 내 setState lint 오류 — 렌더 중 리셋 패턴으로 교체.

## UI I1~I3 — 이슈 분석 재설계: 상황판 + RCA 미니맵 (2026-07-11)

> 사용자 피드백: 정보는 많은데 시각화가 부족해 한눈에 안 들어옴. 진단: 집계 제로 /
> 체인이 체인처럼 안 보임 / 위계 부재. 커밋 단위: I1 / I2 / I3.

- **I1 이슈 상황판**: 숫자 카드(전체/검증 없는 종결/미해결/정체·지연 — 클릭=필터,
  `?flag=`) + 유형별 가로 세그먼트 막대(길이=건수, 색=검증 상태 3분해, 클릭=유형
  필터 `?type=`). 검증 필터를 클라이언트로 옮겨 칩·상황판 카운트가 항상 전체 분포.
- **I2 RCA 미니맵**: 7단 가로 스텝퍼(노드 색=근거 뱃지, 빨강 링 강조) — 끊긴
  고리가 한눈에, 클릭=해당 스텝 펼침+이동. 정상(초록) 스텝은 한 줄 요약으로 접힘,
  문제(빨강)는 배경 틴트, 경고는 전폭 배너 승격. 전체 펼치기/접기.
- **I3 목록 밀도**: `IssueSummary.severity` 추가(백엔드) — 심각도 도트 +
  연결 시나리오 수 표기로 목록 단계의 우선순위 판단 지원.

## 반입 J1+J2 — 사내 데이터 현실 대응: 품질 리포트 + 증분 동기화 (2026-07-11)

> 사용자 관찰(사내 JIRA: 라벨/상태 미정비·다과제 공통·그룹별 인스턴스·대량·주기적
> update) 기반 갭 교정. 설계: `internal_docs/design/14_ingest_reality_gaps.md`.

- **J2 upsert 의미론 통일**: 같은 id 재반입 시 신규/갱신(내용 변경 교체)/변동 없음
  (쓰지 않음, 계보 유지) 3분류 — 같은 JIRA 키·Confluence URL의 주기적 update에서
  바뀐 것만 쓴다. in-memory 중복 축적 버그 해소(Postgres UPSERT와 패리티).
  배치에 `updated_count`/`unchanged_count`(DB 스키마 불변 — payload에서 복원).
  rollback 의미론 재정의: 배치가 현재 소유한 객체만 제거(설계 문서에 명문화).
  배치 내 중복 id는 마지막 행 적용(앞선 행 거부 보고).
- **J2 증분 동기화**: `sync-jira --since auto|<ISO>`(배치 이력에서 마지막 완료 시각
  유도 → `updated >=` JQL 결합), `JiraHttpClient` startAt pagination,
  `--env-prefix`(그룹별 인스턴스 분리).
- **J1 반입 품질 리포트**: 매핑에 선언적 검사 메타데이터(label_domains/ref_checks/
  linkage_fields) → 배치마다 라벨 미등재 값·참조 무결성 경고·**온톨로지 연결률**
  (시나리오/IP 미연결=화면에 안 나타나는 죽은 데이터) 보고 — 경고이지 거부 아님.
  반입 센터: 신규/갱신/변동 없음 카운트 + 품질 섹션 + 거부 행 CSV 내려받기(큐레이션
  루프 1단계). CLI 출력 동일 체계.
- **J3 신선도·일정 신호** (같은 날 후속 승인): `Issue.updated_week`/`due_week`
  (optional — 56 유래 무변경), field map `week_columns`(JIRA 날짜→ISO 주차),
  결정론 룰 — 기준 주차=데이터 최신 활동 주차(벽시계 없음), 미해결+4주 무활동=정체 /
  목표 주차 경과=지연 (판정 근거 주차를 문구에 명시). 이슈 목록 정체/지연 배지.
- **J4 이슈↔문서 연결**: `Issue.doc_refs`(외부 문서 URL/키), `SemanticChunk.
  related_issue_ids`(페이지가 언급하는 이슈 키 — Confluence `issue_keys` 반입).
  RCA 상세에 "관련 문서 후보(증거 아님)" 섹션 — 후보 지위, 증거 승격은 큐레이션.
- **quarantine 보류 풀 (J1 2단계, 같은 날 후속 승인)**: 거부 행을 원본 열 값
  그대로 저장(`ingest_quarantine` — ingest 스테이징, 온톨로지 아님). 반입 센터
  "큐레이션 대기열" 카드 — 매핑별 수정용 CSV(원본 값+사유), 같은 id 재반입 성공 시
  자동 해소, 원 배치 rollback 시 함께 제거. `GET /ingest/quarantine`(읽기 전용),
  마이그레이션 0004. 실서버 왕복 검증(거부→보류→수정 재반입→해소).
- **범위 외(미착수)**: upsert 버전 이력, 다과제 project_ids 복수화 — 설계 문서 §4.

## UI G1~G3 — 변경 영향 재설계: 영향 전파 지도 (2026-07-11)

> 사용자 피드백: 전파 경로가 텍스트 목록으로 흩어져 그래프가 안 보임, 폼이 기계적.
> 커밋 단위: G2(빌더·요약) / G1+G3(그래프·패널·재편) / 마무리(docs·데모·스케일).

- **G2 문장형 질의 빌더**: 셀렉트 나열 → "[IP]의 [knob]·[기능]을 [모드]에서 바꾸면?"
  문장 폼(미선택="전체"). 결과 상단 계기판 요약 스트립(클릭=섹션 이동).
- **G1 영향 전파 지도**: `ImpactFlow` — 연쇄 IP ↔ 분석 대상 → 시나리오 → KPI 계층
  그래프(순수 SVG, 신규 의존성 없음). 간선=근거 규칙 색(IP 요구/knob 관련/사용·의존),
  knob 직접 KPI 점선(★), 의존 방향 화살표, hover 경로 강조, 열당 상한 18(근거 많은 순).
- **G3 재편**: 노드 클릭 → 우측 근거 패널(`?node=` URL 상태), 시나리오/KPI/연쇄 카드를
  그래프+패널로 흡수, 하단 체크리스트+유사 사례 2열. 스플리터 공용 컴포넌트
  (`SplitLayout`) 추출 — 위험 지도와 동일 상호작용 문법. axe 게이트에 화면 추가,
  `docs/change-impact.md` 전파 지도 기준으로 개정.

## UI W1~W3 — 유동 폭 + 열 카테고리 구분 + 코크핏 시각 정체성 (2026-07-11)

> 사용자 피드백: heatmap 수평 스크롤 제거(브라우저 크기 추종), IP/시스템 블록 열 구분,
> "정석적인 AI 생성 느낌" 탈피 — 직관적·fancy하게. 커밋 단위: W1 / W2 / W3.

- **W1 유동 폭**: `.app-main` 1200px 상한 제거, 유동 패딩(clamp). 긴 산문(ask 답변)만
  80ch 가독 상한. 근거 패널 400px.
- **W2 열 카테고리 구분**: `VALUE_LABELS`에 `ip_category` 도메인(커버리지 테스트 편입).
  heatmap thead 2단 — 카테고리 그룹 행(기능 MM IP/컴퓨트 IP/시스템 영향 블록) +
  경계 구분선 + 열 배경 틴트(반투명, 행 hover 투과 / sticky 헤더는 color-mix 불투명 /
  다크 이중화).
- **W3 코크핏 시각 정체성**: 셀=등급 소프트색 채움 타일(심볼 병행 — 색약 대응,
  종합 열은 링 강조), 팔레트 교체(차가운 종이톤 배경 + 딥 인디고 악센트), 양 테마 공통
  다크 슬레이트 헤더 + 히트맵 모티프 브랜드 마크(SVG), 카드 그림자·계기판 레이블
  타이포 위계. 위험색 의미(빨/노/초)·수치 점수 금지 등 불변 원칙 유지.
- **W3+ 스플리터**: 위험 지도 테이블↔판정 근거/이번 주 주목 패널 폭 드래그 조절
  (좌우 화살표 키·더블클릭 초기화, 300~680px, localStorage 유지, 좁은 화면 숨김).

## UI 실사용자 재설계 P0~P2 — 운영 루프 완결 + 신뢰 품질 (2026-07-11)

> 설계: `internal_docs/design/13_ui_operational_redesign.md` (실구동 관찰 기반).
> 커밋 단위: P0-1(신뢰 품질) / P0-2(운영 루프 UI) / P0-3(URL·스케일) / P1(사용성·접근성) / P2(마감).

### P0-1 신뢰 품질

- 실행 초안 중복 텍스트 제거(B1), risk/portfolio/action_draft/ask 조립 문장의
  원문 코드·id 나열 은닉(B2 — 라벨 사용, id는 source_refs 추적 유지, 가드 테스트),
  역할·evidence_type 라벨 도메인 신설. `PostureChip` — 태세를 위험색과 분리(B3).

### P0-2 운영 루프 UI

- **반입 센터**(`/ingest`): 업로드·거부 사유·rollback·템플릿 CSV — 기존 ingest API의
  화면화(신규 쓰기 없음). `GET /ingest/mappings`·`GET /decisions` 읽기 추가.
- 리뷰 팩에 결정 CSV 반입 존 + 팩 결정 목록 — 내보내기→회의→재진입 한 화면 왕복.

### P0-3 URL=상태 + 스케일

- 위험 지도 `?project=&grade=&cell=`, 이슈 `?project=&verification=&q=`, 변경 영향
  역동기화+실패 피드백. 이슈 텍스트 검색(debounce), heatmap sticky(시나리오 열+헤더),
  등급 표시 필터, 종합 열 구분, 범례 이동. URL 재현 테스트.

### P1 사용성·접근성

- 리뷰 센터: 데이터 있는 최신 주 기본, 주차 칩 건수 병기+최근 8주 접기(A3).
- `<Busy>`(스피너+경과 초) — Ask/advisory/변경 영향, 제출 비활성, aria-live(C3).
- 폼 언어(제어 항목/기능, C4). focus-visible 토큰, select 라벨 연결, heatmap 셀
  aria-label, AskCard `status_kind` 계약 필드(한국어 substring 파싱 제거 + 상태 라벨화),
  **axe-core smoke 3화면 serious/critical 0 게이트**(D).

### P2 마감

- 다크 모드(prefers-color-scheme 변수 이중화 + color-scheme), Ctrl/Cmd+K → Ask,
  tabular-nums, 리뷰 활동 역할 배지 한국어.

### 검증

```text
backend 192 passed / 9 skipped · ruff · mypy(61) pass. frontend build / test(29:
axe smoke 3·URL 재현·CSV 계약·훅) / lint 0. E2E(실서버 8155/5275 + PostgreSQL):
반입 센터 업로드 3건→rollback, URL 재현(project/grade/cell → 셀 하이라이트+패널),
이슈 ?q=DPU 5건, 리뷰 센터 W52 기본, 실행 초안 중복 0·코드 노출 0 화면 확인.
```

## 사내 실운영 준비 Phase 4 — U1 값 한국어화 + 위험 지도 근거 태세 (2026-07-11)

> 06_stage16_ui_overhaul.md U1을 Stage 16에서 앞당김(사내 첫인상 + 반입 신규 값 게이트)
> + 백로그 §4 "위험 지도 근거 태세 확장" 실현.

### 추가

- **U1 값 도메인 한국어화**: `glossary.VALUE_LABELS` 계약 신설 — 17개 값 도메인
  (issue_status/issue_type/fix_type/severity/test_type/test_result/event_status/
  schedule_signal/availability/confidence_contribution/measurement_stage/scenario_match/
  request_status/request_priority/requirement_level/direction/support_status).
  - **fixture 전 값 커버리지 테스트** (`test_glossary`): CSV/JIRA 반입으로 새 값이
    들어오면 라벨 누락이 테스트로 드러난다 (JIRA value_maps와 연동 게이트).
  - `GET /meta/glossary`에 `value_labels` 포함, frontend `useValueLabels` 훅 —
    표시는 한국어, 원문 코드는 hover(title)만. 적용: 이슈 목록/RCA 헤더(유형·상태),
    이벤트 심각도·상태(리뷰 센터/이벤트 탭), 요청 우선순위·상태, 근거 가용성
    (필터 칩 영어 하드코딩 D1 해소), 변경 영향 과거 사례 상태. 미등재 값은 원문 폴백.
- **위험 지도 근거 태세 배지**: `ScenarioRiskRow.evidence_posture` — 시나리오 행에
  실측/예측/부재 건수 배지(hover에 정성 판정) + 판정 근거 패널에 태세 문장.
  `EvidencePosture`/`scenario_posture`를 `evidence_ladder.py`로 승격(action_draft와
  risk가 공유 — 중복 계약 제거). 건수·정성 판정만, 수치 점수 없음(§6.3).
- docs/risk-map.md에 근거 태세 배지 해석 가이드 추가.

### 검증

```text
backend 188 passed / 9 skipped · ruff · mypy(61) pass · validate-data 오류 0 ·
frontend build / test(25) / lint 0. E2E(TestClient): value_labels 17 도메인,
위험 지도 23행 중 14행 태세 표시(예: 8K30 → 실측1·예측2·부재1 "예측 비중 높음").
```

## 사내 실운영 준비 Phase 3 — JIRA/Confluence 커넥터 사외 선행분 (2026-07-11)

> 설계: `internal_docs/design/12_jira_connector.md`. Stage 19의 사외 가능 부분을 앞당김 —
> 커넥터 아키텍처·매핑·테스트를 fixture/mock으로 완성. 사내 후속: 보안 승인·실 자격증명·
> 실 스키마 매핑 값·주기 실행.

### 추가

- **`backend/connectors/`**: `JiraClientProtocol`/`FakeJiraClient`(fixture payload)/
  `JiraHttpClient`(env 기반 얇은 실 클라이언트, 비밀은 환경변수만). **필드 매핑은 설정
  YAML**(`jira_field_map.yaml`: dotted 경로 + value_maps 값 정규화 + constants) — 사내
  스키마 확정 시 코드 수정 없이 교체. Confluence 페이지 → `SemanticChunk` **검색 후보**
  반입(`semantic_chunks` 매핑 신설, 증거 지위 아님 §3).
- **커넥터는 ingest 경유만**: `IngestService.ingest_rows(origin, row_refs)` 일반화 —
  CSV와 커넥터의 공용 경로. `origin=integrated`, 계보는 rollback 접두를 유지하며 외부
  키 합성(`import:<batch>:jira:<KEY>`). CSV 경로 동작 불변(기존 테스트 회귀 고정).
- **CLI**: `sync-jira --payload <fixture>|--jql <실서버> [--mapping-file] [--execute]`,
  `sync-confluence --payload`. 기본 dry-run(비영속 검증), `--execute`는 PostgreSQL DSN 필수.

### 검증

```text
backend 185 passed / 9 skipped · ruff · mypy(61) pass · validate-data 오류 0.
test_connectors 7케이스(정규화/값맵/커스텀 YAML/integrated 계보/위험 지도 반영/rollback).
E2E(CLI): sync-jira dry-run 3건 수용 · sync-confluence dry-run 2건 수용 · 인자 누락 거부.
```

## 사내 실운영 준비 Phase 2 — 결정 재진입 B3b (2026-07-11)

> 설계: `internal_docs/design/11_decision_reentry.md`. 원점 4층 루프(review→decision)를
> **ingest 경로로** 닫는다 — 리뷰 팩 결정 CSV를 사람이 채우면 `Decision`으로 재진입.

### 추가

- **`decisions` 반입 매핑**: 결정 CSV의 채워진 행 → `Decision` (행당 결정 1건,
  `supporting_basis` 단일 근거 조립). `결정` 빈 행은 한국어 사유로 거부 보고(의도된 동작).
  `Decision.event_id` 필수는 온톨로지 무변경으로 해소 — 리뷰 회의를 `development_events`
  매핑으로 먼저 반입하고 CSV에 `회의 이벤트 ID` 기입.
- **결정 CSV 템플릿 v2** (`toDecisionCsv`): 결정 ID 제안(`decision_<팩>_r<n>`)·프로젝트
  ID(단일 프로젝트 팩)·근거 유형·확신도(medium) 시스템 프리필. 헤더 계약을 backend/
  frontend 양쪽 테스트로 고정(`test_decision_csv_template_matches_mapping_contract` ↔
  `ReviewPackCsv.test.ts`). `담당/상태`는 회의 기록용(미반입 — ActionItem 반입은 후속).
- 샘플: `sample_decisions.csv`(거부 확인용 결정 없는 행 포함), `sample_events.csv`에
  리뷰 회의 이벤트 추가.

### 변경

- **traceability 시작 시 스냅샷 제거** (`resolve/traceability.py`): 링크 그래프·인덱스를
  호출 시점에 조립 — 반입 객체(결정·이슈 등)가 **재시작 없이** traceability에 반영된다
  (B3b에서 발견된 기존 한계). 파일럿 규모 저비용, 대규모 캐시는 Stage 14 항목.

### 검증

```text
backend 178 passed / 9 skipped · ruff · mypy(58) pass · validate-data 오류 0 ·
frontend build / test(24) / lint 0. E2E: 회의 이벤트+결정 CSV 반입(2 수락/1 거부)
→ 결정↔회의 이벤트·프로젝트 traceability 양방향 확인 → rollback 후 소멸.
```

## 사내 실운영 준비 Phase 0~1 — 얇은 CI + 반입 표면 확대 (2026-07-11)

> **방향 재정의(사용자)**: 목표는 워크숍 데모가 아니라 사내 실운영 + JIRA/Confluence 연동.
> 사외에서는 fixture로 구현·검증 가능한 것을 앞당긴다 — 백로그 P4 재배열 채택.
> 로드맵: Phase 0(CI) → 1(반입 확대) → 2(B3b 결정 재진입) → 3(커넥터 사외 선행분) →
> 4(U1 값 한국어화 + 위험 지도 태세). 이번 완료분은 Phase 0~1.

### 추가

- **얇은 CI** (`.github/workflows/ci.yml`, L1 해소 착수): backend(pytest/ruff/mypy/
  validate-data) / frontend(build/test/lint) / contracts(schema·openapi·gen:api 재생성 후
  `git diff --exit-code` 드리프트 검출) 3 job. PG 통합 job은 후속 확장.
- **반입 매핑 4종** (`backend/ingest/mappings.py`, L3 해소 — JIRA 데이터 착지 표면):
  issues / tests / development_events / evidence_catalog. `convert_row`에 중첩 필드
  (점 표기, `affected_scope.scenarios`), bool 열(예/아니오), 단일 하위 객체 리스트
  (`root_causes` 1건) 지원. 샘플 CSV 4종(`samples/`, fixture 세계관 정합).
- **계약 정밀화 (L8 해소, 변경 규율 6단계)**:
  - `DevelopmentEvent.related_ip_ids`(optional) — 명시 IP 링크.
    `event_related_ips()`는 명시 링크 우선, 없으면 기존 `IPAliasIndex` 휴리스틱(동작 보존).
  - `Issue.severity`(optional) — 미해결 이슈 심각도 low/info면 중간, 그 외/무명시는
    기존대로 높음(근거 서술에 심각도 표기). fixture 무명시라 기존 등급 전부 불변.
  - 컨버터 재생성(`event.yaml`에 `related_ip_ids: []` 63건), schema/openapi/gen:api 재생성.

### 검증

```text
backend 176 passed / 9 skipped · ruff · mypy(58) pass · validate-data 오류 0 ·
frontend build / test(21) / lint 0. test_ingest 14케이스(신규 매핑 왕복 + 파생 뷰 통합).
E2E(실서버 8155): CSV 4종 반입(9건) → 위험 지도 open_issue 셀 근거 / RCA 미검증 close
빨간 경고(no_tests) / 사다리 54→56(실측·정합 1, 예측 1) → rollback 후 전부 기준선 복귀.
```

## 리뷰 팩 조립 — 결정 ← 근거 루프 (B3) (2026-07-10)

> 설계: `internal_docs/design/10_review_pack.md`. 원점 4층 루프의 review→decision 고리.
> 정의만 되고 안 쓰이던 `ReviewPack` 객체를 실제 리뷰 워크플로로 살린다.

### 추가

- **리뷰 팩 조립 파생 뷰** (`GET /api/v1/review-packs`, `/review-packs/{id}`, 리뷰 센터 상단):
  `backend/services/review_pack.py` — `ReviewPack`이 묶은 시나리오들의 실행 초안(ActionDraft)
  +근거 태세를 한 장으로 조립. 회의용 롤업(위험·이슈·근거공백 항목 + 실측/예측/부재 집계).
  - F3 ActionDraft를 시나리오 단위로 **그대로 재사용** — 중복 계약 없음. 없는 팩 → 404.
- **결정 round-trip CSV**(프론트 생성): 리뷰 팩을 결정/담당/상태 컬럼이 **빈** CSV로 복사 —
  회의에서 사람이 채우고 추후 ingest로 재진입해 `Decision`으로 추적(B3b 후속).
- 프론트: 리뷰 센터에 리뷰 팩 섹션(팩 목록 → 조립 문서 + 시나리오별 태세 배지 + CSV 버튼).
  온톨로지 무변경, GET, 결정 자동생성·owner 자동할당 없음(§6.3).

### 검증

```text
backend 168 passed / 9 skipped · ruff · mypy(58) pass · frontend lint 0 / build / test(21) pass.
test_review_pack 8케이스. E2E: pack_project_w_multimedia_review(3 시나리오)
  롤업[위험34·이슈12·공백5 · 실측7·예측2·부재4] + 404 확인.
```

## 근거 신뢰 사다리 → 결정 지점 통합 (Action Draft) (2026-07-10)

> 설계: `internal_docs/design/09_evidence_ladder.md` §7. 사다리가 근거 탐색 화면에만
> 머물면 결정 품질로 이어지지 않는다 — 결정이 일어나는 실행 초안으로 끌어온다.

### 추가

- **실행 초안에 근거 태세**(`ActionDraft.evidence_posture`): 시나리오 근거의 실측/예측/부재
  건수 + 정성 판정(예: "예측 비중이 높음 — 실측 확보 시 신뢰 상승"). `EvidenceLadderService`
  재사용. 근거 없으면 None. 카운트 비교 기반 정성 문장(수치 점수 아님, §6.3).
- **근거 수집 항목에 신뢰 등급**(`DraftItem.strength_ko`): `classify_evidence`로 각 근거 공백
  항목의 등급(실측·정합/유사/에뮬/예측/부재) 표시 — "무엇부터 실측할지" 우선순위 신호.
- 프론트: `ActionDraftTab` 상단 근거 태세 배지 + 항목별 신뢰 chip, Markdown 내보내기 반영.
  온톨로지 무변경, GET. openapi/schema.d.ts 재생성.

### 검증

```text
backend 160 passed / 9 skipped · ruff · mypy(57) pass · frontend lint 0 / build / test(21) pass.
E2E: '8K30 Recording KPI' 태세[실측1·예측2·부재1 "예측 비중 높음"] + 항목 등급 확인.
```

## 근거 신뢰 사다리 (Evidence Ladder) — P1 실현 (2026-07-09)

> 설계: `internal_docs/design/09_evidence_ladder.md`. 백로그 P1(G-3)을 원점 §5.3의
> 시맨틱 메타(evidence_level)가 아니라 **evidence_catalog에 실재하는 필드**로 재정초.
> "이 조언이 이 시나리오의 실측인가, 빌려온 예측인가"를 결정론 정성 등급으로 노출.

### 추가

- **근거 신뢰 등급 파생 뷰** (`GET /api/v1/evidence/ladder`, 근거 탐색 화면 상단 패널):
  `backend/services/evidence_ladder.py` — `measurement_stage`·`scenario_match`·
  `availability`·`is_measurement/prediction`를 규칙으로 조합해 강→약 5단
  (실측·정합 / 실측·유사 / 에뮬레이션 / 예측·설계 / 부재·미가용) 정성 분류 + 판정 근거.
  - `absent`(미가용/무정합)를 최우선으로 걸러 "없는 근거 강신뢰" 오류 차단.
  - 분포(tier별 건수) + 실측/예측/부재 3분 요약. **수치 점수·가중치·rank 없음**(§6.3).
  - `origin`(synthetic/imported/integrated) 동반 — fixture→real 전환 시 "레벨업" 훅.
- 프론트: 근거 탐색에 **신뢰 분포 패널**(세그먼트 바 + 헤드라인) + 항목별 **신뢰 등급 배지**.
  project 필터 연동. i18n `evidence_ladder` 블록, openapi/schema.d.ts 재생성.

### 검증

```text
backend 158 passed / 9 skipped · ruff · mypy(57) pass · validate-data 오류 0 ·
frontend lint 0 / build / test(21) pass. test_evidence_ladder 14케이스.
E2E(TestClient): 전체 54건 분포[실측17·예측/에뮬22·부재15],
  프로젝트별 U(실측14/예측1) · V(예측11) · W(예측10/실측3) → 성숙도 U>V>W 가시화.
```

## 후속 H1·B1 — lint 게이트 복구 + L8 귀속 통일 (2026-07-09)

> 백로그 `internal_docs/design/08_bridge_followups.md` §1·§2. Bridge를 코드 레벨에서 마무리.

### 변경

- **H1 — frontend lint 게이트 복구** (render 순수성 위반 3건):
  - `DemoStoryBar`: 씬 배너를 `SceneBar`로 분리, `key={sceneIndex}` remount로 장면별
    스톱워치를 리셋(effect 내 `setState` 제거). render 중 `Date.now()` 호출 제거.
  - `AskPage`: `question`을 URL(`?q=`) 파생으로 전환(state 이중화 제거), effect 동기화를
    render 중 previous-value 비교로 대체. `react-hooks/set-state-in-effect`·`purity` 0.
- **B1 — event↔IP 귀속 통일 (L8 완전 해소)**:
  - `IPAliasIndex`에 다중값 `resolve_all(token) -> set[str]` 추가. 한 토큰이 여러 IP에
    걸리는 경우('memory'→MIF·SMMU, 'ai'→GPU·NPU)를 보존 — 큐레이션용 단일 `resolve`와 분리.
  - `risk.py::event_related_ips`를 인덱스 기반으로 재작성, 고유 휴리스틱 `ip_match_tokens`
    폐기. `change_impact.py`도 공용 인덱스 사용. 엔티티 해석과 **단일 정규화 규칙** 공유.
  - **동작 보존**: fixture 63개 이벤트 전수 비교에서 기존 귀속과 0/63 차이 → `test_risk`
    고정 기대값 무변경. (naive `resolve` 단일 치환은 'memory'→SMMU 탈락 회귀라 기각.)

### 검증

```text
backend 144 passed / 9 skipped · ruff · mypy(56 files) pass · validate-data 오류 0 ·
frontend lint 0 / build / test(21) pass. 귀속 동등성: 63/63 이벤트 일치(사전 검증 스크립트).
```

## Bridge F3 — 실행 초안 (2026-07-09)

> 설계: `internal_docs/design/07_advisory_to_os_bridge.md` §3. 원점 비전 4층 루프
> (조언 → 실행)의 다리 — 조언 tool을 operating system으로 잇는다.

### 추가

- **실행 초안** (`GET /api/v1/action-draft/scenario/{id}`, 시나리오 상세 '실행 초안' 탭):
  `backend/services/action_draft.py` — 위험 근거·미해결/미검증 이슈·근거 공백을
  결정론으로 조립한 리뷰 팩 초안. 기존 파생 서비스(RiskService 등) 재사용.
  - 3섹션(위험 근거 검토 / 확인 필요 이슈 / 근거 수집), 모든 항목이 최소 1개 근거 동반.
  - **저장 안 함·owner 자동할당 없음** — `provenance_note`로 "사람이 검토·커밋" 명시.
    재진입은 ingest 계층으로만(CLAUDE.md §6.3). GET이라 `test_no_write_endpoints` 무영향.
  - 프론트: JSON/Markdown 복사 버튼(change_impact 복사 패턴 재사용).

### 검증

```text
backend 144 passed / ruff / mypy(56 files) pass · frontend build / test(21) pass ·
  validate-data 오류 0. openapi/gen:api 재생성. lint 기존 3건 외 신규 0.
E2E(TestClient): F1 549객체/32컬렉션, F2 별칭11/미해석23,
  F3 '8K30 Recording KPI' 섹션[위험8·이슈1·근거공백2] + 404 동작 확인.
```

## Bridge F2 — 엔티티 해석 (2026-07-09)

> 설계: `internal_docs/design/07_advisory_to_os_bridge.md` §2. 원점 비전의 "식별자
> 파편화"(§2) 대응 — 같은 IP의 명칭 불일치를 canonical ip_id로 해석하는 1급 서비스.

### 추가

- **엔티티 해석** (`GET /api/v1/entity-resolution`, 출처 지도 페이지 '식별자 해석' 섹션):
  `backend/resolve/entity_resolution.py` — `IPAliasIndex`(IPBlock name/domain/aliases
  토큰 역인덱스) + `EntityResolutionService.report()`.
  - **별칭표**: canonical IP별 도메인·별칭 목록.
  - **미해석 토큰 큐**: event `affected_domains` 중 어떤 IP로도 해석 안 되는 토큰을
    빈도순 수집 — 사람 판별용 큐레이션 큐(별칭 누락 vs 비-IP 개념축).
  - 교정은 IPBlock.aliases 변경(변경 규율)으로만 — 쓰기 API 없음.
  - `risk.py` 귀속 통일(L8 완전 해소)은 본 단계 out-of-scope (05 Stage 15).

### 검증

```text
backend 139 passed / ruff / mypy(55 files) pass · frontend build / test(21) pass ·
  validate-data 오류 0. openapi/gen:api 재생성. lint 기존 3건 외 신규 0.
관찰: 현 fixture affected_domains에 IP 토큰 + 비-IP 개념축(architecture/bandwidth/
  quality/schedule 등 23종)이 혼재 — 큐가 이를 정직하게 노출(L8 근거 재확인).
```

## Bridge F1 — 출처 지도 (2026-07-09)

> 설계: `internal_docs/design/07_advisory_to_os_bridge.md` §1. 원점 비전의 Data
> Fragmentation Map 대응 — "지식 중 무엇이 가상이고 무엇이 실데이터인가" 가시화.

### 추가

- **출처 지도** (`GET /api/v1/source-map`, 내비 '출처 지도'):
  전 컬렉션의 `SourceMeta.origin`(가상/반입/연동) + `ref` 유무를 집계하는
  결정론 파생 뷰(`backend/services/source_map.py`). 온톨로지 계약 변경 없음.
  - 컬렉션별 origin 세그먼트 막대 + 전체 요약(실데이터 N/M건) + 계보 미기재 경고.
  - 수치 리스크 점수 아님 — 단순 건수/비율 집계 (CLAUDE.md §6.3 무관).
  - `collection_ko`는 glossary `object_label`에서 파생(신규 라벨 불필요).

### 검증

```text
backend 133 passed / ruff / mypy pass · frontend build / test(21) pass ·
  validate-data 오류 0. openapi 재생성 + gen:api 반영.
참고: frontend lint의 기존 오류 3건(DemoStoryBar/AskPage, react-hooks) 선존 —
  본 변경과 무관(HEAD에서도 재현). 별도 처리 예정.
```

## Stage 12 — 데모 스토리 + TAT 측정 체계 (2026-07-06)

> 원점 목표 복원(Stage 8~12)의 마지막 단계 (`internal_docs/design/03_course_correction.md` §4.5).
> **Stage 8~12 교정 계획 완료** — 5대 질문 코크핏 + 데모/효과 측정 체계.

### 추가

- **데모 스토리 모드** (`?story=1`, 내비 '데모 스토리'):
  "위험 발견 → 원인 분석 → 변경 영향 → 결정 근거" 4장면을 클릭만으로 진행.
  - 장면별 사전 구성 딥링크: 홈 heatmap → 이슈 RCA(`?issue=`) →
    변경 영향 자동 실행(`?ip=&knob=` 신규 지원) → Ask SoC(`?q=`).
  - 장면별 경과 시간 실시간 표시 + localStorage 기록(`soc_tat_run`) →
    완료 시 장면별/합계 TAT 요약 표시 (앱 내 로그).
- **TAT 측정 체계** (`internal_docs/validation/01_tat_measurement.md`):
  원점 데모 질문 5종 + 스토리 4장면의 수작업 baseline vs 코크핏 비교 기준표,
  측정 방법(도달 정의/스톱워치/앱 내 로그), 클릭 3번 규칙 검증 절차.
- **사내 검증 워크숍 자료** (`internal_docs/validation/02_workshop_fixture_hypotheses.md`):
  원점 Phase 0D 대응 — 연결 모델/위험 룰/원인 유형/archetype/역할 경계 가설 22건
  판정표 + 60분 진행안.

### 검증

```text
backend 127 passed / ruff / mypy pass · frontend build / test(21, +DemoStoryBar 3) / lint pass
E2E: 데모 4장면 실제 완주 — 클릭만으로 진행, 합계 1:35 (실 Claude 질의 포함),
  TAT 요약 바 표시 확인. 수용 기준(클릭 진행/비교표 산출) 충족.
```

## Stage 11 — Ask SoC 자연어 질의 (2026-07-06)

> "과거 과제에서 비슷한 문제가 있었나?" — 원점 5대 질문 메뉴의 마지막 조각
> (`internal_docs/design/03_course_correction.md` §4.4). 이로써 코크핏 내비의
> 질문 메뉴 4종(위험 지도/변경 영향/이슈 분석/Ask SoC)이 전부 활성화됐다.

### 추가

- `backend/agents/ask_runner.py`: 질의 러너 —
  - **검색(결정론)**: 혼합 스크립트 토큰화(한국어 문장+영어 키워드), 해상도 표기 확장
    (4K→UHD, 8k30→8k/k30), IPBlock 별칭 매칭. 카드마다 결정론 상태 요약 부착
    (시나리오=위험 등급+최악 셀, 이슈=검증 상태, 테스트=결과, 이벤트=일정 신호).
    risk/위험 의도 질의는 구체 시나리오 매치가 없을 때 위험 지도 상위를 편입.
  - **LLM 답변**: 기존 provider 체인(claude_cli→on-prem) 재사용. **인용은 수집된 카드
    ID로 한정** — 검증 관문이 빈 인용/미수집 인용/근거 약한 high confidence를 거부하고
    다음 엔진으로 넘어간다.
  - **LLM 미가용/전부 거부 시**: 검색 결과+상태 요약만으로 결정론 답변 (수용 기준).
- API: `GET /api/v1/ask/presets`(원점 데모 질문 5종), `POST /api/v1/ask`
  (질의 연산 — 데이터 수정 아님, read-only 가드 테스트에 등록).
- Frontend `AskPage`(`/ask`, 내비 활성화 — 비활성 placeholder 전부 소진):
  검색창+프리셋 5종 → 답변(엔진/확신도 뱃지, 도출 과정, **인용 칩 클릭 시 카드로 스크롤**,
  검증 기록 접기) + 관련 객체 카드(시나리오→상세, 이슈→RCA 딥링크 `?issue=`).
  홈(위험 지도) 상단에 Ask SoC 검색창 추가 (§4.1 홈 구성 ① 완성).
- `docs/ask.md` 가이드 (동작 원리/확신도 해석/질문 팁/한계).

### 실 E2E 검증 기록 (Claude CLI)

- "UHD60 recording에서 현재 가장 위험한 IP는 무엇인가?" → claude_cli, medium,
  인용 4건 전부 카드 내, 검증 기록 0건. 위험 지도 셀 등급을 근거로 MFC를 지목하되
  "DPU·ISP도 함께 높음 셀에 있어 단정 불가"라는 유보까지 명시.
- "UHD60 thermal issue가 해결됐다고 판단할 evidence는 무엇인가?" → claude_cli, **low**,
  "해결됐다고 판단할 evidence가 확인되지 않는다"는 정직한 답 + 부족한 근거 3종 인용.

### 검증

```text
backend 127 passed(+ask 9, api 1) / ruff / mypy pass
frontend build / test(18, +AskPage 3) / lint pass · validate-data 오류 0
```

## Stage 10 — 이슈 분석: RCA 체인 + Test 온톨로지 확장 (2026-07-06)

> "이 이슈의 원인은? 정말 해결됐나?" — **close됐지만 검증 테스트가 없는 이슈가
> 빨갛게 드러나는 것**이 이 화면의 존재 이유 (`internal_docs/design/04_stage10_rca_design.md`).
> 변경 규율 6단계(설계→모델→schema→fixture→테스트→changelog) 준수.

### 온톨로지 확장 (event 모듈)

- `Test` 저장 객체 신설 (컬렉션 `tests`): test_type(regression/scenario/cts_vts/power),
  result(passed/failed/blocked/planned), 시나리오/이슈/근거 연결, 실행 주차.
- `RootCauseType` enum 6종 (원점 문서 분류 승계): architecture_miss / spec_ambiguity /
  verification_gap / power_model_error / sw_workaround_dependency / customer_scenario_mismatch.
- `RootCause` 구조화 (유형/서술/확신도/근거) + `Issue` 확장: root_causes, fix_type,
  fix_description, workaround, verifying_test_ids, residual_risk, reusable_lesson,
  resolved_week — 전부 optional, 56 유래 이슈 4건 무변경 통과.
- glossary label_ko 전체 추가, JSON Schema/openapi 재생성, 무결성 검사 확장
  (tests↔issues/scenarios/projects hard 참조, issue affected_scope 검증).

### 56 드리프트 재동기화

- `Variant.source_basis` 추가 후 변환기 재실행 — 56의 2026-07-05 갱신 반영
  (변형 +1건 matched_baseline, 측정 요구 +2건, 관계 +18건). **converter roundtrip 복구.**
- 로더에 `<module>_58.yaml` 오버레이 지원: 56 생성물과 58 전용 synthetic을 분리 관리
  (id 충돌 거부, 계보 ref `58:fixtures/...`). roundtrip 테스트는 `_58` 제외 비교.

### Fixture 보강 (`fixtures/event_58.yaml`)

- 원점 문서 §7 archetype 기반 이슈 **32건** (ISP 7 / DPU 6 / Codec 6 / Audio 6 / DDR·NoC 7)
  + 검증 테스트 **30건**. 상태 구성: RCA 완결 체인(전부 통과) 5건+,
  **검증 테스트 없는 close 이슈 3건**(수용 기준 사례), failed/planned 미검증, workaround 의존,
  open 후보 단계 혼재. validate-data 무결성 오류 0 유지.

### RCA 서비스 + 화면

- `backend/services/rca.py`: 7단 체인 파생 뷰 — 증상→영향→원인→조치→검증 테스트→
  잔존 리스크→재사용 교훈. 노드별 근거 뱃지(green/red/yellow) + 판정 사유.
  검증 상태(verified/unverified/no_tests), 종결+미검증 경고. 원인은 기록된 데이터만
  표시(LLM 추론 없음).
- API: `GET /api/v1/issues`(project/verification 필터, 경고 이슈 선두 정렬),
  `GET /api/v1/issues/{id}/rca`.
- Frontend `IssueAnalysisPage`(`/issues`, 내비 '이슈 분석' 활성화): 이슈 목록(검증 뱃지,
  경고 빨간 강조) → 세로 RCA 흐름(색 보더+뱃지+사유). UI 공통 원칙 준수.
- `docs/` 가이드에 `issues.md` 추가 (뱃지 규칙/원인 유형 6종 해석, 스크린샷 2장).

### 검증

```text
backend 117 passed(+rca 12, api 1) / 0 failed — converter roundtrip 포함 전부 green
ruff / mypy pass · frontend build / test(15) / lint pass · validate-data 오류 0
E2E: 실구동 — 이슈 36건 목록(경고 3건 선두·빨간 강조), 검증 없는 close 이슈의
  검증 노드 red + 경고 배너, 완결 체인 이슈 all-green(테스트 2건 통과) 확인.
```

## Stage 9 — 변경 영향 (Change Impact) (2026-07-05)

> "이 IP/knob을 바꾸면 어디에 영향이 가나?" — TAT 효과 1위 유스케이스 복원
> (`internal_docs/design/03_course_correction.md` §4.2). 결정론 그래프 순회만 사용, LLM 불개입.

### 추가

- `backend/services/change_impact.py`: 결정론 그래프 순회 엔진 (파생 뷰, 저장 없음).
  - 입력: IP 필수 + knob/capability/모드 선택. knob·capability·모드가 구체 링크를 만들면
    그 시나리오로 한정, 아니면 IP 수준(사용/의존+전체 요구)으로 확장.
  - 순회: scenario_ip_requirements → 영향 시나리오 → primary_kpis /
    ip_dependency_rules → 연쇄 IP(양방향: 선택 IP가 의존 ↔ 선택 IP에 의존, 조건 표시) /
    ip_knobs → 방향성(전력·지연·대역폭·리스크)·affected_kpis·related_scenarios /
    같은 IP 조합의 과거 이슈·이벤트 → 유사 사례(겹침 시나리오 명시).
  - **역할별 검토 체크리스트**: 역할 책임 경계(CLAUDE.md §2.2) 반영 — HW/SW는
    "feedback_items로 전달" 명시, Management는 "구현 세부 결정 아님". 트리거 근거가 있을
    때만 항목 생성 (일반론 금지, 테스트로 강제). 체크리스트 내보내기 텍스트 조립.
  - capability↔요구 매칭은 보수적 토큰 부분집합 일치만 — 근거 없는 연결 금지.
  - `services/common.py` `BasisItem` 신설 — risk 파생 뷰와 근거 항목 계약 공용화
    (`ip_match_tokens`/`event_related_ips`도 공용 승격).
- API: `GET /api/v1/change-impact`(ip_id/knob_id/capability_id/mode, 404/400 검증),
  `GET /api/v1/change-impact/options`(폼 옵션 — IP별 knob/capability/모드).
- Frontend `ChangeImpactPage`(`/change-impact`, 내비 활성화):
  IP→knob/capability/모드 셀렉트 → [분석 실행] → knob 방향성 뱃지 + 4분면
  (영향 시나리오/영향 KPI(knob 직접 ★ 우선)/연쇄 IP/역할별 체크리스트) + 과거 유사 사례.
  체크리스트 클립보드 복사. UI 공통 원칙(ID 숨김·색 의미·접기) 준수.

### 검증

```text
backend 103 passed(+change_impact 15, api 1) / 1 failed(기존 56 드리프트 — Stage 8 기록 참조)
ruff / mypy pass · frontend build / test(12) / lint pass
validate-data → 오류 0건 유지
E2E: ISP×pixel_mode 실구동 — 4분면 완결, 역할 경계 문구, 유사 사례 10건(이슈 우선),
  체크리스트 복사 "복사됨" 확인. API 프로브: 미지 IP 404 / knob-IP 불일치 400.
```

## Stage 8 — 홈 개편 + 위험 지도 (2026-07-05)

> 방향 교정(`internal_docs/design/03_course_correction.md`) 첫 구현 — 원점 문서의
> Milestone Risk Early Warning 복원. UI를 "질문이 곧 메뉴인 코크핏"으로 재편 시작.

### 추가

- `backend/services/risk.py`: 시나리오×IP **정성 위험 등급** 결정론 룰 (파생 뷰, 저장 없음).
  - 셀 룰: 미해결 이슈(높음) / 확신도 차단 근거(상한 low=높음, medium=중간 — 가중 차등) /
    일정 위험 신호 at_risk·delayed·window_closing(고심각도 결합 시 높음) / 고심각도 이벤트(중간) /
    요구 근거 미충족(중간) / 과거 유사 이슈(중간). 신호 없으면 낮음 + `no_signal` 근거.
  - 시나리오 종합 룰: 셀 최고 등급 + P0 요청 근거 부족(높음) / P1 요청(중간) / 근거 공백 누적 ≥3(중간).
  - **모든 등급은 판정 근거 목록(원본 객체 ref) 동반 — 근거 없는 등급 없음. 수치 점수 산출·표시 없음**
    (CLAUDE.md §6.3 승인 범위, 테스트로 강제).
  - 이벤트→IP 귀속은 IPBlock의 domain/aliases 토큰과 candidate option의 명시 참조로만 판별
    (synthetic ID 하드코딩 없음). heatmap 열도 시나리오가 참조하는 블록에서 파생 (10열, ip_cpu 제외).
  - "이번 주 주목" 3~5건: P0/P1 요청 근거 부족 → 확신도 차단 → 일정 위험 순, 최근 주차 우선.
- API: `GET /api/v1/risk/heatmap`(project_id 필터, 열은 필터와 무관하게 고정),
  `GET /api/v1/meta/labels`(내부 ID→표시명 — ID 숨김 원칙 지원).
- Frontend 홈 개편:
  - 내비 재편 — 위험 지도(홈) / 변경 영향·이슈 분석·Ask SoC(비활성, Stage 9~11 예정) /
    "데이터 탐색" 하위 그룹(기존 4화면 유지).
  - `RiskMapPage`: 프로젝트 탭 U/V/W, ●◐○ heatmap(위험 시나리오 우선 정렬), 셀/행 클릭 →
    판정 근거 패널 → 기존 시나리오 상세로 drill-down (3클릭 내 원본 근거 도달).
- UI 공통 원칙 전 화면 적용:
  - 내부 ID 숨김 — `useLabels` 훅으로 프로젝트/시나리오/그룹/IP/역할 ID를 표시명으로 렌더
    (ID는 hover title에만). 컴포넌트 가드 테스트로 강제.
  - 색 의미 통일 — 빨강=위험, 노랑=주의, 초록=정상 (`risk-high/medium/low`).
  - 접기 기본 — `CollapsibleList`(상위 5건+더 보기), 포트폴리오 주의 lane 44건 나열 문제 해소.

### 알려진 문제 (Stage 8 범위 밖 — 사용자 결정 필요)

- `test_converter_roundtrip` 1건 실패: 56 참조 데이터가 2026-07-05 15:23에 갱신됨
  (variants 5→6건, Variant에 `source_basis` 필드 추가, scenarios/relations/measurement_requirements 변경)
  — Stage 1 변환 스냅샷과 드리프트. 동기화는 온톨로지 계약·fixture 변경(변경 규율 6단계)이라
  별도 승인 필요. Stage 8 코드와 무관.

### 검증

```text
backend 87 passed / 1 failed(위 드리프트) / ruff / mypy pass
frontend build / test(9) / lint pass — RiskMapPage 3건 + ID 숨김 가드 포함
validate-data → 오류 0건 유지
E2E: uvicorn 8155 + vite 5275 실구동 — heatmap 렌더/셀 drill-down/프로젝트 탭 전환/
  주목 5건/포트폴리오 접기·표시명 브라우저 확인. 미지 project_id→빈 결과 200, DELETE→405.
```

## Stage 7 — Excel/CSV 실데이터 반입 파일럿 (2026-07-04)

### 추가

- `backend/ingest/tabular.py`: CSV(UTF-8/CP949)·XLSX 파서.
- `backend/ingest/mappings.py`: **한국어 열 이름** → 온톨로지 필드 매핑 레지스트리.
  1차 매핑: 프로젝트 마일스톤, 측정 근거. 리스트 열(`;` 구분)/정수 열 변환 지원.
- `backend/ingest/service.py`: 반입 서비스 — 파싱 → 매핑 → 모델 검증 → 배치 저장.
  - 실패 행은 한국어 사유와 행 번호로 보고 (`필수 열 누락`, `형 변환 실패`, 필드 검증 실패).
  - 모든 반입 객체는 `source.origin=imported` + `import:<배치>:<파일>#row<N>` 계보.
  - **rollback은 배치 단위만** — 개별 객체 수정/삭제 API는 계속 부재.
  - synthetic 데이터는 rollback의 영향을 받지 않음 (테스트 강제).
- 저장 백엔드별 writer: `MemoryIngestWriter`(개발) / `PostgresIngestWriter`(운영,
  마이그레이션 `0003_ingest_batches.sql`).
- API: `POST /api/v1/ingest/file`(multipart), `GET /api/v1/ingest/batches`,
  `POST /api/v1/ingest/batches/{id}/rollback`.
- CLI: `ingest-file --file --mapping [--dsn]` (DSN 없으면 검증만), `ingest-rollback`.
- UI: `SourceBadge`(가상/반입/연동) — 근거 탐색에 표시, 반입 이력 카드.
- 샘플: `samples/sample_milestones.csv` (한국어 헤더).

### 검증

```text
backend 82 passed (+PG: 반입→조회→rollback 왕복 포함) / ruff / mypy pass
frontend build / test(5) / lint pass
validate-data → 오류 0건 유지
```

## Stage 6 — 포트폴리오 현황 · 리뷰 센터 · 근거 탐색 (2026-07-04)

### 추가

- 4화면 체계 완성 (헤더 내비게이션: 포트폴리오/시나리오/리뷰 센터/근거 탐색).
- **① 포트폴리오 현황** (`/portfolio`): U/V/W 프로젝트 요약 카드, 주의 lane 6종
  (근거 부족/정의 필요/확신도 차단/전파 검토/리스크 해소 후보/경영 주의),
  시나리오×프로젝트 매트릭스 (요청/이벤트/근거 공백 카운트) — 셀 클릭 시 시나리오 상세.
  "참여 권장이며 담당 지정 아님 · 수치 점수 없음 · 결정 아님" 원칙을 화면에 명시.
- **③ 리뷰 센터** (`/review/:week?`): 주차 선택 → 이벤트/역할 활동/요청 스냅샷.
- **④ 근거 탐색** (`/evidence`): 근거 카탈로그 목록, 프로젝트/가용성 필터,
  측정/예측 구분, 시나리오 링크.
- `AttentionItem.scenario_ids` 추가 — 주의 항목에서 시나리오 상세로 직접 이동.
- API: `GET /api/v1/evidence` (project_id/scenario_id/availability 필터).

### 검증

```text
backend 73 passed (+ PG) / ruff / mypy pass
frontend build / test(5) / lint pass
```

## Stage 5 — LLM Provider Chain + Scenario Advisory (2026-07-04)

### 추가

- `backend/agents/providers/`: `LLMProvider` 프로토콜 + 3단 체인.
  - `claude_cli`(1차, 외부): headless 실행 `claude -p --output-format json`, 타임아웃/오류 처리.
  - `openai_compat`(2차, 사내): chat/completions 호환, `SOC_ONPREM_BASE_URL/MODEL/API_KEY`.
  - 결정론 어드바이저(3차, 내장): 근거 공백/일정 신호/측정 요구 규칙 기반 — 항상 가용.
- `backend/agents/validators.py`: evidence-grounded 검증 관문 (provider 무관 필수 통과) —
  supporting_basis 필수·미해석 근거 거부·일반론 거부·근거 약한 high confidence 금지.
- `backend/agents/runner.py`: 컨텍스트 조립(분석 결과 → 압축 JSON) → 역할별 프롬프트(한국어
  출력 강제, 역할 책임 경계 반영) → 체인 실행 → 검증 → `RoleAdvisory` 채택.
- 감사 기록 `AgentRun`: provider/모델/입력 해시/검증 기록/소요시간.
  `InMemoryRunStore` + `PostgresRunStore`(마이그레이션 `0002_agent_runs.sql`).
- 정책 스위치 `SOC_ALLOW_EXTERNAL_LLM=false` → 외부(사외) LLM 건너뜀 (실데이터 보안 대비).
  체인 구성은 `SOC_ADVISORY_PROVIDERS` 환경변수.
- API: `POST /api/v1/scenarios/{id}/advisory`(생성), `GET`(기록 조회).
  데이터 수정 엔드포인트는 여전히 없음 (PUT/PATCH/DELETE 부재를 테스트로 강제).
- 런타임 계약 `RoleAdvisory` 추가 + JSON Schema/openapi/frontend 타입 재생성.
- Frontend: 시나리오 상세에 "조언" 탭 — 생성 버튼, 역할별 조언 카드
  (생성 엔진/확신도 뱃지, 근거 문장, 검증 기록 표시).

### 실 E2E 검증 기록

실제 Claude CLI(haiku)로 PM 역할 advisory를 2회 실행:

1. 1차: LLM이 근거 공백 9건 상황에서 high confidence 출력 → **validator가 거부하고
   결정론 fallback 채택** (감사 기록에 거부 사유 보존). 검증 관문이 설계대로 동작.
2. 프롬프트에 "근거 공백 존재 시 high 금지" 규칙 명시 후 2차: **claude_cli 출력이
   validator 통과** — medium confidence, 해석 가능한 근거 ID 인용
   (req_v_emulator_power_unknown_w24 등), 한국어 조언, 검증 기록 0건.

### 검증

```text
uv run pytest (+ POSTGRES_TEST_DSN) → 71 passed (agents 16건, PG run store 왕복 포함)
frontend build / test / lint → pass
uv run ruff check / mypy → pass (45 files)
```

## Stage 4 — 한국어 Frontend: 시나리오 상세 화면 (2026-07-04)

### 추가

- `frontend/` 신규 구축: Vite + React 19 + TypeScript + react-router v7 + TanStack Query v5.
- API 타입 자동 생성: openapi-typescript(`npm run gen:api`) + openapi-fetch 타입 클라이언트.
  수동 API 타입 없음 (56의 1,463줄 수동 types.ts 방식 폐기).
- 화면:
  - 시나리오 목록 (`/scenarios`): 프로젝트 필터, 그룹/KPI 표시.
  - 시나리오 상세 (`/scenarios/:id/:tab`): 개요(기본 정보·근거 공백·KPI·IP·요청·이슈·
    변형·측정) / 타임라인(주차 그룹) / 이벤트·활동(근거 문장 표시) / 추적.
- 공통 traceability drill-down 패널 (`TraceabilityPanel`): breadcrumb 스택 기반 —
  이후 모든 화면이 재사용할 단일 패턴.
- 한국어 전용 UI: `src/i18n/ko.ts` 단일 소스 + JSX 영어 하드코딩 금지 가드 테스트.
- uvicorn 추가 — `uv run uvicorn backend.api.app:create_app --factory`로 API 구동.
- README: 실행/검증/계약 재생성 가이드.

### 검증

```text
npm run build / test(4 passed) / lint → pass
uvicorn 스모크: health ok, analysis 응답 (gaps 9, timeline 21)
backend 회귀 유지: pytest / ruff / mypy pass
```

## Stage 3 — 결정론 서비스 + Read-only API (2026-07-04)

### 추가

- `backend/resolve/`: `ObjectIndex`(전역 ID 해석, 내장 전파 포함),
  `TraceabilityService`(명시 relations + 암묵 참조 필드의 양방향 링크, 한국어 관계 유형).
- `backend/services/scenario_analysis.py`: 시나리오 종합 — 그룹/변형/KPI/요청/이벤트/
  역할 활동/이슈/근거 카탈로그/측정, 근거 공백 진단(누락·미가용·요구 미충족·확신도 차단),
  주차 타임라인(이벤트·활동·요청·마일스톤).
- `backend/services/portfolio.py`: U/V/W 요약 + 주의 lane 6종(근거 부족/정의 필요/
  확신도 차단/전파 검토/리스크 해소 후보/경영 주의) + 시나리오×프로젝트 매트릭스.
  수치 점수·결정 자동화·담당자 할당 없음 (56 원칙 유지).
- `backend/services/review.py`: 주간 인덱스/스냅샷 파생 뷰.
- `backend/api/`: FastAPI read-only 표면 13개 GET 엔드포인트
  (health/meta/glossary/projects/scenarios/analysis/timeline/events/traceability/
  portfolio/weekly). GET 외 메서드 부재를 테스트로 강제.
- `openapi.json` 커밋 + 드리프트 테스트 — Stage 4 frontend 타입 생성 소스.
- 저장소 백엔드 자동 선택: `SOC_ONTOLOGY_DSN` 설정 시 PostgreSQL, 아니면 in-memory.

### 수정

- `InMemoryRepository.list`가 미지 컬렉션에 KeyError — PostgresRepository와 계약 통일
  (백엔드 간 API 패리티 테스트로 검증).

### 검증

```text
uv run pytest (+ POSTGRES_TEST_DSN) → 53 passed
  - API 패리티: 메모리/PostgreSQL 백엔드 응답 동일 (analysis/portfolio/weekly/traceability)
uv run ruff check / mypy → pass (35 files)
validate-data → 오류 0건 유지
```

## Stage 2 — PostgreSQL 계층 (2026-07-04)

### 추가

- `backend/db/`: psycopg3 연결 관리(`SOC_ONTOLOGY_DSN`), 버전드 SQL 마이그레이션 + 경량 러너.
- `migrations/0001_core.sql`: Phase3-lite 패턴 —
  `ontology_objects`(collection+id PK, 필터 컬럼, JSONB payload, source 추적, GIN 인덱스),
  `relations` 그래프 투영, pgvector-ready `semantic_chunks` 투영.
- `backend/ingest/yaml_seed.py`: fixture 전량 멱등 반입 (ON CONFLICT upsert).
- `backend/db/repository.py`: `PostgresRepository` — payload에서 모델 재구성, 적재 순서 보존.
- `backend/loaders/protocols.py`: `RepositoryProtocol` — in-memory/PostgreSQL 공용 계약.
  `check_integrity`가 protocol 기반으로 일반화됨.
- CLI: `db-init` / `db-seed` / `db-check` (한국어 출력).
- 테스트: DSN 없이 도는 단위 테스트 6건 + `POSTGRES_TEST_DSN` 게이트 통합 테스트 6건
  (시드 건수, in-memory 패리티, 멱등성, PG 위 무결성 0오류, 투영 테이블).

### 검증

```text
uv run pytest -p no:cacheprovider → 24 passed, 6 skipped (DSN 게이트)
POSTGRES_TEST_DSN=... uv run pytest -m postgres → 6 passed (pgvector/pg16, soc58_test DB)
uv run ruff check / mypy → pass
validate-data → 오류 0건 유지
```

## Stage 1 — 온톨로지 v1.0 계약 + 프로젝트 스캐폴드 (2026-07-04)

### 추가

- uv 기반 프로젝트 스캐폴드: pyproject.toml, ruff/mypy/pytest 설정.
- `backend/ontology/` 8모듈 온톨로지 계약 (Pydantic v2, extra="forbid"):
  - project / scenario / ip / event / evidence / role / decision / relation.
  - 56의 스키마 30개를 통합: `event` + `development_event` → `DevelopmentEvent` 단일 계약.
  - 파생 뷰(portfolio board, weekly snapshot, scenario trace)는 저장 계약에서 제외.
  - 모든 저장 객체에 `source(origin/ref/ingested_at)` 출처 메타데이터.
  - 런타임 계약: `RoleOutput`, `GroundedStatement` (Stage 5 advisory 대비).
- 한국어 glossary (`backend/ontology/glossary.py`):
  - 전 모델/필드/enum의 label_ko — 커버리지 테스트로 강제.
  - `Confidence` enum이 56의 H/M/L 축약 표기를 정규화.
- JSON Schema 자동 export (`backend/ontology/schema_export.py`) → `schemas/` 33개.
  - 수동 3중 동기화(56 방식) 폐기 — Pydantic 모델이 단일 소스.
  - 드리프트는 테스트로 차단.
- 56 fixture 전량 변환 (`tools/convert_56_fixtures.py`) → `fixtures/` 8파일 465건.
  - id 별칭 필드(event_id, activity_id 등 8종) 제거 — 동일성 검증 후.
  - 구 events.yaml 4건을 DevelopmentEvent로 승격 (`event_category=legacy_event`).
  - `IPBaseSpec.spec_id`는 별칭이 아닌 원본 스펙 식별자로 판별되어 유지.
- In-memory repository + 참조 무결성 검사 (`backend/loaders/`):
  - 하드 참조(프로젝트/시나리오/IP/역할/이벤트/마일스톤/요청/전파/근거) 오류 0건.
  - 56 원본 데이터 자체의 느슨한 참조(시나리오 그룹의 미등록 시나리오 15건)는 경고로 분류.
- CLI `validate-data`: 적재 + 검증 + 무결성 + glossary 커버리지 보고 (한국어 출력).
- 테스트 18건: 적재/모델 계약/무결성/glossary/스키마 드리프트/변환 회귀(56 존재 시).

### 검증

```text
uv run pytest -p no:cacheprovider  → 18 passed
uv run ruff check backend tests tools → pass
uv run mypy → pass (18 files)
uv run python -m backend.cli.main validate-data → 오류 0 / 경고 15 / glossary 누락 0
```

## 설계 확정 (2026-07-04)

- `internal_docs/design/01_system_architecture.md`: 운영 시스템 아키텍처 확정 — LLM 3단 체인
  (Claude CLI → 사내 on-prem → 결정론), PostgreSQL-first, 온톨로지 8모듈, 한국어 1급.
- `internal_docs/design/02_implementation_roadmap.md`: Stage 1~8+ 전체 상세 계획.
