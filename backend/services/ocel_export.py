"""OCEL 2.0 export — 온톨로지+버전 로그의 표준 교환 포맷 직렬화 (설계 22 §4).

읽기 전용 파생 뷰다: 내부 계약을 바꾸지 않고 프로세스 마이닝 도구
(PM4Py/Celonis 등)가 읽는 OCEL 2.0 JSON 문서를 만든다.

시간 축은 transaction time(recorded_at) — domain time(week)은 timestamp로
변환하지 않고 객체 attribute로 남긴다 (가짜 타임스탬프 제조 금지, 설계 15 §3).
같은 저장소 상태는 같은 출력을 만든다 (정렬 고정, 생성 시각 미포함).

56의 snapshot export/compare 회귀 도구 계열(이식 금지 대상)과 무관하다 —
이것은 교환 포맷 산출이지 회귀 스냅샷이 아니다.
"""

from __future__ import annotations

from typing import Any

from backend.ingest.history import ObjectVersion, VersionSourceProtocol
from backend.ingest.mappings import field_values
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology import COLLECTIONS, OntologyObject
from backend.services.source_map import LINK_FIELDS

# 속성 시각 미상(버전 로그 없는 현재 상태) 표기용 — 거짓 시각을 만들지 않는다.
EPOCH = "1970-01-01T00:00:00+00:00"

TIME_AXIS_NOTE_KO = (
    "time axis = transaction time (recorded_at) — twin이 알게 된 시각. "
    "domain time(week)은 이벤트 시각이 아니라 객체 attribute다."
)

_SCALAR_TYPES = (bool, int, float, str)


def _attr_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    return "string"


def _scalar_attributes(dump: dict[str, Any]) -> dict[str, Any]:
    """OCEL 객체 attribute — 스칼라 필드만, id/source(계보 메타)는 제외."""
    return {
        key: value
        for key, value in sorted(dump.items())
        if key not in {"id", "source"} and isinstance(value, _SCALAR_TYPES)
    }


def _event_type(
    collection: str, version: ObjectVersion, previous_status: str | None
) -> tuple[str, str | None]:
    """이벤트 타입 — status 전이가 동반되면 세분한다. (타입, 새 status) 반환."""
    status = None
    if version.payload is not None:
        raw = version.payload.get("status")
        if isinstance(raw, str):
            status = raw
    if status is not None and status != previous_status:
        return f"{collection}_status_{status}", status
    return f"{collection}_{version.change_kind}", status if status else previous_status


def build_ocel(
    repo: RepositoryProtocol, versions: VersionSourceProtocol
) -> dict[str, Any]:
    """OCEL 2.0 JSON 문서 (dict) — objectTypes/eventTypes/objects/events."""
    dumps: dict[str, list[tuple[OntologyObject, dict[str, Any]]]] = {}
    exported_ids: set[str] = set()
    for collection in COLLECTIONS:
        rows = [
            (obj, obj.model_dump(mode="json"))
            for obj in repo.list(collection)
            if isinstance(obj, OntologyObject)
        ]
        if rows:
            dumps[collection] = rows
            exported_ids.update(obj.id for obj, _ in rows)

    # 객체별 마지막 기록 시각 — attribute 시각으로 쓴다 (미상은 EPOCH).
    last_recorded: dict[tuple[str, str], str] = {}
    version_rows: dict[str, list[ObjectVersion]] = {}
    for collection in dumps:
        entries = versions.collection_versions(collection)
        version_rows[collection] = entries
        for entry in entries:
            key = (collection, entry.object_id)
            known = last_recorded.get(key)
            if known is None or entry.recorded_at > known:
                last_recorded[key] = entry.recorded_at

    object_types: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    for collection, rows in sorted(dumps.items()):
        attr_types: dict[str, str] = {}
        for _, dump in rows:
            for name, value in _scalar_attributes(dump).items():
                attr_types.setdefault(name, _attr_type(value))
        object_types.append(
            {
                "name": collection,
                "attributes": [
                    {"name": name, "type": attr_types[name]}
                    for name in sorted(attr_types)
                ],
            }
        )
        link_paths = LINK_FIELDS.get(collection, [])
        for obj, dump in rows:
            attr_time = last_recorded.get((collection, obj.id), EPOCH)
            relationships = [
                {"objectId": target, "qualifier": path}
                for path in link_paths
                for target in field_values(dump, path)
                if target in exported_ids
            ]
            objects.append(
                {
                    "id": obj.id,
                    "type": collection,
                    "attributes": [
                        {"name": name, "time": attr_time, "value": value}
                        for name, value in _scalar_attributes(dump).items()
                    ],
                    "relationships": relationships,
                }
            )

    events: list[dict[str, Any]] = []
    event_type_names: set[str] = set()
    for collection, entries in sorted(version_rows.items()):
        link_paths = LINK_FIELDS.get(collection, [])
        previous_status: dict[str, str | None] = {}
        for entry in sorted(entries, key=lambda e: (e.object_id, e.version)):
            type_name, new_status = _event_type(
                collection, entry, previous_status.get(entry.object_id)
            )
            previous_status[entry.object_id] = new_status
            event_type_names.add(type_name)
            relationships = [{"objectId": entry.object_id, "qualifier": "subject"}]
            if entry.payload is not None:
                relationships += [
                    {"objectId": target, "qualifier": path}
                    for path in link_paths
                    for target in field_values(entry.payload, path)
                    if target in exported_ids
                ]
            events.append(
                {
                    "id": f"{collection}:{entry.object_id}:v{entry.version}",
                    "type": type_name,
                    "time": entry.recorded_at,
                    "attributes": [],
                    "relationships": relationships,
                }
            )
    # 이벤트는 시간순 — 동시각은 id 순 (결정론).
    events.sort(key=lambda e: (e["time"], e["id"]))

    return {
        "meta": {"note_ko": TIME_AXIS_NOTE_KO, "spec": "OCEL 2.0 (JSON)"},
        "objectTypes": object_types,
        "eventTypes": [
            {"name": name, "attributes": []} for name in sorted(event_type_names)
        ],
        "objects": objects,
        "events": events,
    }
