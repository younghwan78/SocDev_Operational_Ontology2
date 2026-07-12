# 운영 Runbook — 사내 배포·운영 절차 (D1-5, Stage 14)

> 대상: 사내 서버 관리자·운영 담당. 전제: Docker + Docker Compose가 설치된 리눅스
> 서버(또는 동급). 이 문서의 전 절차는 사외 리허설로 검증됨 (2026-07-12).

## 1. 설치·기동

```bash
git clone <사내 미러 저장소> soc-ontology && cd soc-ontology/deploy
cp .env.example .env        # 값 채우기 — 아래 두 개는 필수
#   POSTGRES_PASSWORD=<강한 비밀번호>
#   SOC_API_TOKEN=<접속 토큰 — 사용자에게 배포할 값>
docker compose up -d --build
```

- 웹: `http://<서버>:8080` (HTTP_PORT로 변경). 첫 접속 시 **접속 토큰** 입력
  (= SOC_API_TOKEN 값, 브라우저에 저장됨).
- 최초 데모/검증이면 `.env`에 `SEED_FIXTURES=true`로 synthetic 549건을 시드.
  실데이터 운영 전에는 반드시 `false`로 되돌리고 데이터를 초기화한다(§5 복구).

구성: `postgres`(pgvector, 볼륨 `pgdata`) ← `api`(기동 시 마이그레이션 자동 적용)
← `frontend`(nginx 정적 + /api 프록시). **API는 호스트에 노출되지 않는다** —
모든 접근은 nginx 경유, 토큰 필수(`/api/v1/health`만 무인증 — 모니터링용).

## 2. LLM 정책

| 변수 | 사내 권장 | 의미 |
|---|---|---|
| `SOC_ALLOW_EXTERNAL_LLM` | `false` | 외부(사외) LLM 차단 — Ask/advisory 공통 관문 |
| `SOC_ADVISORY_PROVIDERS` | `openai_compat` | 사내 on-prem만 사용 |
| `SOC_ONPREM_BASE_URL/API_KEY/MODEL` | 사내 값 | OpenAI 호환 API |

on-prem 미설정이어도 시스템은 **결정론 fallback**으로 항상 동작한다(조회·위험
지도·RCA·변경 영향은 LLM 무관). 같은 질문 재질의는 캐시로 즉답(`SOC_ASK_CACHE`).

**시맨틱 검색(선택)**: `SOC_EMBED_PROVIDER=openai_compat` + 임베딩 모델 지정 후
`embed-chunks --provider openai_compat` 실행(청크 반입 후, 멱등) — Ask가 키워드에
더해 문서 후보(증거 아님)를 벡터로 찾는다. 미설정이면 키워드 검색만으로 동작.

## 3. JIRA/Confluence 동기화 (주기 실행)

사전 조건: 보안 승인, 서비스 계정 토큰, `backend/connectors/jira_field_map.yaml`
사내 스키마 값 확정 (핸드오버 킷 워크시트 참조 — D2).

```bash
# 리허설 (저장 없음 — 정규화·품질 리포트만)
docker compose exec api uv run python -m backend.cli.main sync-jira \
  --jql 'project = MM AND updated >= -7d' --since auto

# 실제 반입
docker compose exec -e JIRA_BASE_URL=... -e JIRA_API_TOKEN=... api \
  uv run python -m backend.cli.main sync-jira --jql '...' --since auto --execute
```

주기 실행(호스트 cron 예 — 평일 06:00):

```cron
0 6 * * 1-5  cd /opt/soc-ontology/deploy && docker compose exec -T api \
  uv run python -m backend.cli.main sync-jira --jql '...' --since auto --execute \
  >> /var/log/soc-sync.log 2>&1
```

모니터링: `docker compose exec api uv run python -m backend.cli.main sync-status`
— 소스별 마지막 완료 시각·카운트·**보류(quarantine) 건수**. 보류가 쌓이면 반입
센터 화면의 큐레이션 대기열에서 수정용 CSV를 내려받아 처리한다.

## 4. 백업

```bash
# 일일 백업 (cron 권장) — 온톨로지 + 감사 로그 + 배치 이력 전부 포함
docker compose exec -T postgres pg_dump -U soc soc_ontology | gzip \
  > /backup/soc_ontology_$(date +%Y%m%d).sql.gz
```

보존 권장: 일 7 + 주 4. fixture/코드는 git이 원본이므로 DB 덤프만 백업하면 된다.

## 5. 복구·되돌리기

- **배치 단위 되돌리기(운영 중 기본 수단)**: 반입 센터 화면의 rollback 버튼 또는
  `ingest-rollback --batch-id <id>`. 잘못 들어온 반입은 이것으로 해결 — DB 복원 불필요.
- **전체 복원**:
  ```bash
  docker compose stop api
  gunzip -c /backup/soc_ontology_YYYYMMDD.sql.gz | \
    docker compose exec -T postgres psql -U soc -d soc_ontology
  docker compose start api
  ```
- **초기화(데모 → 실운영 전환)**: `docker compose down -v` (볼륨 삭제) 후
  `.env`의 `SEED_FIXTURES=false`로 재기동.

## 6. 업그레이드

```bash
cd /opt/soc-ontology && git pull
cd deploy && docker compose up -d --build   # 마이그레이션은 api 기동 시 자동(멱등)
```

전 버전 복귀: `git checkout <이전 태그>` 후 동일 명령. 스키마 마이그레이션은
추가 전용(add-only)이라 코드 하위 호환이 유지된다.

## 7. 로그·관측

- **요청 로그**: `docker logs <api>` — JSON 라인(`kind:access`, 경로/상태/소요 ms).
  토큰·본문은 기록되지 않는다. 오류는 `kind:error` + 스택.
- **감사 기록**(DB): `agent_runs`(advisory), `ask_log`(질의/답변·FAQ 원천),
  `ingest_batches`(반입 이력). 백업에 포함된다.
- 헬스체크: `GET /api/v1/health` (무인증) — `{"status":"ok","backend":"postgres"}`.

## 8. 트러블슈팅

| 증상 | 점검 |
|---|---|
| 화면에서 토큰 입력이 반복됨 | SOC_API_TOKEN 값 불일치 — 서버 `.env`와 입력 값 비교 |
| 502 | `docker logs <api>` — DB 대기/기동 실패. postgres healthy 확인 |
| 질의가 항상 "LLM 미개입" | on-prem env 미설정 또는 정책 차단 — §2 |
| 반입했는데 화면에 안 보임 | 품질 리포트의 연결률 확인 — 시나리오/IP 미연결 데이터는 파생 뷰에 안 나타남 |
| 동기화 멈춤 | `sync-status` 마지막 완료 시각 + cron 로그 |
