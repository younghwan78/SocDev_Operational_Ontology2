"""W1 결정 데이터-시점 워터마크 — 해석 우선순위 검증 (설계 22 §2)."""

from __future__ import annotations

from backend.ingest.history import ObjectVersion
from backend.ingest.service import IngestService, MemoryIngestWriter
from backend.loaders.repository import InMemoryRepository
from backend.ontology.decision import Decision
from backend.services.decision_watermark import (
    WATERMARK_INGESTED_AT,
    WATERMARK_PRECAPTURE,
    WATERMARK_VERSION_LOG,
    DecisionWatermarkService,
)


def _decision(decision_id: str, project_id: str = "proj_u", **source: object) -> Decision:
    return Decision.model_validate(
        {
            "id": decision_id,
            "project_id": project_id,
            "event_id": "evt_1",
            "decision_type": "architecture",
            "selected_option": "옵션 B",
            "tradeoff_summary": "전력 우선",
            "source": source or {"origin": "synthetic"},
        }
    )


def _version(
    decision_id: str, version: int, recorded_at: str, kind: str
) -> ObjectVersion:
    payload = _decision(decision_id).model_dump(mode="json", exclude_none=True)
    return ObjectVersion(
        collection="decisions",
        object_id=decision_id,
        version=version,
        change_kind=kind,
        recorded_at=recorded_at,
        batch_id="batch_1" if kind == "created" else "batch_2",
        source_origin="imported",
        payload=payload,
    )


def _service(
    decisions: list[Decision], versions: list[ObjectVersion]
) -> DecisionWatermarkService:
    repo = InMemoryRepository({})
    repo.add_objects("decisions", decisions)
    ingest = IngestService(MemoryIngestWriter(repo))
    ingest._writer.append_versions(versions)  # noqa: SLF001 — 테스트 전용 직접 적재
    return DecisionWatermarkService(repo, ingest)


def test_version_log_created_is_exact_watermark() -> None:
    service = _service(
        [_decision("dec_a")],
        [_version("dec_a", 1, "2026-07-14T09:12:00+00:00", "created")],
    )
    [mark] = service.watermarks()
    assert mark.source == WATERMARK_VERSION_LOG
    assert mark.recorded_at == "2026-07-14T09:12:00+00:00"
    assert mark.batch_id == "batch_1"


def test_updated_first_prefers_ingested_at() -> None:
    """첫 버전이 updated(캡처 전 존재)면 반입 시각이 근사로 우선한다."""
    service = _service(
        [
            _decision(
                "dec_b",
                origin="imported",
                ref="csv:dec.csv",
                ingested_at="2026-07-10T08:00:00+00:00",
            )
        ],
        [_version("dec_b", 1, "2026-07-14T09:12:00+00:00", "updated")],
    )
    [mark] = service.watermarks()
    assert mark.source == WATERMARK_INGESTED_AT
    assert mark.recorded_at == "2026-07-10T08:00:00+00:00"
    assert mark.batch_id is None
    assert "근사" in mark.note_ko


def test_updated_first_without_ingested_at_approximates_with_note() -> None:
    service = _service(
        [_decision("dec_c")],
        [_version("dec_c", 1, "2026-07-14T09:12:00+00:00", "updated")],
    )
    [mark] = service.watermarks()
    assert mark.source == WATERMARK_VERSION_LOG
    assert mark.recorded_at == "2026-07-14T09:12:00+00:00"
    assert "근사" in mark.note_ko


def test_ingested_at_fallback_without_versions() -> None:
    service = _service(
        [
            _decision(
                "dec_d",
                origin="imported",
                ref="csv:dec.csv",
                ingested_at="2026-07-11T10:30:00+00:00",
            )
        ],
        [],
    )
    [mark] = service.watermarks()
    assert mark.source == WATERMARK_INGESTED_AT
    assert mark.recorded_at == "2026-07-11T10:30:00+00:00"


def test_precapture_has_no_replay_entry_point() -> None:
    service = _service([_decision("dec_e")], [])
    [mark] = service.watermarks()
    assert mark.source == WATERMARK_PRECAPTURE
    assert mark.recorded_at is None
    assert "재생할 수 없다" in mark.note_ko


def test_project_filter_and_sorted_output() -> None:
    service = _service(
        [
            _decision("dec_z", project_id="proj_v"),
            _decision("dec_a", project_id="proj_u"),
            _decision("dec_m", project_id="proj_u"),
        ],
        [],
    )
    marks = service.watermarks("proj_u")
    assert [m.decision_id for m in marks] == ["dec_a", "dec_m"]
