"""T3 as-of 재구성 — 임의 시점의 twin 상태 재생 (16_digital_twin_followups.md §3).

transaction time(recorded_at) 축 전용이다: "그 시점에 twin이 알던 것"을 재생한다.
"그 시점에 현실이 그랬던 것"(domain time, week 필드)과 섞지 않는다 (설계 15 §3).

재생 규칙 (컬렉션·객체별):
- 버전 이력 없음(캡처 이전 시드/synthetic) → 현재 상태 그대로 포함 — "캡처 이전부터
  존재" 가정. 가정 건수를 meta에 명시한다.
- ts 이전 버전 존재 → 그중 최신 적용 (retracted면 제외, 아니면 그 payload).
- 모든 버전이 ts 이후 + 첫 버전 created → 제외 (그 시점 twin은 몰랐다).
- 모든 버전이 ts 이후 + 첫 버전 updated → 캡처 이전 존재·당시 payload 미상 —
  가장 이른 기록 payload로 근사하고 근사 건수를 meta에 명시한다.

거짓 정밀도 방지: 근사·가정을 숨기지 않고 AsOfMeta로 응답에 동반한다.
기존 읽기 경로는 무변경(설계 15 대안 B) — as-of는 별도 표면이다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.ingest.history import CHANGE_CREATED, ObjectVersion, VersionSourceProtocol
from backend.loaders.protocols import RepositoryProtocol
from backend.loaders.repository import InMemoryRepository
from backend.ontology import COLLECTIONS, OntologyObject
from backend.services.risk import RiskHeatmap


class AsOfMeta(BaseModel):
    """재생 결과의 정직성 메타 — 무엇이 사실이고 무엇이 가정/근사인지."""

    model_config = ConfigDict(extra="forbid")

    as_of: str
    replayed_versions: int  # ts 이전에 기록돼 재생에 사용된 버전 행 수
    precapture_assumed_objects: int  # 버전 이력 없음 → "캡처 이전부터 존재" 가정
    approximated_objects: int  # 당시 payload 미상 → 가장 이른 기록으로 근사
    excluded_objects: int  # 그 시점에 없었던(미생성/철회) 객체
    skipped_invalid: int  # payload 검증 실패로 건너뛴 버전 (정상적으로 0)
    note_ko: str


class AsOfRiskHeatmap(BaseModel):
    """as-of 위험 지도 응답 — 지도 계약(RiskHeatmap)은 현재 뷰와 동일."""

    model_config = ConfigDict(extra="forbid")

    meta: AsOfMeta
    heatmap: RiskHeatmap


class InvalidTimestampError(ValueError):
    pass


def _parse_cutoff(ts: str) -> datetime:
    try:
        cutoff = datetime.fromisoformat(ts)
    except ValueError as exc:
        raise InvalidTimestampError(
            f"시각 형식이 아님: {ts!r} (ISO 8601, 예: 2026-07-15T09:00:00Z)"
        ) from exc
    # naive 입력은 UTC로 간주 — recorded_at은 항상 UTC-aware라 비교 축을 통일한다.
    return cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=UTC)


def _recorded_instant(version: ObjectVersion) -> datetime | None:
    try:
        recorded = datetime.fromisoformat(version.recorded_at)
    except ValueError:
        return None
    return recorded if recorded.tzinfo else recorded.replace(tzinfo=UTC)


class AsOfService:
    def __init__(
        self, repo: RepositoryProtocol, versions: VersionSourceProtocol
    ) -> None:
        self._repo = repo
        self._versions = versions

    def snapshot(self, ts: str) -> tuple[InMemoryRepository, AsOfMeta]:
        """ts 시점의 twin 상태를 재생한 스냅샷 저장소 + 정직성 메타."""
        cutoff = _parse_cutoff(ts)
        replayed = 0
        precapture = 0
        approximated = 0
        excluded = 0
        skipped = 0

        collections: dict[str, list[OntologyObject]] = {}
        for collection, (_, model) in COLLECTIONS.items():
            current = {obj.id: obj for obj in self._repo.list(collection)}
            by_object: dict[str, list[ObjectVersion]] = {}
            for entry in self._versions.collection_versions(collection):
                by_object.setdefault(entry.object_id, []).append(entry)

            resolved: dict[str, OntologyObject] = {}
            for object_id, obj in current.items():
                if object_id not in by_object:
                    resolved[object_id] = obj  # 캡처 이전부터 존재 가정
                    precapture += 1

            for object_id, entries in by_object.items():
                applicable = [
                    e
                    for e in entries
                    if (instant := _recorded_instant(e)) is not None
                    and instant <= cutoff
                ]
                if applicable:
                    replayed += len(applicable)
                    last = applicable[-1]  # entries는 version 오름차순
                    if last.payload is None:  # retracted — 그 시점에 철회됨
                        excluded += 1
                        continue
                    validated = self._validate(model, last.payload)
                    if validated is None:
                        skipped += 1
                    else:
                        resolved[object_id] = validated
                    continue
                # 모든 버전이 ts 이후
                if entries[0].change_kind == CHANGE_CREATED:
                    excluded += 1  # 그 시점 twin은 이 객체를 몰랐다
                    continue
                earliest_payload = next(
                    (e.payload for e in entries if e.payload is not None), None
                )
                if earliest_payload is not None:
                    validated = self._validate(model, earliest_payload)
                    if validated is None:
                        skipped += 1
                    else:
                        resolved[object_id] = validated
                        approximated += 1
                elif object_id in current:
                    resolved[object_id] = current[object_id]
                    approximated += 1
                else:
                    excluded += 1

            # 현재 상태의 순서를 보존하고, 재생으로 부활한 객체는 id 순으로 뒤에.
            ordered = [resolved[i] for i in current if i in resolved]
            ordered += [
                resolved[i] for i in sorted(resolved) if i not in current
            ]
            collections[collection] = ordered

        meta = AsOfMeta(
            as_of=cutoff.isoformat(),
            replayed_versions=replayed,
            precapture_assumed_objects=precapture,
            approximated_objects=approximated,
            excluded_objects=excluded,
            skipped_invalid=skipped,
            note_ko=(
                "transaction time(recorded_at) 축 재생 — 그 시점에 twin이 알던 상태. "
                f"버전 이력이 없는 {precapture}건은 '캡처 이전부터 존재' 가정으로 "
                "현재 상태를 포함했고, 당시 payload 미상 "
                f"{approximated}건은 가장 이른 기록으로 근사했다."
            ),
        )
        return InMemoryRepository(collections), meta

    @staticmethod
    def _validate(
        model: type[OntologyObject], payload: dict
    ) -> OntologyObject | None:
        try:
            return model.model_validate(payload)
        except ValidationError:
            return None
