"""RCA 서비스 테스트 — 7단 체인/근거 뱃지/검증 경고의 결정론 고정.

수용 기준: '검증 테스트 없는 close 이슈'가 드러남, RCA 완결 체인 1건 이상.
"""

from pathlib import Path

import pytest
from backend.loaders.repository import InMemoryRepository
from backend.services.rca import (
    STEP_LABELS,
    IssueNotFoundError,
    RCAService,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def service() -> RCAService:
    return RCAService(InMemoryRepository.from_fixtures(FIXTURES))


def test_issue_list_covers_all_issues(service) -> None:
    summaries = service.list_issues()
    assert len(summaries) >= 36, "56 유래 4건 + 58 추가 32건"
    assert all(s.verification in ("verified", "unverified", "no_tests") for s in summaries)


def test_closed_without_verification_flagged_and_first(service) -> None:
    """수용 기준 — close됐지만 검증 테스트 없는 이슈가 드러나고 앞에 온다."""
    summaries = service.list_issues()
    flagged = [s for s in summaries if s.closed_without_verification]
    assert flagged, "검증 없는 종결 이슈 사례가 있어야 한다"
    flagged_ids = {s.issue_id for s in flagged}
    assert "issue_isp_hdr_latency_closed_unverified_u" in flagged_ids
    assert "issue_dpu_qos_frame_drop_closed_unverified_u" in flagged_ids
    assert "issue_abox_lowpower_path_closed_unverified_u" in flagged_ids
    # 경고 이슈가 목록 선두에 온다.
    boundary = len(flagged)
    assert all(s.closed_without_verification for s in summaries[:boundary])


def test_chain_has_seven_steps_in_order(service) -> None:
    chain = service.chain("issue_isp_csid_bw_overrun_u")
    assert [n.step for n in chain.nodes] == [
        "symptom", "impact", "root_cause", "action",
        "verification", "residual_risk", "lesson",
    ]
    assert all(n.step_ko == STEP_LABELS[n.step] for n in chain.nodes)
    assert all(n.badge in ("green", "red", "yellow") for n in chain.nodes)
    assert all(n.badge_reason_ko for n in chain.nodes)


def test_complete_chain_all_green(service) -> None:
    """수용 기준 — RCA 완결 체인: 증상→교훈 전부 근거와 함께 green."""
    chain = service.chain("issue_isp_csid_bw_overrun_u")
    assert chain.verification == "verified"
    assert chain.closed_without_verification is False
    assert chain.alert_ko is None
    assert [n.badge for n in chain.nodes] == ["green"] * 7
    verification = next(n for n in chain.nodes if n.step == "verification")
    assert {i.ref_id for i in verification.items} == {
        "test_isp_csid_bw_regression", "test_isp_csid_bw_power",
    }


def test_closed_unverified_chain_red_verification(service) -> None:
    """핵심 화면 사유 — 종결 이슈의 검증 노드가 빨갛게 뜬다."""
    chain = service.chain("issue_isp_hdr_latency_closed_unverified_u")
    assert chain.closed_without_verification is True
    assert chain.alert_ko and "검증 테스트가 없습니다" in chain.alert_ko
    verification = next(n for n in chain.nodes if n.step == "verification")
    assert verification.badge == "red"
    assert verification.items == []


def test_workaround_only_action_yellow(service) -> None:
    chain = service.chain("issue_isp_m2m_ddr_traffic_v")
    action = next(n for n in chain.nodes if n.step == "action")
    assert action.badge == "yellow", "workaround만 있으면 노랑"
    verification = next(n for n in chain.nodes if n.step == "verification")
    assert verification.badge == "yellow", "failed 테스트는 미검증(노랑)"


def test_open_issue_candidates_yellow(service) -> None:
    chain = service.chain("issue_isp_lowlight_power_u")
    cause = next(n for n in chain.nodes if n.step == "root_cause")
    assert cause.badge == "yellow"
    assert all(item.badge == "yellow" for item in cause.items)


def test_legacy_issue_without_rca_fields(service) -> None:
    """56 유래 이슈(확장 필드 없음)도 체인이 성립하고 공백이 뱃지로 드러난다."""
    chain = service.chain("issue_u_uhd60_eis_power_gap")
    verification = next(n for n in chain.nodes if n.step == "verification")
    assert verification.badge == "red"
    cause = next(n for n in chain.nodes if n.step == "root_cause")
    assert cause.badge in ("yellow", "red")


def test_impact_node_resolves_names(service) -> None:
    chain = service.chain("issue_dpu_underrun_composition_u")
    impact = next(n for n in chain.nodes if n.step == "impact")
    titles = [i.title for i in impact.items]
    assert "Display Video Mode Underrun Prevention" in titles
    assert "DPU" in titles


def test_filters(service) -> None:
    only_w = service.list_issues(project_id="project_w")
    assert only_w and all(s.project_id == "project_w" for s in only_w)
    no_tests = service.list_issues(verification="no_tests")
    assert no_tests and all(s.verification == "no_tests" for s in no_tests)


def test_deterministic(service) -> None:
    a = service.chain("issue_mfc_4k60_power_spike_u")
    b = service.chain("issue_mfc_4k60_power_spike_u")
    assert a.model_dump() == b.model_dump()


def test_unknown_issue_raises(service) -> None:
    with pytest.raises(IssueNotFoundError):
        service.chain("issue_없음")


def test_freshness_stale_and_overdue_signals() -> None:
    """J3 — 미해결+무활동=정체, 목표 주차 경과=지연. 종결 이슈는 판정하지 않는다."""
    from pathlib import Path

    from backend.loaders.repository import InMemoryRepository
    from backend.ontology.event import Issue
    from backend.services.rca import RCAService

    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    repo = InMemoryRepository.from_fixtures(fixtures)
    base = {
        "project_id": "project_u",
        "title": "신선도 테스트",
        "issue_type": "underrun",
        "status": "open",
        "symptom": "s",
        "confidence": "medium",
    }
    # 기준 주차는 데이터 최신 활동 주차 — 이 이슈로 W50을 만들어 통제한다.
    repo.add_objects(
        "issues",
        [
            Issue.model_validate(
                {**base, "id": "issue_fresh_anchor", "updated_week": 50}
            ),
            Issue.model_validate(
                {**base, "id": "issue_fresh_stale", "updated_week": 45}
            ),
            Issue.model_validate(
                {**base, "id": "issue_fresh_overdue", "updated_week": 49, "due_week": 48}
            ),
            Issue.model_validate(
                {
                    **base,
                    "id": "issue_fresh_closed",
                    "status": "closed",
                    "updated_week": 40,
                    "due_week": 41,
                }
            ),
        ],
    )
    summaries = {s.issue_id: s for s in RCAService(repo).list_issues()}

    stale = summaries["issue_fresh_stale"]
    assert stale.stale and not stale.overdue
    assert stale.freshness_ko and "정체" in stale.freshness_ko and "W45" in stale.freshness_ko

    overdue = summaries["issue_fresh_overdue"]
    assert overdue.overdue and not overdue.stale
    assert overdue.freshness_ko and "지연" in overdue.freshness_ko and "W48" in overdue.freshness_ko

    anchor = summaries["issue_fresh_anchor"]
    assert not anchor.stale and not anchor.overdue and anchor.freshness_ko is None

    closed = summaries["issue_fresh_closed"]
    assert not closed.stale and not closed.overdue, "종결 이슈는 신선도 판정 제외"


def test_doc_candidates_reverse_link() -> None:
    """J4 — 이슈를 언급하는 청크가 RCA 상세의 관련 문서 후보로 역링크된다 (증거 아님)."""
    from pathlib import Path

    from backend.loaders.repository import InMemoryRepository
    from backend.ontology.event import Issue
    from backend.ontology.evidence import SemanticChunk
    from backend.services.rca import RCAService

    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    repo = InMemoryRepository.from_fixtures(fixtures)
    repo.add_objects(
        "issues",
        [
            Issue.model_validate(
                {
                    "id": "issue_doc_case",
                    "project_id": "project_u",
                    "title": "문서 연결 테스트",
                    "issue_type": "underrun",
                    "status": "open",
                    "symptom": "s",
                    "confidence": "medium",
                    "doc_refs": ["https://confluence.local/pages/123"],
                }
            )
        ],
    )
    repo.add_objects(
        "semantic_chunks",
        [
            SemanticChunk.model_validate(
                {
                    "id": "chunk_confluence_123",
                    "chunk_text": "underrun 분석 회의록\n" + "x" * 200,
                    "source_id": "123",
                    "source_type": "confluence_page",
                    "embedding_status": "pending",
                    "evidence_confidence": "low",
                    "related_issue_ids": ["issue_doc_case"],
                }
            )
        ],
    )
    chain = RCAService(repo).chain("issue_doc_case")
    assert chain.doc_refs == ["https://confluence.local/pages/123"]
    assert len(chain.doc_candidates) == 1
    candidate = chain.doc_candidates[0]
    assert candidate.ref_collection == "semantic_chunks"
    assert candidate.description.endswith("…"), "본문은 160자 미리보기로 자른다"
