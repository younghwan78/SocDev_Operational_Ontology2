"""설계 24 — 링크 제안 룰 3종 검증 (매치/제외/변별력/프로젝트 필터)."""

from __future__ import annotations

from pathlib import Path

from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue
from backend.ontology.ip import IPBlock
from backend.ontology.scenario import Scenario
from backend.services.link_proposals import LinkProposalService

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _scenario(
    scenario_id: str,
    name: str,
    uses: list[str] | None = None,
    relevance: list[str] | None = None,
) -> Scenario:
    return Scenario.model_validate(
        {
            "id": scenario_id,
            "name": name,
            "description": "-",
            "domain": "camera",
            "scenario_class": "recording",
            "scenario_group_id": "grp",
            "uses_ip_blocks": uses or [],
            "project_relevance": relevance or [],
            "customer_request_relevance": "high",
            "development_relevance": "high",
            "dou_relevance": "high",
            "iq_relevance": "high",
            "sustain_power_relevance": "high",
            "hw_pipeline_change_sensitivity": "high",
            "sw_control_complexity": "high",
        }
    )


def _ip(ip_id: str, name: str, aliases: list[str] | None = None) -> IPBlock:
    return IPBlock.model_validate(
        {
            "id": ip_id,
            "name": name,
            "domain": "camera",
            "category": "functional_mm_ip",
            "aliases": aliases or [],
        }
    )


def _issue(
    issue_id: str,
    title: str,
    symptom: str = "-",
    scenarios: list[str] | None = None,
    ip_blocks: list[str] | None = None,
    project_id: str = "proj_u",
) -> Issue:
    return Issue.model_validate(
        {
            "id": issue_id,
            "project_id": project_id,
            "title": title,
            "issue_type": "hw_bug",
            "status": "open",
            "symptom": symptom,
            "confidence": "medium",
            "affected_scope": {
                "scenarios": scenarios or [],
                "ip_blocks": ip_blocks or [],
            },
        }
    )


def _service(
    issues: list[Issue],
    scenarios: list[Scenario] | None = None,
    ips: list[IPBlock] | None = None,
) -> LinkProposalService:
    repo = InMemoryRepository({})
    repo.add_objects("issues", issues)
    if scenarios:
        repo.add_objects("scenarios", scenarios)
    if ips:
        repo.add_objects("ip_blocks", ips)
    return LinkProposalService(repo)


def test_r1_ip_alias_token_match() -> None:
    service = _service(
        [_issue("iss_1", "ISP 야간 프레임 드랍")],
        ips=[_ip("ip_isp", "ISP", aliases=["camera_isp"]), _ip("ip_dpu", "DPU")],
    )
    report = service.report()
    [entry] = report.issues
    ip_proposals = [p for p in entry.proposals if p.rule == "ip_alias_token"]
    assert [p.target_id for p in ip_proposals] == ["ip_isp"]
    assert "isp" in ip_proposals[0].basis_note_ko.lower()


def test_r1_skipped_when_ip_already_linked() -> None:
    service = _service(
        [_issue("iss_1", "ISP 야간 프레임 드랍", ip_blocks=["ip_isp"])],
        ips=[_ip("ip_isp", "ISP")],
    )
    assert service.report().issues == []


def test_r2_scenario_token_with_project_relevance_filter() -> None:
    scenarios = [
        _scenario("uhd60_recording", "UHD60 녹화", relevance=["proj_u"]),
        _scenario("uhd60_other_project", "UHD60 재생", relevance=["proj_v"]),
    ]
    service = _service(
        [_issue("iss_1", "UHD60 전력 초과", project_id="proj_u")],
        scenarios=scenarios,
    )
    [entry] = service.report().issues
    scenario_proposals = [p for p in entry.proposals if p.rule == "scenario_token"]
    # proj_v 전용 시나리오는 제안되지 않는다.
    assert [p.target_id for p in scenario_proposals] == ["uhd60_recording"]
    assert "uhd60" in scenario_proposals[0].basis_note_ko


def test_r2_indistinct_token_excluded() -> None:
    """4개 이상 시나리오에 걸리는 토큰은 비변별 — 제안 근거가 되지 못한다."""
    scenarios = [
        _scenario(f"video_case_{n}", f"video case {n}") for n in range(4)
    ]
    service = _service([_issue("iss_1", "video 이상")], scenarios=scenarios)
    assert service.report().issues == []


def test_r3_scenario_uses_ip_chain() -> None:
    service = _service(
        [_issue("iss_1", "전력 마진 부족", scenarios=["uhd60_recording"])],
        scenarios=[_scenario("uhd60_recording", "UHD60 녹화", uses=["ip_isp", "ip_mif"])],
        ips=[_ip("ip_isp", "ISP"), _ip("ip_mif", "MIF")],
    )
    [entry] = service.report().issues
    chain = [p for p in entry.proposals if p.rule == "scenario_uses_ip"]
    assert {p.target_id for p in chain} == {"ip_isp", "ip_mif"}
    assert all("UHD60 녹화" in p.basis_note_ko for p in chain)
    # 시나리오 링크는 이미 있으므로 시나리오 제안은 없다.
    assert all(p.field == "affected_scope.ip_blocks" for p in entry.proposals)


def test_project_filter_and_deterministic_order() -> None:
    service = _service(
        [
            _issue("iss_b", "ISP 이슈", project_id="proj_u"),
            _issue("iss_a", "ISP 이슈", project_id="proj_u"),
            _issue("iss_v", "ISP 이슈", project_id="proj_v"),
        ],
        ips=[_ip("ip_isp", "ISP")],
    )
    report = service.report("proj_u")
    assert [e.issue_id for e in report.issues] == ["iss_a", "iss_b"]
    assert report.apply_note_ko  # 반영 경로 안내 동반


def test_fixture_smoke_runs_clean() -> None:
    """fixture 위에서 오류 없이 동작 — 건수는 고정하지 않는다 (대부분 연결됨)."""
    repo = InMemoryRepository.from_fixtures(FIXTURES)
    report = LinkProposalService(repo).report()
    for entry in report.issues:
        assert entry.proposals
        for proposal in entry.proposals:
            assert proposal.basis_note_ko
            assert proposal.rule_ko
            assert proposal.field in {
                "affected_scope.scenarios",
                "affected_scope.ip_blocks",
            }
