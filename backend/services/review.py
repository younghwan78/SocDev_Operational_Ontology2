"""리뷰 서비스 — 주간 스냅샷 파생 뷰 (저장하지 않음)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent
from backend.ontology.role import RoleActivity
from backend.ontology.scenario import ScenarioRequest


class WeeklySnapshot(BaseModel):
    """한 주의 이벤트/활동/요청 스냅샷."""

    model_config = ConfigDict(extra="forbid")

    week: int
    events: list[DevelopmentEvent]
    activities: list[RoleActivity]
    requests: list[ScenarioRequest]


class WeeklyIndex(BaseModel):
    """주차 목록과 주차별 건수 요약."""

    model_config = ConfigDict(extra="forbid")

    weeks: list[int]
    event_counts: dict[int, int]
    activity_counts: dict[int, int]
    request_counts: dict[int, int]


class ReviewService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo

    def _events(self) -> list[DevelopmentEvent]:
        return [e for e in self._repo.list("development_events") if isinstance(e, DevelopmentEvent)]

    def _activities(self) -> list[RoleActivity]:
        return [a for a in self._repo.list("role_activities") if isinstance(a, RoleActivity)]

    def _requests(self) -> list[ScenarioRequest]:
        return [r for r in self._repo.list("scenario_requests") if isinstance(r, ScenarioRequest)]

    def index(self) -> WeeklyIndex:
        event_counts: dict[int, int] = {}
        activity_counts: dict[int, int] = {}
        request_counts: dict[int, int] = {}
        for event in self._events():
            if event.week is not None:
                event_counts[event.week] = event_counts.get(event.week, 0) + 1
        for activity in self._activities():
            activity_counts[activity.week] = activity_counts.get(activity.week, 0) + 1
        for request in self._requests():
            request_counts[request.requested_week] = request_counts.get(request.requested_week, 0) + 1
        weeks = sorted(set(event_counts) | set(activity_counts) | set(request_counts))
        return WeeklyIndex(
            weeks=weeks,
            event_counts=event_counts,
            activity_counts=activity_counts,
            request_counts=request_counts,
        )

    def snapshot(self, week: int) -> WeeklySnapshot:
        return WeeklySnapshot(
            week=week,
            events=[e for e in self._events() if e.week == week],
            activities=[a for a in self._activities() if a.week == week],
            requests=[r for r in self._requests() if r.requested_week == week],
        )
