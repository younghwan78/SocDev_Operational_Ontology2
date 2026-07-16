"""P4 what-if 주입 — 가정 실험의 결정론·불변성·등급 재계산 (설계 16 §5)."""

from __future__ import annotations

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.ontology.event import Issue
from backend.ontology.ip import IPBlock
from backend.ontology.scenario import Scenario, ScenarioGroup
from backend.services.what_if import (
    InvalidAssumptionError,
    UnknownTargetError,
    WhatIfAssumption,
    WhatIfService,
)

_SRC = {"origin": "synthetic", "ref": "test:whatif"}


def _repo(issue_status: str = "open") -> InMemoryRepository:
    """최소 우주 — 시나리오 1 × IP 1 × 그 조합을 겨누는 이슈 1."""
    scenario = Scenario.model_validate(
        {
            "id": "scn_x",
            "source": _SRC,
            "name": "테스트 시나리오",
            "description": "what-if 검증용",
            "domain": "camera",
            "scenario_class": "recording",
            "scenario_group_id": "grp_x",
            "project_relevance": ["proj_u"],
            "uses_ip_blocks": ["ip_x"],
            "customer_request_relevance": "high",
            "development_relevance": "high",
            "dou_relevance": "low",
            "iq_relevance": "low",
            "sustain_power_relevance": "low",
            "hw_pipeline_change_sensitivity": "low",
            "sw_control_complexity": "low",
        }
    )
    group = ScenarioGroup.model_validate(
        {
            "id": "grp_x",
            "source": _SRC,
            "name": "테스트 그룹",
            "purpose": "테스트",
            "scenarios": ["scn_x"],
        }
    )
    ip = IPBlock.model_validate(
        {
            "id": "ip_x",
            "source": _SRC,
            "name": "ISP-X",
            "category": "functional_mm_ip",
            "domain": "camera",
        }
    )
    issue = Issue.model_validate(
        {
            "id": "iss_x",
            "source": _SRC,
            "project_id": "proj_u",
            "title": "대역폭 초과",
            "issue_type": "bandwidth_overrun",
            "status": issue_status,
            "symptom": "프레임 드랍",
            "confidence": "medium",
            "affected_scope": {"scenarios": ["scn_x"], "ip_blocks": ["ip_x"]},
        }
    )
    return InMemoryRepository(
        {
            "scenarios": [scenario],
            "scenario_groups": [group],
            "ip_blocks": [ip],
            "issues": [issue],
        }
    )


def test_resolving_open_issue_lowers_grade() -> None:
    """수용 기준 1 — open→resolved 가정 시 미해결 이슈 근거가 빠진 등급으로 재계산."""
    repo = _repo("open")
    result = WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="resolved")]
    )
    assert len(result.changed_rows) == 1
    row = result.changed_rows[0]
    assert (row.baseline_grade, row.projected_grade) == ("high", "medium")
    cell = row.changed_cells[0]
    assert cell.ip_id == "ip_x"
    assert (cell.baseline_grade, cell.projected_grade) == ("high", "medium")
    # 재계산 근거는 실제 위험 룰의 산출물 — 과거 이슈 패턴으로 바뀐다.
    assert any(b.rule == "past_issue_pattern" for b in cell.projected_basis)
    # 가정 에코 — assumption 지위 + confidence 상한.
    assumption = result.assumptions[0]
    assert assumption.basis_type == "assumption"
    assert assumption.confidence == "medium"
    assert (assumption.from_value, assumption.to_value) == ("open", "resolved")


def test_reopening_closed_issue_raises_grade() -> None:
    """반대 방향 — closed→open 가정 시 등급이 올라간다."""
    repo = _repo("closed")
    result = WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="open")]
    )
    row = result.changed_rows[0]
    assert (row.baseline_grade, row.projected_grade) == ("medium", "high")


def test_repository_is_never_mutated() -> None:
    """수용 기준 2 — 어떤 경우에도 저장소 불변 (ephemeral overlay)."""
    repo = _repo("open")
    WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="resolved")]
    )
    issue = repo.get("issues", "iss_x")
    assert isinstance(issue, Issue) and issue.status == "open"


def test_unknown_target_and_invalid_value_rejected() -> None:
    repo = _repo("open")
    service = WhatIfService(repo)
    with pytest.raises(UnknownTargetError):
        service.run(
            [WhatIfAssumption(kind="issue_status", target_id="없는_이슈", value="open")]
        )
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="이상한값")]
        )
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [WhatIfAssumption(kind="없는_종류", target_id="iss_x", value="open")]
        )
    # 실패한 실행도 저장소를 건드리지 않는다.
    issue = repo.get("issues", "iss_x")
    assert isinstance(issue, Issue) and issue.status == "open"


def test_deterministic_same_input_same_output() -> None:
    """수용 기준 4 — 동일 입력 동일 출력."""
    repo = _repo("open")
    service = WhatIfService(repo)
    assumptions = [
        WhatIfAssumption(kind="issue_status", target_id="iss_x", value="resolved")
    ]
    assert service.run(assumptions).model_dump() == service.run(assumptions).model_dump()


def test_no_change_assumption_reports_unchanged() -> None:
    """변화 없음도 명시적으로 보고된다."""
    repo = _repo("open")
    result = WhatIfService(repo).run(
        [WhatIfAssumption(kind="issue_status", target_id="iss_x", value="open")]
    )
    assert result.changed_rows == []
    assert result.unchanged_scenario_count == 1

# ---------------------------------------------------------- Q2 확장 (설계 17 §3)


def test_new_issue_injection_raises_grade_and_leaves_repo_clean() -> None:
    """수용 기준 1 — 가정 이슈 주입이 open_issue 룰로 재계산되고 저장소엔 없다."""
    repo = _repo("resolved")  # 기존 이슈는 해결 상태 — baseline은 과거 패턴(중간)
    result = WhatIfService(repo).run(
        [
            WhatIfAssumption(
                kind="new_issue",
                target_id="iss_hypo",
                scenario_ids=["scn_x"],
                ip_ids=["ip_x"],
                severity="high",
                title="가정: 신규 대역폭 이슈",
                note="8K30 동시 동작 가정",
            )
        ]
    )
    row = result.changed_rows[0]
    assert (row.baseline_grade, row.projected_grade) == ("medium", "high")
    assert any(
        b.rule == "open_issue" for c in row.changed_cells for b in c.projected_basis
    )
    # 가정 이슈는 overlay에만 존재 — 저장소와 이슈 신호 delta로 확인.
    assert repo.get("issues", "iss_hypo") is None
    appeared = [c for c in result.changed_issue_signals if c.appeared]
    assert [c.issue_id for c in appeared] == ["iss_hypo"]
    # 에코: 신규 주입은 from 없음 → to=open(기본), confidence 상한 유지.
    echo = result.assumptions[0]
    assert (echo.from_value, echo.to_value) == (None, "open")
    assert echo.confidence == "medium"


def test_new_issue_rejects_existing_id_and_bad_refs() -> None:
    """수용 기준 2 — 기존 id·미존재 참조는 400급 오류, 저장소 불변."""
    repo = _repo("open")
    service = WhatIfService(repo)
    base = {"kind": "new_issue", "scenario_ids": ["scn_x"], "ip_ids": ["ip_x"]}
    with pytest.raises(InvalidAssumptionError):
        service.run([WhatIfAssumption(**base, target_id="iss_x")])  # 실데이터와 충돌
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [
                WhatIfAssumption(
                    kind="new_issue",
                    target_id="iss_hypo",
                    scenario_ids=["없는_시나리오"],
                    ip_ids=["ip_x"],
                )
            ]
        )
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [WhatIfAssumption(kind="new_issue", target_id="iss_hypo", scenario_ids=["scn_x"], ip_ids=[])]
        )
    assert repo.get("issues", "iss_hypo") is None


def _repo_with_due_week() -> InMemoryRepository:
    repo = _repo("open")
    issue = repo.get("issues", "iss_x")
    assert isinstance(issue, Issue)
    shifted = issue.model_copy(update={"due_week": 20, "updated_week": 20})
    repo.remove_by_ids("issues", ["iss_x"])
    repo.add_objects("issues", [shifted])
    return repo


def test_week_shift_changes_overdue_signal() -> None:
    """수용 기준 3 — due_week 시프트가 지연 신호 delta로 나타난다."""
    repo = _repo_with_due_week()
    result = WhatIfService(repo).run(
        [
            WhatIfAssumption(
                kind="issue_week_shift", target_id="iss_x", week_delta=-5
            )
        ]
    )
    echo = result.assumptions[0]
    assert (echo.field, echo.from_value, echo.to_value) == ("due_week", "20", "15")
    signal = next(c for c in result.changed_issue_signals if c.issue_id == "iss_x")
    assert "지연: 아니오 → 예" in signal.changes
    # 저장소 불변.
    issue = repo.get("issues", "iss_x")
    assert isinstance(issue, Issue) and issue.due_week == 20


# ------------------------------------------------- W1 가정 후보 (설계 18 §3)


def _candidate_repo() -> InMemoryRepository:
    """후보 4룰이 각각 발화하는 우주 — 검증 없는 종결 / 미해결 고심각+목표 주차 / 위험 이벤트."""
    from backend.ontology.event import DevelopmentEvent

    repo = _repo("open")
    open_issue = repo.get("issues", "iss_x")
    assert isinstance(open_issue, Issue)
    high_with_due = open_issue.model_copy(
        update={"severity": "high", "due_week": 20, "updated_week": 20}
    )
    closed_unverified = Issue.model_validate(
        {
            "id": "iss_closed",
            "source": _SRC,
            "project_id": "proj_u",
            "title": "검증 없이 종결된 이슈",
            "issue_type": "bandwidth_overrun",
            "status": "closed",
            "symptom": "종결 근거 미기록",
            "confidence": "low",
            "affected_scope": {"scenarios": ["scn_x"], "ip_blocks": ["ip_x"]},
        }
    )
    repo.remove_by_ids("issues", ["iss_x"])
    repo.add_objects("issues", [high_with_due, closed_unverified])
    repo.add_objects(
        "development_events",
        [
            DevelopmentEvent.model_validate(
                {
                    "id": "ev_risk",
                    "source": _SRC,
                    "project_id": "proj_u",
                    "title": "위험 일정 이벤트",
                    "description": "검토 창이 닫히는 중",
                    "event_type": "review",
                    "event_category": "schedule",
                    "schedule_signal": "at_risk",
                }
            )
        ],
    )
    return repo


def test_candidates_derived_from_signals() -> None:
    """수용 기준 1·3 — 4룰이 각각 후보를 내고, 룰 순서 + id 정렬이 결정론이다."""
    service = WhatIfService(_candidate_repo())
    result = service.candidates()
    by_rule = {(c.rule, c.target_id): c for c in result.candidates}

    unverified = by_rule[("unverified_close", "iss_closed")]
    assert (unverified.kind, unverified.value) == ("issue_status", "open")
    assert "검증" in unverified.basis_note_ko

    resolve = by_rule[("open_high_resolve", "iss_x")]
    assert (resolve.kind, resolve.value) == ("issue_status", "resolved")

    shift = by_rule[("due_week_shift", "iss_x")]
    assert (shift.kind, shift.week_delta) == ("issue_week_shift", -2)
    assert "W20" in shift.basis_note_ko

    event = by_rule[("event_at_risk", "ev_risk")]
    assert (event.kind, event.value) == ("event_schedule_signal", "on_track")

    # 룰 순서 고정 + 결정론 (점수 없음).
    assert [c.rule for c in result.candidates] == [
        "unverified_close",
        "open_high_resolve",
        "due_week_shift",
        "event_at_risk",
    ]
    assert result.candidates == service.candidates().candidates


def test_candidates_project_filter() -> None:
    service = WhatIfService(_candidate_repo())
    assert len(service.candidates("proj_u").candidates) == 4
    assert service.candidates("proj_v").candidates == []


def test_candidates_are_executable_assumptions() -> None:
    """수용 기준 2 — 후보 좌표를 그대로 POST /what-if에 넣으면 계산된다."""
    repo = _candidate_repo()
    service = WhatIfService(repo)
    for candidate in service.candidates().candidates:
        result = service.run(
            [
                WhatIfAssumption(
                    kind=candidate.kind,
                    target_id=candidate.target_id,
                    value=candidate.value,
                    week_delta=candidate.week_delta,
                )
            ]
        )
        assert result.assumptions[0].target_id == candidate.target_id


def test_week_shift_requires_delta_and_due_week() -> None:
    repo = _repo("open")  # iss_x에는 due_week가 없다
    service = WhatIfService(repo)
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [WhatIfAssumption(kind="issue_week_shift", target_id="iss_x", week_delta=2)]
        )
    with pytest.raises(InvalidAssumptionError):
        service.run(
            [WhatIfAssumption(kind="issue_week_shift", target_id="iss_x")]
        )
    with pytest.raises(InvalidAssumptionError):
        service.run([WhatIfAssumption(kind="issue_status", target_id="iss_x")])
