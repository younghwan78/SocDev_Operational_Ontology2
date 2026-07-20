"""설계 26 G1 — 게이트 콘솔 파생 뷰 (자동 선택 룰·지배 요인·신뢰도 줄)."""

from __future__ import annotations

from backend.ingest.service import IngestBatch
from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue
from backend.ontology.project import GateCriterion, Project, ProjectMilestone
from backend.services.gate_console import GateConsoleService


def _project(project_id: str = "proj_u") -> Project:
    return Project(id=project_id, name="U", type="mobile", phase="mp")


def _milestone(
    milestone_id: str,
    week: int | None,
    criteria: list[GateCriterion],
    project_id: str = "proj_u",
) -> ProjectMilestone:
    return ProjectMilestone.model_validate(
        {
            "id": milestone_id,
            "project_id": project_id,
            "title": f"게이트 {milestone_id}",
            "description": "-",
            "milestone_type": "release",
            "lifecycle_stage": "es",
            "decision_window": "open",
            **({"week": week} if week is not None else {}),
            "exit_criteria": [c.model_dump() for c in criteria],
        }
    )


def _issue(
    issue_id: str,
    status: str = "open",
    due_week: int | None = None,
    scenarios: list[str] | None = None,
) -> Issue:
    return Issue.model_validate(
        {
            "id": issue_id,
            "project_id": "proj_u",
            "title": f"이슈 {issue_id}",
            "issue_type": "hw_bug",
            "status": status,
            "symptom": "s",
            "confidence": "medium",
            **({"due_week": due_week} if due_week else {}),
            "affected_scope": {"scenarios": scenarios or []},
        }
    )


def _criterion(criterion_id: str = "c1", kind: str = "max_open_issues") -> GateCriterion:
    return GateCriterion(criterion_id=criterion_id, kind=kind, description="-")


class _FakeBatches:
    def __init__(self, batches: list[IngestBatch]) -> None:
        self._batches = batches

    def list_batches(self) -> list[IngestBatch]:
        return self._batches


def _batch(batch_id: str, created_at: str, status: str = "completed") -> IngestBatch:
    return IngestBatch(
        id=batch_id,
        filename="f.csv",
        mapping_name="issues",
        target_collection="issues",
        accepted_count=1,
        rejected_count=0,
        status=status,
        created_at=created_at,
    )


def _console(repo: InMemoryRepository, batches: _FakeBatches | None = None):
    return GateConsoleService(repo, batches).console()


def test_selects_nearest_upcoming_gate_by_reference_week() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects(
        "project_milestones",
        [
            _milestone("ms_past", 10, [_criterion()]),
            _milestone("ms_next", 20, [_criterion()]),
            _milestone("ms_far", 30, [_criterion()]),
        ],
    )
    # 기준 주차 = 최신 활동 주차 (due_week 15) → W20이 최근접 다가올 게이트.
    repo.add_objects("issues", [_issue("iss_1", due_week=15)])
    console = _console(repo)
    assert console.reference_week == 15
    [project] = console.projects
    assert project.selected_milestone_id == "ms_next"
    assert "W15 이후 최근접" in project.selection_note_ko
    assert len(project.reviews) == 3  # 드롭다운 전환용 전체 게이트 판정 포함


def test_all_gates_past_falls_back_to_latest_with_honest_note() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects(
        "project_milestones",
        [_milestone("ms_a", 5, [_criterion()]), _milestone("ms_b", 8, [_criterion()])],
    )
    repo.add_objects("issues", [_issue("iss_1", due_week=15)])
    [project] = _console(repo).projects
    assert project.selected_milestone_id == "ms_b"
    assert "이전" in project.selection_note_ko


def test_no_gated_milestone_is_honest_unassigned() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects("project_milestones", [_milestone("ms_plain", 12, [])])
    [project] = _console(repo).projects
    assert project.selected_milestone_id is None
    assert "게이트 미지정" in project.selection_note_ko
    assert project.reviews == []
    # 타임라인에는 기준 미정의 마일스톤이 유령 칩으로 노출된다 (일정은 보여준다).
    [entry] = project.timeline
    assert entry.milestone_id == "ms_plain"
    assert entry.has_gate is False
    assert entry.verdict is None


def test_timeline_orders_all_milestones_with_verdict_summary() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects(
        "project_milestones",
        [
            # 종결 이슈 없음 → met (미해결 이슈가 있어도 verified_closure는 통과)
            _milestone("ms_gate_late", 30, [_criterion("c3", "verified_closure")]),
            _milestone("ms_plain", 20, []),  # 기준 미정의
            _milestone(
                "ms_gate_fail", 10, [_criterion("c1"), _criterion("c2", "unknown")]
            ),  # 이슈 있음 → not_met 요약
        ],
    )
    repo.add_objects("issues", [_issue("iss_1")])
    [project] = _console(repo).projects
    assert [e.milestone_id for e in project.timeline] == [
        "ms_gate_fail",
        "ms_plain",
        "ms_gate_late",
    ]
    fail, plain, late = project.timeline
    assert (fail.has_gate, fail.verdict) == (True, "not_met")
    assert (plain.has_gate, plain.verdict) == (False, None)
    assert (late.has_gate, late.verdict) == (True, "met")
    assert fail.verdict_ko == "미충족"


def test_gates_without_week_cannot_autoselect() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects("project_milestones", [_milestone("ms_noweek", None, [_criterion()])])
    [project] = _console(repo).projects
    assert project.selected_milestone_id is None
    assert "주차 미지정" in project.selection_note_ko
    assert len(project.reviews) == 1  # 판정 자체는 보여준다


def test_dominant_factor_prefers_issue_count_then_evidence() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects(
        "project_milestones",
        [
            _milestone(
                "ms_gate",
                20,
                [
                    GateCriterion(
                        criterion_id="c_ev",
                        kind="required_evidence",
                        description="실측",
                        evidence_types=["lab_trace"],
                    ),
                    GateCriterion(
                        criterion_id="c_issues",
                        kind="max_open_issues",
                        description="0건",
                    ),
                ],
            )
        ],
    )
    repo.add_objects("issues", [_issue("iss_1", due_week=20), _issue("iss_2")])
    [project] = _console(repo).projects
    [review] = project.reviews
    assert review.dominant is not None
    # 룰: 이슈 수 최다(max_open_issues) → 근거 누락 순 — 근거 기준도 미충족이지만 이슈가 대표.
    assert review.dominant.criterion_id == "c_issues"
    assert review.dominant.headline_ko == "미해결 이슈 2건"
    assert review.dominant.drill == "issues"
    assert review.verdict_line_ko.startswith("미충족 2/2 — 지배 요인: 미해결 이슈 2건")


def test_verdict_lines_for_met_and_not_evaluable() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects(
        "project_milestones",
        [
            _milestone(
                "ms_gate",
                20,
                [
                    _criterion("c1"),  # 이슈 없음 → met
                    _criterion("c2", kind="unknown_rule"),  # → not_evaluable
                ],
            )
        ],
    )
    [project] = _console(repo).projects
    [review] = project.reviews
    assert review.dominant is None
    assert "충족 1/2" in review.verdict_line_ko
    assert "판정 불가 1건" in review.verdict_line_ko


def test_trust_line_counts_issue_links_and_latest_completed_batch() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    repo.add_objects(
        "issues",
        [_issue("iss_linked", scenarios=["sc_1"]), _issue("iss_bare")],
    )
    batches = _FakeBatches(
        [
            _batch("b1", "2026-07-01T00:00:00+00:00"),
            _batch("b2", "2026-07-19T00:00:00+00:00"),
            _batch("b3", "2026-07-20T00:00:00+00:00", status="rolled_back"),
        ]
    )
    [project] = _console(repo, batches).projects
    assert project.trust.issue_total == 2
    assert project.trust.issue_linked == 1
    # rolled_back 배치는 신선도에 계수하지 않는다.
    assert project.trust.latest_batch_at == "2026-07-19T00:00:00+00:00"
    assert project.trust.note_ko  # "이 판정이 못 보는 것" 문구 존재


def test_no_batches_is_none_not_fake_timestamp() -> None:
    repo = InMemoryRepository({})
    repo.add_objects("projects", [_project()])
    [project] = _console(repo).projects
    assert project.trust.latest_batch_at is None
