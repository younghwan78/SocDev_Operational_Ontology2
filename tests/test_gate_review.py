"""설계 23 — 마일스톤 게이트 판정 룰 검증 (kind 3종 + 범위·예외)."""

from __future__ import annotations

from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue, Test
from backend.ontology.evidence import EvidenceCatalogEntry
from backend.ontology.project import GateCriterion, ProjectMilestone
from backend.services.gate_review import GateReviewService


def _milestone(criteria: list[GateCriterion]) -> ProjectMilestone:
    return ProjectMilestone.model_validate(
        {
            "id": "ms_gate",
            "project_id": "proj_u",
            "title": "ES release",
            "description": "gate test",
            "milestone_type": "release",
            "lifecycle_stage": "es",
            "decision_window": "open",
            "week": 12,
            "exit_criteria": [c.model_dump() for c in criteria],
        }
    )


def _issue(
    issue_id: str,
    status: str = "open",
    severity: str | None = None,
    scenarios: list[str] | None = None,
    verifying: list[str] | None = None,
) -> Issue:
    return Issue.model_validate(
        {
            "id": issue_id,
            "project_id": "proj_u",
            "title": f"이슈 {issue_id}",
            "issue_type": "hw_bug",
            "status": status,
            **({"severity": severity} if severity else {}),
            "symptom": "s",
            "confidence": "medium",
            "affected_scope": {"scenarios": scenarios or []},
            "verifying_test_ids": verifying or [],
        }
    )


def _evidence(
    entry_id: str, evidence_type: str, availability: str, scenario_id: str = "sc_1"
) -> EvidenceCatalogEntry:
    return EvidenceCatalogEntry.model_validate(
        {
            "id": entry_id,
            "project_id": "proj_u",
            "scenario_id": scenario_id,
            "title": f"근거 {entry_id}",
            "evidence_type": evidence_type,
            "availability": availability,
            "confidence_contribution": "medium",
            "is_measurement": True,
            "is_prediction": False,
            "known_limitation": "-",
            "measurement_stage": "silicon",
            "scenario_match": "exact",
            "source_system": "lab",
            "source_ref": "test",
            "week": 10,
        }
    )


def _service(
    criteria: list[GateCriterion],
    issues: list[Issue] | None = None,
    evidence: list[EvidenceCatalogEntry] | None = None,
    tests: list[Test] | None = None,
) -> GateReviewService:
    repo = InMemoryRepository({})
    repo.add_objects("project_milestones", [_milestone(criteria)])
    if issues:
        repo.add_objects("issues", issues)
    if evidence:
        repo.add_objects("evidence_catalog", evidence)
    if tests:
        repo.add_objects("tests", tests)
    return GateReviewService(repo)


def _single_verdict(service: GateReviewService):
    [review] = service.for_projects(["proj_u"])
    [verdict] = review.criteria
    return verdict


def test_max_open_issues_not_met_with_basis() -> None:
    criterion = GateCriterion(
        criterion_id="c1", kind="max_open_issues", description="미해결 0건"
    )
    verdict = _single_verdict(
        _service([criterion], issues=[_issue("iss_1"), _issue("iss_2", status="closed")])
    )
    assert verdict.verdict == "not_met"
    assert verdict.verdict_ko == "미충족"
    assert [b.ref_id for b in verdict.basis] == ["iss_1"]  # 종결 이슈는 계수 안 함


def test_max_open_issues_min_severity_excludes_unrated_with_note() -> None:
    criterion = GateCriterion(
        criterion_id="c1",
        kind="max_open_issues",
        description="높음 이상 0건",
        min_severity="high",
    )
    service = _service(
        [criterion],
        issues=[
            _issue("iss_high", severity="high"),
            _issue("iss_low", severity="low"),
            _issue("iss_unrated"),  # 심각도 미기재 — 계수 제외 + note 명시
        ],
    )
    verdict = _single_verdict(service)
    assert verdict.verdict == "not_met"
    assert [b.ref_id for b in verdict.basis] == ["iss_high"]
    assert "심각도 미기재 1건 제외" in verdict.note_ko


def test_max_open_issues_scenario_scope_filter() -> None:
    criterion = GateCriterion(
        criterion_id="c1",
        kind="max_open_issues",
        description="시나리오 범위 0건",
        scenario_ids=["sc_target"],
    )
    service = _service(
        [criterion],
        issues=[
            _issue("iss_in", scenarios=["sc_target"]),
            _issue("iss_out", scenarios=["sc_other"]),
        ],
    )
    verdict = _single_verdict(service)
    assert [b.ref_id for b in verdict.basis] == ["iss_in"]


def test_required_evidence_met_and_not_met() -> None:
    criterion = GateCriterion(
        criterion_id="c1",
        kind="required_evidence",
        description="실측 근거",
        evidence_types=["lab_trace", "dump"],
    )
    service = _service(
        [criterion],
        evidence=[
            _evidence("ev_1", "lab_trace", "available"),
            _evidence("ev_2", "dump", "missing"),  # 가용 아님 → 누락
        ],
    )
    verdict = _single_verdict(service)
    assert verdict.verdict == "not_met"
    refs = {b.ref_id for b in verdict.basis}
    assert "ev_1" in refs  # 발견된 근거
    assert "missing:dump" in refs  # 누락 유형도 근거로 명시

    met = _single_verdict(
        _service(
            [criterion],
            evidence=[
                _evidence("ev_1", "lab_trace", "available"),
                _evidence("ev_2", "dump", "available"),
            ],
        )
    )
    assert met.verdict == "met"


def test_required_evidence_empty_types_not_evaluable() -> None:
    criterion = GateCriterion(
        criterion_id="c1", kind="required_evidence", description="정의 누락"
    )
    verdict = _single_verdict(_service([criterion]))
    assert verdict.verdict == "not_evaluable"


def test_verified_closure_flags_unverified_and_passes_verified() -> None:
    criterion = GateCriterion(
        criterion_id="c1", kind="verified_closure", description="검증된 종결"
    )
    passed = Test.model_validate(
        {
            "id": "t_pass",
            "title": "회귀",
            "test_type": "regression",
            "result": "passed",
            "project_id": "proj_u",
            "summary": "-",
        }
    )
    service = _service(
        [criterion],
        issues=[
            _issue("iss_ok", status="closed", verifying=["t_pass"]),
            _issue("iss_bad", status="resolved"),  # 검증 없는 종결
            _issue("iss_open"),  # 미종결 — 대상 아님
        ],
        tests=[passed],
    )
    verdict = _single_verdict(service)
    assert verdict.verdict == "not_met"
    assert [b.ref_id for b in verdict.basis] == ["iss_bad"]
    assert "종결 2건 중 검증 없는 종결 1건" in verdict.note_ko


def test_verified_closure_no_closed_issues_is_met_with_note() -> None:
    criterion = GateCriterion(
        criterion_id="c1", kind="verified_closure", description="검증된 종결"
    )
    verdict = _single_verdict(_service([criterion], issues=[_issue("iss_open")]))
    assert verdict.verdict == "met"
    assert "종결 이슈 없음" in verdict.note_ko


def test_unknown_kind_not_evaluable() -> None:
    criterion = GateCriterion(
        criterion_id="c1", kind="unknown_rule", description="미래 kind"
    )
    verdict = _single_verdict(_service([criterion]))
    assert verdict.verdict == "not_evaluable"
    assert "미등재 기준 유형" in verdict.note_ko


def test_milestones_without_criteria_are_excluded() -> None:
    repo = InMemoryRepository({})
    plain = ProjectMilestone.model_validate(
        {
            "id": "ms_plain",
            "project_id": "proj_u",
            "title": "no gate",
            "description": "-",
            "milestone_type": "release",
            "lifecycle_stage": "es",
            "decision_window": "open",
        }
    )
    repo.add_objects("project_milestones", [plain])
    assert GateReviewService(repo).for_projects(["proj_u"]) == []


def test_review_counts_sum() -> None:
    criteria = [
        GateCriterion(criterion_id="c1", kind="max_open_issues", description="0건"),
        GateCriterion(criterion_id="c2", kind="unknown", description="?"),
    ]
    [review] = _service(criteria).for_projects(["proj_u"])
    assert review.met + review.not_met + review.not_evaluable == len(review.criteria)
    assert review.week == 12
