"""결정 데이터-시점 워터마크 — "twin이 이 결정을 알게 된 시각" (설계 22 §2).

transaction time 축의 파생 뷰다 (저장하지 않음): 결정 객체의 첫 버전
recorded_at을 워터마크로 잡아 as-of 재생("그 시점에 twin이 알던 상태")의
진입점으로 쓴다. `decided_at` 같은 domain time 필드는 신설하지 않는다 —
재생 축(recorded_at)과 섞이면 거짓 리플레이가 된다 (설계 15 §3).

워터마크가 없으면(캡처 이전 synthetic 시드) 리플레이 진입점을 만들지 않고
그 사실을 note_ko로 명시한다 — 거짓 정밀도 방지 (AsOfMeta와 같은 태도).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.ingest.history import CHANGE_CREATED, ObjectVersion, VersionSourceProtocol
from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.decision import Decision

WATERMARK_VERSION_LOG = "version_log"
WATERMARK_INGESTED_AT = "ingested_at"
WATERMARK_PRECAPTURE = "precapture"


class DecisionWatermark(BaseModel):
    """결정 하나의 데이터-시점 — 리플레이 진입점 + 정직성 문구."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    project_id: str
    recorded_at: str | None  # ISO — None이면 리플레이 불가 (캡처 이전)
    batch_id: str | None  # 계보 (버전 로그 유래일 때)
    source: str  # version_log | ingested_at | precapture
    note_ko: str


class DecisionWatermarkService:
    def __init__(
        self, repo: RepositoryProtocol, versions: VersionSourceProtocol
    ) -> None:
        self._repo = repo
        self._versions = versions

    def watermarks(self, project_id: str | None = None) -> list[DecisionWatermark]:
        first_versions: dict[str, ObjectVersion] = {}
        for entry in self._versions.collection_versions("decisions"):
            known = first_versions.get(entry.object_id)
            if known is None or entry.version < known.version:
                first_versions[entry.object_id] = entry

        results = [
            self._watermark(obj, first_versions.get(obj.id))
            for obj in self._repo.list("decisions")
            if isinstance(obj, Decision)
            and (project_id is None or obj.project_id == project_id)
        ]
        return sorted(results, key=lambda w: w.decision_id)

    @staticmethod
    def _watermark(
        decision: Decision, first: ObjectVersion | None
    ) -> DecisionWatermark:
        ingested = decision.source.ingested_at
        if first is not None and first.change_kind == CHANGE_CREATED:
            return DecisionWatermark(
                decision_id=decision.id,
                project_id=decision.project_id,
                recorded_at=first.recorded_at,
                batch_id=first.batch_id,
                source=WATERMARK_VERSION_LOG,
                note_ko=(
                    "버전 로그 첫 기록 시각 — 이 시점의 as-of 재생이 "
                    "결정 당시 twin이 알던 상태다."
                ),
            )
        if first is not None:
            # 첫 버전이 updated — 캡처 시작 전부터 존재. 반입 시각이 있으면
            # 그쪽이 "twin이 알게 된 시각"에 더 가깝다.
            if ingested is not None:
                return DecisionWatermark(
                    decision_id=decision.id,
                    project_id=decision.project_id,
                    recorded_at=ingested.isoformat(),
                    batch_id=None,
                    source=WATERMARK_INGESTED_AT,
                    note_ko="캡처 시작 전부터 존재 — 반입 시각으로 근사했다.",
                )
            return DecisionWatermark(
                decision_id=decision.id,
                project_id=decision.project_id,
                recorded_at=first.recorded_at,
                batch_id=first.batch_id,
                source=WATERMARK_VERSION_LOG,
                note_ko=(
                    "캡처 시작 전부터 존재 — 첫 기록 시각으로 근사했다 "
                    "(실제 인지 시각은 더 이르다)."
                ),
            )
        if ingested is not None:
            return DecisionWatermark(
                decision_id=decision.id,
                project_id=decision.project_id,
                recorded_at=ingested.isoformat(),
                batch_id=None,
                source=WATERMARK_INGESTED_AT,
                note_ko="버전 로그 없음 — 반입 시각 기준.",
            )
        return DecisionWatermark(
            decision_id=decision.id,
            project_id=decision.project_id,
            recorded_at=None,
            batch_id=None,
            source=WATERMARK_PRECAPTURE,
            note_ko="캡처 이전 결정 — 버전 로그가 없어 당시 상태를 재생할 수 없다.",
        )
