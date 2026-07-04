"""전 컬렉션 ID 인덱스 — 임의 ID를 (컬렉션, 객체)로 해석한다."""

from __future__ import annotations

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology import COLLECTIONS, OntologyObject
from backend.ontology.scenario import Propagation, ScenarioRequest


class ObjectIndex:
    """ID → (컬렉션, 객체) 전역 인덱스.

    ScenarioRequest 내장 전파 레코드도 propagation_id로 해석된다.
    """

    def __init__(self, repo: RepositoryProtocol) -> None:
        self._index: dict[str, tuple[str, OntologyObject]] = {}
        self._propagations: dict[str, Propagation] = {}
        for collection in COLLECTIONS:
            for obj in repo.list(collection):
                self._index[obj.id] = (collection, obj)
        for request in repo.list("scenario_requests"):
            assert isinstance(request, ScenarioRequest)
            for propagation in request.propagation:
                self._propagations[propagation.propagation_id] = propagation

    def resolve(self, object_id: str) -> tuple[str, OntologyObject] | None:
        return self._index.get(object_id)

    def resolve_propagation(self, propagation_id: str) -> Propagation | None:
        return self._propagations.get(propagation_id)

    def collection_of(self, object_id: str) -> str | None:
        entry = self._index.get(object_id)
        return entry[0] if entry else None

    def exists(self, object_id: str) -> bool:
        return object_id in self._index or object_id in self._propagations
