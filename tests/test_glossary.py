"""glossary 커버리지 테스트 — 모든 공개 모델/필드/enum에 label_ko가 있어야 한다."""

from backend.ontology import COLLECTIONS, RUNTIME_CONTRACTS
from backend.ontology.glossary import (
    enum_label,
    export_glossary,
    field_label,
    find_missing_labels,
    object_label,
)


def all_root_models() -> list[type]:
    models = [model for _, model in COLLECTIONS.values()]
    models += list(RUNTIME_CONTRACTS.values())
    return models


def test_no_missing_labels() -> None:
    missing = find_missing_labels(all_root_models())
    assert missing == [], f"glossary 누락 {len(missing)}건:\n" + "\n".join(missing)


def test_core_terms() -> None:
    """핵심 도메인 용어의 한국어 라벨 고정 — 변경은 changelog 필수."""
    assert object_label("Project") == "프로젝트"
    assert object_label("DevelopmentEvent") == "개발 이벤트"
    assert field_label("GroundedStatement", "supporting_basis") == "뒷받침 근거"
    assert field_label("GroundedStatement", "confidence") == "확신도"
    assert enum_label("Confidence", "low") == "낮음"
    assert enum_label("SourceOrigin", "synthetic") == "가상"


def test_export_glossary_structure() -> None:
    exported = export_glossary(all_root_models())
    assert set(exported.keys()) == {"objects", "fields", "enums", "value_labels"}
    assert exported["objects"]["Scenario"] == "시나리오"
    assert exported["fields"]["Project"]["phase"] == "프로젝트 단계"


def test_value_labels_cover_all_fixture_values() -> None:
    """U1 값 도메인 커버리지 — fixture(+오버레이)에 등장하는 전 값에 라벨이 있어야 한다.

    반입(CSV/JIRA)으로 새 값이 들어오면 이 테스트가 누락을 드러낸다
    (06_stage16_ui_overhaul.md U1 계약).
    """
    from pathlib import Path

    from backend.loaders.repository import InMemoryRepository
    from backend.ontology.glossary import VALUE_LABELS, value_label

    fixtures = Path(__file__).resolve().parents[1] / "fixtures"
    repo = InMemoryRepository.from_fixtures(fixtures)

    # (도메인, 컬렉션, 필드) — 값 도메인이 실재하는 지점 전수.
    domain_fields = [
        ("project_phase", "projects", "phase"),
        ("scenario_domain", "scenarios", "domain"),
        ("ip_domain", "ip_blocks", "domain"),
        ("action_status", "action_items", "status"),
        ("due_phase", "action_items", "due_phase"),
        ("ip_category", "ip_blocks", "category"),
        ("issue_status", "issues", "status"),
        ("issue_type", "issues", "issue_type"),
        ("fix_type", "issues", "fix_type"),
        ("severity", "issues", "severity"),
        ("severity", "development_events", "severity"),
        ("test_type", "tests", "test_type"),
        ("test_result", "tests", "result"),
        ("event_status", "development_events", "status"),
        ("schedule_signal", "development_events", "schedule_signal"),
        ("availability", "evidence_catalog", "availability"),
        ("confidence_contribution", "evidence_catalog", "confidence_contribution"),
        ("measurement_stage", "evidence_catalog", "measurement_stage"),
        ("scenario_match", "evidence_catalog", "scenario_match"),
        ("request_status", "scenario_requests", "status"),
        ("request_priority", "scenario_requests", "priority"),
        ("requirement_level", "scenario_ip_requirements", "requirement_level"),
        ("direction", "ip_knobs", "power_direction"),
        ("direction", "ip_knobs", "latency_direction"),
        ("direction", "ip_knobs", "bandwidth_direction"),
        ("direction", "ip_knobs", "risk_direction"),
        ("support_status", "ip_capabilities", "support_status"),
        ("evidence_type", "evidence_catalog", "evidence_type"),
        ("role", "roles", "id"),
    ]
    missing: list[str] = []
    for domain, collection, field_name in domain_fields:
        for obj in repo.list(collection):
            value = getattr(obj, field_name, None)
            if value is None or value == "":
                continue
            if value_label(domain, str(value)) is None:
                missing.append(f"{domain}: '{value}' ({collection}.{field_name})")
    assert missing == [], "값 라벨 누락:\n" + "\n".join(sorted(set(missing)))
    # 도메인 사전 자체도 비어 있지 않아야 한다.
    for domain in VALUE_LABELS:
        assert VALUE_LABELS[domain], f"빈 값 도메인: {domain}"


def test_export_glossary_includes_value_labels() -> None:
    exported = export_glossary(all_root_models())
    assert "value_labels" in exported
    assert exported["value_labels"]["availability"]["available"] == "확보"
