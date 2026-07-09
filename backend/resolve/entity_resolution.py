"""엔티티 해석 — IP 명칭 불일치를 canonical ip_id로 해석하는 1급 서비스.

원점 비전의 "식별자 파편화"(§2) 대응. IPBlock의 name/domain/aliases에서 토큰 역인덱스를
구축해 임의 명칭을 canonical ip_id로 해석하고, 해석되지 않는 토큰을 큐레이션 큐로 모은다.

교정(별칭 추가)은 IPBlock.aliases 변경(변경 규율)으로만 반영한다 — 쓰기 API 없음.
본 인덱스는 risk.py의 event↔IP 귀속에서도 공용으로 쓰인다(`resolve_all`) — 구
`ip_match_tokens` 휴리스틱(L8)을 대체하는 단일 정규화·해석 경로다.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.loaders.protocols import RepositoryProtocol
from backend.ontology.event import DevelopmentEvent
from backend.ontology.ip import IPBlock


def normalize_tokens(*values: str) -> set[str]:
    """대소문자·`_` 분해를 정규화한 토큰 집합 (risk.py ip_match_tokens와 동일 규칙)."""
    tokens: set[str] = set()
    for value in values:
        lowered = value.strip().lower()
        if not lowered:
            continue
        tokens.add(lowered)
        tokens.update(part for part in lowered.split("_") if part)
    return tokens


class AliasEntry(BaseModel):
    """canonical IP 하나의 별칭표."""

    model_config = ConfigDict(extra="forbid")

    ip_id: str
    ip_name: str
    domain: str
    aliases: list[str]


class UnmatchedToken(BaseModel):
    """어떤 IP로도 해석되지 않은 토큰 — 별칭 큐레이션 후보."""

    model_config = ConfigDict(extra="forbid")

    token: str
    occurrences: int
    sample_refs: list[str]


class EntityResolutionReport(BaseModel):
    """엔티티 해석 리포트 — 별칭표 + 미해석 큐."""

    model_config = ConfigDict(extra="forbid")

    aliases: list[AliasEntry]
    unmatched: list[UnmatchedToken]


class IPAliasIndex:
    """토큰 → canonical ip_id 역인덱스.

    한 토큰이 여러 IP에 걸릴 수 있다(예: 'memory'→MIF·SMMU, 'ai'→GPU·NPU). 큐레이션용
    `resolve`는 단일 canonical(첫 등록 우선)을, risk 귀속용 `resolve_all`은 전체 집합을 준다.
    """

    def __init__(self, repo: RepositoryProtocol) -> None:
        self._blocks: dict[str, IPBlock] = {
            b.id: b for b in repo.list("ip_blocks") if isinstance(b, IPBlock)
        }
        self._ids_by_token: dict[str, list[str]] = {}
        for ip in self._blocks.values():
            self._add(ip.id.lower(), ip.id)
            for token in normalize_tokens(ip.name, ip.domain, *ip.aliases):
                self._add(token, ip.id)

    def _add(self, token: str, ip_id: str) -> None:
        ids = self._ids_by_token.setdefault(token, [])
        if ip_id not in ids:
            ids.append(ip_id)

    def resolve(self, token: str) -> str | None:
        """단일 canonical ip_id (첫 등록 우선). 별칭 큐레이션·미해석 판정용."""
        ids = self._ids_by_token.get(token.strip().lower())
        return ids[0] if ids else None

    def resolve_all(self, token: str) -> set[str]:
        """토큰에 걸리는 모든 ip_id. event↔IP 귀속(risk)에서 다중 관련 IP를 보존한다."""
        return set(self._ids_by_token.get(token.strip().lower(), ()))

    def alias_entries(self) -> list[AliasEntry]:
        return [
            AliasEntry(
                ip_id=ip.id,
                ip_name=ip.name,
                domain=ip.domain,
                aliases=sorted(ip.aliases),
            )
            for ip in sorted(self._blocks.values(), key=lambda b: (b.category, b.name))
        ]


class EntityResolutionService:
    def __init__(self, repo: RepositoryProtocol) -> None:
        self._repo = repo
        self._index = IPAliasIndex(repo)

    def report(self) -> EntityResolutionReport:
        # 이벤트 affected_domains 토큰을 해석 시도 — 미해석분이 큐레이션 큐.
        unmatched: dict[str, list[str]] = {}
        for event in self._repo.list("development_events"):
            if not isinstance(event, DevelopmentEvent):
                continue
            for domain in event.affected_domains:
                if self._index.resolve(domain) is not None:
                    continue
                unmatched.setdefault(domain, []).append(event.id)
        queue = [
            UnmatchedToken(
                token=token,
                occurrences=len(refs),
                sample_refs=sorted(set(refs))[:5],
            )
            for token, refs in unmatched.items()
        ]
        queue.sort(key=lambda u: (-u.occurrences, u.token))
        return EntityResolutionReport(
            aliases=self._index.alias_entries(),
            unmatched=queue,
        )
