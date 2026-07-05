# SoC Operational Ontology

Multimedia SoC 개발 운영 온톨로지 — evidence-grounded 분석·조언 시스템.

## 문서

- **UI 사용·해석 가이드 (사용자용, GitHub Pages 소스)**: [`docs/`](docs/index.md)
  — 위험 지도 / 변경 영향 / 데이터 탐색 / 공통 개념
- 내부 설계 문서 (개발용): `internal_docs/design/`
  - 시스템 아키텍처: `internal_docs/design/01_system_architecture.md`
  - 전체 로드맵: `internal_docs/design/02_implementation_roadmap.md`
  - 교정 설계 (Stage 8~12 기준): `internal_docs/design/03_course_correction.md`
- 활성 Stage: `CURRENT_TASK.md`
- 참조(read-only): `E:\56_Codex_SoC_Operational_Ontology`

> GitHub Pages 연동: 저장소 Settings → Pages → Source를 `main` 브랜치의 `/docs`
> 폴더로 지정하면 UI 가이드가 웹으로 게시된다.

## 실행

### Backend (API)

```bash
uv sync
uv run python -m backend.cli.main validate-data        # fixture 검증
uv run uvicorn backend.api.app:create_app --factory --port 8155
```

> 이 머신의 포트 규칙: 58은 **8155(API) / 5275(frontend)** 전용.
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
VITE_API_TARGET=http://127.0.0.1:8155 npx vite --host 127.0.0.1 --port 5275 --strictPort
# → http://127.0.0.1:5275 (API는 /api proxy → VITE_API_TARGET)
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
