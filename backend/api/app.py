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
from pydantic import BaseModel, ConfigDict, Field

from backend.agents.ask_runner import PRESET_QUESTIONS, AskResult, AskRunner
from backend.agents.run_store import InMemoryRunStore, RunStoreProtocol
from backend.agents.runner import AdvisoryRunner
from backend.ingest.service import (
    IngestBatch,
    IngestError,
    IngestReport,
    IngestService,
    MemoryIngestWriter,
    QuarantineEntry,
)
from backend.loaders.protocols import RepositoryProtocol
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS, RUNTIME_CONTRACTS
from backend.ontology.decision import Decision
from backend.ontology.event import DevelopmentEvent
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.ontology.glossary import export_glossary
from backend.ontology.project import Project
from backend.ontology.relation import AgentRun
from backend.ontology.scenario import Scenario
from backend.resolve.entity_resolution import EntityResolutionReport, EntityResolutionService
from backend.resolve.traceability import TraceabilityResult, TraceabilityService
from backend.services.action_draft import ActionDraft, ActionDraftService
from backend.services.change_impact import (
    ChangeImpactOptions,
    ChangeImpactResult,
    ChangeImpactService,
    InvalidSelectionError,
    UnknownIPError,
)
from backend.services.evidence_ladder import EvidenceLadder, EvidenceLadderService
from backend.services.portfolio import PortfolioOverview, PortfolioService
from backend.services.rca import (
    IssueNotFoundError,
    IssueSummary,
    RCAChain,
    RCAService,
)
from backend.services.review import ReviewService, WeeklyIndex, WeeklySnapshot
from backend.services.review_pack import (
    ReviewPackDocument,
    ReviewPackNotFoundError,
    ReviewPackService,
    ReviewPackSummary,
)
from backend.services.risk import RiskHeatmap, RiskService
from backend.services.scenario_analysis import (
    ScenarioAnalysis,
    ScenarioAnalysisService,
    ScenarioNotFoundError,
    TimelineItem,
)
from backend.services.source_map import SourceCoverage, SourceCoverageService

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
    rca: RCAService
    source_map: SourceCoverageService
    entity_resolution: EntityResolutionService
    action_draft: ActionDraftService
    evidence_ladder: EvidenceLadderService
    review_pack: ReviewPackService
    traceability: TraceabilityService
    advisory: AdvisoryRunner
    ask: AskRunner
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
    return AppServices(
        repo=repo,
        backend_kind=backend_kind,
        analysis=ScenarioAnalysisService(repo),
        portfolio=PortfolioService(repo),
        review=ReviewService(repo),
        risk=RiskService(repo),
        change_impact=ChangeImpactService(repo),
        rca=RCAService(repo),
        source_map=SourceCoverageService(repo),
        entity_resolution=EntityResolutionService(repo),
        action_draft=ActionDraftService(repo),
        evidence_ladder=EvidenceLadderService(repo),
        review_pack=ReviewPackService(repo),
        traceability=TraceabilityService(repo),
        advisory=AdvisoryRunner(repo, run_store),
        ask=AskRunner(repo),
        run_store=run_store,
        ingest=ingest_service,
    )


class AdvisoryRequest(BaseModel):
    """advisory 실행 요청 — 역할 미지정 시 7개 역할 전체."""

    roles: list[str] | None = Field(default=None, description="role_id 목록 (기본: 전체)")


class AskRequest(BaseModel):
    """Ask SoC 질의 요청."""

    question: str = Field(min_length=2, description="한국어/영어 혼용 자연어 질의")


class IngestMappingInfo(BaseModel):
    """반입 매핑 메타 — 반입 센터 화면 계약 (읽기 전용)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    label_ko: str
    target_collection: str
    columns: list[str]
    required_columns: list[str]


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

    @app.get(f"{prefix}/evidence/ladder", response_model=EvidenceLadder)
    def evidence_ladder(
        project_id: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
    ) -> EvidenceLadder:
        return services.evidence_ladder.ladder(project_id, scenario_id)

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

    @app.get(f"{prefix}/issues", response_model=list[IssueSummary])
    def list_issues(
        project_id: str | None = Query(default=None, description="프로젝트 필터"),
        verification: str | None = Query(
            default=None, description="verified | unverified | no_tests"
        ),
    ) -> list[IssueSummary]:
        """이슈 목록 — 검증 상태 뱃지 포함 (종결+미검증이 먼저)."""
        return services.rca.list_issues(project_id, verification)

    @app.get(f"{prefix}/issues/{{issue_id}}/rca", response_model=RCAChain)
    def issue_rca(issue_id: str) -> RCAChain:
        """이슈 RCA 체인 — 증상→영향→원인→조치→검증→잔존→교훈 (근거 뱃지)."""
        try:
            return services.rca.chain(issue_id)
        except IssueNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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

    @app.get(f"{prefix}/source-map", response_model=SourceCoverage)
    def source_map() -> SourceCoverage:
        """출처 지도 — 컬렉션별 가상/반입/연동 집계 (파편화·실데이터 진척 가시화)."""
        return services.source_map.coverage()

    @app.get(f"{prefix}/entity-resolution", response_model=EntityResolutionReport)
    def entity_resolution() -> EntityResolutionReport:
        """엔티티 해석 — IP 별칭표 + 미해석 토큰 큐 (식별자 파편화 가시화)."""
        return services.entity_resolution.report()

    @app.get(f"{prefix}/action-draft/scenario/{{scenario_id}}", response_model=ActionDraft)
    def action_draft(scenario_id: str) -> ActionDraft:
        """실행 초안 — 시나리오 기준 결정론 리뷰 팩 초안 (저장 아님, 사람이 검토·커밋)."""
        try:
            return services.action_draft.draft(scenario_id)
        except ScenarioNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(f"{prefix}/review-packs", response_model=list[ReviewPackSummary])
    def review_packs() -> list[ReviewPackSummary]:
        """리뷰 팩 목록 — 함께 검토할 시나리오 묶음."""
        return services.review_pack.list_packs()

    @app.get(f"{prefix}/review-packs/{{pack_id}}", response_model=ReviewPackDocument)
    def review_pack(pack_id: str) -> ReviewPackDocument:
        """리뷰 팩 조립 — 묶인 시나리오들의 실행 초안+근거 태세 (저장 아님, 결정은 사람이)."""
        try:
            return services.review_pack.assemble(pack_id)
        except ReviewPackNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

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

    @app.get(f"{prefix}/ask/presets")
    def ask_presets() -> list[dict[str, str]]:
        """프리셋 질문 5종 — 원점 문서 데모 질문."""
        return PRESET_QUESTIONS

    @app.post(f"{prefix}/ask", response_model=AskResult)
    def ask(request: AskRequest) -> AskResult:
        """Ask SoC 질의 — 검색(결정론) → LLM 근거 인용 답변 (데이터 수정 아님).

        LLM 미가용/검증 거부 시 검색 결과 요약만으로 답한다.
        """
        return services.ask.ask(request.question)

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

    @app.get(f"{prefix}/ingest/mappings", response_model=list[IngestMappingInfo])
    def list_ingest_mappings() -> list[IngestMappingInfo]:
        """반입 매핑 목록 — 반입 센터의 매핑 선택·템플릿 다운로드용 (읽기 전용)."""
        return [
            IngestMappingInfo(
                name=m.name,
                label_ko=m.label_ko,
                target_collection=m.target_collection,
                columns=list(m.column_map.keys()),
                required_columns=sorted(m.required_columns),
            )
            for m in services.ingest.mappings()
        ]

    @app.get(f"{prefix}/decisions", response_model=list[Decision])
    def list_decisions(
        project_id: str | None = Query(default=None),
        event_id: str | None = Query(default=None),
    ) -> list[Decision]:
        """결정 목록 — 리뷰 팩의 '이 팩에서 나온 결정' 표시용 (읽기 전용)."""
        decisions = [
            d for d in services.repo.list("decisions") if isinstance(d, Decision)
        ]
        if project_id:
            decisions = [d for d in decisions if d.project_id == project_id]
        if event_id:
            decisions = [d for d in decisions if d.event_id == event_id]
        return sorted(decisions, key=lambda d: d.id)

    @app.get(f"{prefix}/ingest/quarantine", response_model=list[QuarantineEntry])
    def list_ingest_quarantine(
        mapping: str | None = Query(default=None, description="매핑 이름 필터"),
    ) -> list[QuarantineEntry]:
        """보류 행 목록 (J1 2단계) — 거부 행의 큐레이션 대기열 (읽기 전용).

        수정용 CSV는 프론트가 원본 열 값으로 재구성한다. 같은 id의 행이 수용되면
        해소되고, 원 배치 rollback 시 함께 제거된다.
        """
        return services.ingest.list_quarantine(mapping)

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
