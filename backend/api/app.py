"""Read-only FastAPI 표면 — 결정론 서비스 위의 조회 API.

데이터 수정 엔드포인트는 없다. 저장소는 환경에 따라 선택된다:
SOC_ONTOLOGY_DSN 설정 시 PostgreSQL, 아니면 fixtures 기반 in-memory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from backend.agents.run_store import InMemoryRunStore, RunStoreProtocol
from backend.agents.runner import AdvisoryRunner
from backend.ingest.service import (
    IngestBatch,
    IngestError,
    IngestReport,
    IngestService,
    MemoryIngestWriter,
)
from backend.loaders.protocols import RepositoryProtocol
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS, RUNTIME_CONTRACTS
from backend.ontology.event import DevelopmentEvent
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.ontology.glossary import export_glossary
from backend.ontology.project import Project
from backend.ontology.relation import AgentRun
from backend.ontology.scenario import Scenario
from backend.resolve.object_index import ObjectIndex
from backend.resolve.traceability import TraceabilityResult, TraceabilityService
from backend.services.change_impact import (
    ChangeImpactOptions,
    ChangeImpactResult,
    ChangeImpactService,
    InvalidSelectionError,
    UnknownIPError,
)
from backend.services.portfolio import PortfolioOverview, PortfolioService
from backend.services.review import ReviewService, WeeklyIndex, WeeklySnapshot
from backend.services.risk import RiskHeatmap, RiskService
from backend.services.scenario_analysis import (
    ScenarioAnalysis,
    ScenarioAnalysisService,
    ScenarioNotFoundError,
    TimelineItem,
)

API_VERSION = "v1"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / "fixtures"


@dataclass
class AppServices:
    """앱 수명 동안 공유되는 저장소·서비스 묶음."""

    repo: RepositoryProtocol
    backend_kind: str
    analysis: ScenarioAnalysisService
    portfolio: PortfolioService
    review: ReviewService
    risk: RiskService
    change_impact: ChangeImpactService
    traceability: TraceabilityService
    advisory: AdvisoryRunner
    run_store: RunStoreProtocol
    ingest: IngestService


def build_services(
    repo: RepositoryProtocol | None = None, fixtures_dir: Path = DEFAULT_FIXTURES
) -> AppServices:
    backend_kind = "memory"
    run_store: RunStoreProtocol = InMemoryRunStore()
    ingest_service: IngestService | None = None
    if repo is None:
        dsn = os.environ.get("SOC_ONTOLOGY_DSN")
        if dsn:
            import psycopg

            from backend.agents.run_store import PostgresRunStore
            from backend.db.repository import PostgresRepository
            from backend.ingest.service import PostgresIngestWriter

            conn = psycopg.connect(dsn)
            repo = PostgresRepository(conn)
            run_store = PostgresRunStore(conn)
            ingest_service = IngestService(PostgresIngestWriter(conn))
            backend_kind = "postgres"
        else:
            repo = InMemoryRepository.from_fixtures(fixtures_dir)
    if ingest_service is None:
        if isinstance(repo, InMemoryRepository):
            ingest_service = IngestService(MemoryIngestWriter(repo))
        else:
            ingest_service = IngestService(MemoryIngestWriter(InMemoryRepository({})))
    index = ObjectIndex(repo)
    return AppServices(
        repo=repo,
        backend_kind=backend_kind,
        analysis=ScenarioAnalysisService(repo),
        portfolio=PortfolioService(repo),
        review=ReviewService(repo),
        risk=RiskService(repo),
        change_impact=ChangeImpactService(repo),
        traceability=TraceabilityService(repo, index),
        advisory=AdvisoryRunner(repo, run_store),
        run_store=run_store,
        ingest=ingest_service,
    )


class AdvisoryRequest(BaseModel):
    """advisory 실행 요청 — 역할 미지정 시 7개 역할 전체."""

    roles: list[str] | None = Field(default=None, description="role_id 목록 (기본: 전체)")


def create_app(repo: RepositoryProtocol | None = None) -> FastAPI:
    app = FastAPI(
        title="SoC 운영 온톨로지 API",
        description="Multimedia SoC 개발 운영 온톨로지 — read-only 조회 표면",
        version="0.1.0",
    )
    services = build_services(repo)
    prefix = f"/api/{API_VERSION}"

    @app.get(f"{prefix}/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "backend": services.backend_kind}

    @app.get(f"{prefix}/meta")
    def meta() -> dict[str, Any]:
        counts = {key: len(services.repo.list(key)) for key in COLLECTIONS}
        return {
            "version": app.version,
            "backend": services.backend_kind,
            "collections": counts,
        }

    @app.get(f"{prefix}/meta/glossary")
    def glossary() -> dict[str, Any]:
        models: list[type[BaseModel]] = [model for _, model in COLLECTIONS.values()]
        models += list(RUNTIME_CONTRACTS.values())
        return export_glossary(models)

    @app.get(f"{prefix}/meta/labels")
    def labels() -> dict[str, str]:
        """내부 ID → 표시명 매핑 — ID 숨김 원칙(ID는 hover/상세만 노출) 지원."""
        result: dict[str, str] = {}
        for collection in ("projects", "scenarios", "scenario_groups", "ip_blocks", "roles"):
            for obj in services.repo.list(collection):
                name = getattr(obj, "name", None)
                if isinstance(name, str) and name:
                    result[obj.id] = name
        return result

    @app.get(f"{prefix}/projects", response_model=list[Project])
    def list_projects() -> list[Project]:
        return [p for p in services.repo.list("projects") if isinstance(p, Project)]

    @app.get(f"{prefix}/projects/{{project_id}}", response_model=Project)
    def get_project(project_id: str) -> Project:
        obj = services.repo.get("projects", project_id)
        if not isinstance(obj, Project):
            raise HTTPException(status_code=404, detail=f"프로젝트 없음: {project_id}")
        return obj

    @app.get(f"{prefix}/scenarios", response_model=list[Scenario])
    def list_scenarios(
        project_id: str | None = Query(default=None, description="프로젝트 필터"),
    ) -> list[Scenario]:
        scenarios = [s for s in services.repo.list("scenarios") if isinstance(s, Scenario)]
        if project_id:
            scenarios = [s for s in scenarios if project_id in s.project_relevance]
        return scenarios

    @app.get(f"{prefix}/scenarios/{{scenario_id}}/analysis", response_model=ScenarioAnalysis)
    def scenario_analysis(scenario_id: str) -> ScenarioAnalysis:
        try:
            return services.analysis.analyze(scenario_id)
        except ScenarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(f"{prefix}/scenarios/{{scenario_id}}/timeline", response_model=list[TimelineItem])
    def scenario_timeline(scenario_id: str) -> list[TimelineItem]:
        try:
            return services.analysis.analyze(scenario_id).timeline
        except ScenarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(f"{prefix}/events", response_model=list[DevelopmentEvent])
    def list_events(
        project_id: str | None = Query(default=None),
        week: int | None = Query(default=None),
    ) -> list[DevelopmentEvent]:
        events = [
            e for e in services.repo.list("development_events") if isinstance(e, DevelopmentEvent)
        ]
        if project_id:
            events = [e for e in events if e.project_id == project_id]
        if week is not None:
            events = [e for e in events if e.week == week]
        return events

    @app.get(f"{prefix}/events/{{event_id}}", response_model=DevelopmentEvent)
    def get_event(event_id: str) -> DevelopmentEvent:
        obj = services.repo.get("development_events", event_id)
        if not isinstance(obj, DevelopmentEvent):
            raise HTTPException(status_code=404, detail=f"이벤트 없음: {event_id}")
        return obj

    @app.get(f"{prefix}/evidence", response_model=list[EvidenceCatalogEntry])
    def list_evidence(
        project_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
        availability: str | None = Query(default=None),
    ) -> list[EvidenceCatalogEntry]:
        entries = [
            e
            for e in services.repo.list("evidence_catalog")
            if isinstance(e, EvidenceCatalogEntry)
        ]
        if project_id:
            entries = [e for e in entries if e.project_id == project_id]
        if scenario_id:
            entries = [e for e in entries if e.scenario_id == scenario_id]
        if availability:
            entries = [e for e in entries if e.availability == availability]
        return entries

    @app.get(f"{prefix}/traceability/{{object_id}}", response_model=TraceabilityResult)
    def traceability(object_id: str) -> TraceabilityResult:
        result = services.traceability.trace(object_id)
        if result.collection is None and not result.links:
            raise HTTPException(status_code=404, detail=f"객체 없음: {object_id}")
        return result

    @app.get(f"{prefix}/portfolio/overview", response_model=PortfolioOverview)
    def portfolio_overview() -> PortfolioOverview:
        return services.portfolio.overview()

    @app.get(f"{prefix}/risk/heatmap", response_model=RiskHeatmap)
    def risk_heatmap(
        project_id: str | None = Query(default=None, description="프로젝트 필터"),
    ) -> RiskHeatmap:
        """위험 지도 — 시나리오×IP 정성 등급 + 판정 근거 (수치 점수 없음)."""
        return services.risk.heatmap(project_id)

    @app.get(f"{prefix}/change-impact/options", response_model=ChangeImpactOptions)
    def change_impact_options() -> ChangeImpactOptions:
        """변경 영향 폼 옵션 — IP별 knob/capability/모드."""
        return services.change_impact.options()

    @app.get(f"{prefix}/change-impact", response_model=ChangeImpactResult)
    def change_impact(
        ip_id: str = Query(description="변경 대상 IP 블록"),
        knob_id: str | None = Query(default=None),
        capability_id: str | None = Query(default=None),
        mode: str | None = Query(default=None),
    ) -> ChangeImpactResult:
        """변경 영향 분석 — 결정론 그래프 순회 (모든 항목에 근거 ref)."""
        try:
            return services.change_impact.analyze(
                ip_id, knob_id=knob_id, capability_id=capability_id, mode=mode
            )
        except UnknownIPError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except InvalidSelectionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(f"{prefix}/review/weekly", response_model=WeeklyIndex)
    def weekly_index() -> WeeklyIndex:
        return services.review.index()

    @app.get(f"{prefix}/review/weekly/{{week}}", response_model=WeeklySnapshot)
    def weekly_snapshot(week: int) -> WeeklySnapshot:
        return services.review.snapshot(week)

    @app.post(f"{prefix}/scenarios/{{scenario_id}}/advisory", response_model=AgentRun)
    def run_advisory(scenario_id: str, request: AdvisoryRequest | None = None) -> AgentRun:
        """역할 조언 생성 — provider 체인 실행, 감사 기록 저장 (데이터 수정 아님)."""
        try:
            return services.advisory.run(
                scenario_id, role_ids=request.roles if request else None
            )
        except ScenarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(f"{prefix}/scenarios/{{scenario_id}}/advisory", response_model=list[AgentRun])
    def list_advisory(scenario_id: str) -> list[AgentRun]:
        """해당 시나리오의 advisory 실행 기록 (최신순)."""
        return services.run_store.list_for_scenario(scenario_id)

    @app.post(f"{prefix}/ingest/file", response_model=IngestReport)
    async def ingest_file(
        mapping: str = Query(description="매핑 이름 (예: project_milestones)"),
        file: UploadFile = File(description="CSV 또는 XLSX 파일"),
    ) -> IngestReport:
        """실데이터 반입 — 온톨로지 데이터가 진입하는 유일한 쓰기 경로."""
        content = await file.read()
        try:
            return services.ingest.ingest(file.filename or "upload", content, mapping)
        except IngestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get(f"{prefix}/ingest/batches", response_model=list[IngestBatch])
    def list_ingest_batches() -> list[IngestBatch]:
        """반입 이력 (최신순)."""
        return services.ingest.list_batches()

    @app.post(f"{prefix}/ingest/batches/{{batch_id}}/rollback")
    def rollback_ingest_batch(batch_id: str) -> dict[str, int]:
        """반입 배치 단위 rollback — 허용되는 유일한 삭제 경로."""
        removed = services.ingest.rollback(batch_id)
        return {"removed": removed}

    return app
