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
    assert set(exported.keys()) == {"objects", "fields", "enums"}
    assert exported["objects"]["Scenario"] == "시나리오"
    assert exported["fields"]["Project"]["phase"] == "프로젝트 단계"
