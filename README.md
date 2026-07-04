# SoC Operational Ontology

Multimedia SoC 개발 운영 온톨로지 — evidence-grounded 분석·조언 시스템.

- 설계: `docs/design/01_system_architecture.md`
- 전체 로드맵: `docs/design/02_implementation_roadmap.md`
- 활성 Stage: `CURRENT_TASK.md`
- 참조(read-only): `E:\56_Codex_SoC_Operational_Ontology`

## 실행

### Backend (API)

```bash
uv sync
uv run python -m backend.cli.main validate-data        # fixture 검증
uv run uvicorn backend.api.app:create_app --factory --port 8155
```

> 이 머신의 포트 규칙: 58은 **8155(API) / 5273(frontend)** 전용.
> 8000/5173 등은 다른 프로젝트(56 등)가 사용하므로 건드리지 않는다.

PostgreSQL 사용 시 (선택):

```bash
uv run python -m backend.cli.main db-init  --dsn postgresql://...
uv run python -m backend.cli.main db-seed  --dsn postgresql://...
SOC_ONTOLOGY_DSN=postgresql://... uv run uvicorn backend.api.app:create_app --factory
```

### Frontend

```bash
cd frontend
npm install
VITE_API_TARGET=http://127.0.0.1:8155 npx vite --host 127.0.0.1 --port 5273 --strictPort
# → http://127.0.0.1:5273 (API는 /api proxy → VITE_API_TARGET)
```

## 검증

```bash
uv run pytest -p no:cacheprovider
uv run ruff check backend tests tools
uv run mypy
cd frontend && npm run build && npm run test && npm run lint
```

## 계약 재생성 (모델 변경 시)

```bash
uv run python -m backend.ontology.schema_export   # schemas/*.schema.json
uv run python -m backend.api.openapi_export       # openapi.json
cd frontend && npm run gen:api                    # src/api/schema.d.ts
```
