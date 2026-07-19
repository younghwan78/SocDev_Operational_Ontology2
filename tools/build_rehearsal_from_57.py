"""57 world.yaml → 리허설 유니버스 payload 생성 (설계 25).

원천: E:\\57_Claude_SoC_DigitalTwin\\OperationalOntology\\data\\world.yaml
(read-only — 절대 수정하지 않는다). 산출: rehearsal/ 디렉토리.

역할 분담(설계 25 §1.2): JIRA=이슈·계획·진행(간결한 요약·상태·일정),
Confluence=세부 기술 서사·측정 리포트·결정 노트·공식 architecture 문서.

의도된 지저분함(§1.3): 링크 필드 대부분 비움, 미등재 상태("In Review"/"백로그"),
심각도 일부 누락, project_v는 W30~37 전이를 W38에 몰아서 기록(기록 규율 왜곡).

결정론: 같은 world.yaml → 같은 산출물. 실 사내 전환은 payload 대신 실 REST +
field map 값 교체 (경로 동일 — FakeJiraClient ↔ JiraHttpClient).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WORLD = Path(r"E:\57_Claude_SoC_DigitalTwin\OperationalOntology\data\world.yaml")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "rehearsal"
DEFAULT_BASE_DATE = date(2025, 8, 4)  # W1 월요일 — W48이 과거에 들어오도록

PROJECT_MAP = {"U": "project_u", "V": "project_v", "W": "project_w"}

# 57 activity stage → JIRA 상태. "In Review"는 의도적으로 field map 사전 밖
# (미등재 라벨 경고 UX 검증용). 종결은 이벤트별로 Resolved/Closed 순환.
STAGE_STATUS = {"plan": "Open", "act": "In Progress", "judge": "In Review"}

# 사내식 이슈 유형(한국어) — rehearsal field map value_maps가 58 코드로 정규화.
# "근거요청"은 사전에 없음(의도 — 미등재 유형 경고 1종).
TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("발열", "발열"),
    ("thermal", "발열"),
    ("power", "전력"),
    ("전력", "전력"),
    ("underrun", "언더런"),
    ("latency", "지연"),
    ("BW", "대역폭"),
    ("bw", "대역폭"),
    ("area", "아키검토"),
    ("arch", "아키검토"),
    ("spec", "아키검토"),
    ("IQ", "화질"),
    ("화질", "화질"),
    ("benchmark", "성능"),
    ("경쟁", "성능"),
]

VALUE_MAP_TYPES = {
    "발열": "thermal_throttling",
    "전력": "power_budget_overrun",
    "언더런": "underrun",
    "지연": "latency_regression",
    "대역폭": "bandwidth_overrun",
    "아키검토": "architecture_tradeoff",
    "화질": "image_quality_regression",
    "성능": "performance_competitiveness",
    "결함": "defect",
}

AXIS_TYPES = {
    "power": "전력",
    "business": "성능",
    "area": "아키검토",
    "resource": "대역폭",
    "schedule": "지연",
    "quality": "화질",
}

PRIORITY_MAP = {"P0": "Highest", "P1": "High", "P2": "Medium", "P3": "Low"}

DOMAIN_SPACES: list[tuple[str, str]] = [
    ("camera", "CAM"),
    ("isp", "CAM"),
    ("display", "DISP"),
    ("video", "VID"),
    ("codec", "VID"),
    ("audio", "AUD"),
    ("arch", "ARCH"),
]

# 링크를 일부러 채우는 소수 이벤트 — 연결률이 0이 아니라 "낮게 시작"하도록.
PRELINKED_SCENARIOS = {
    "E-106": "uhd60_recording_eis_on",  # KPI recording(UHD60)
    "E-103": "video_mode_panel_underrun_prevention",  # DPU underrun
}

FIELD_MAP_YAML = {
    "issue_mapping": "issues",
    "columns": {
        "이슈 ID": "key",
        "제목": "fields.summary",
        "유형": "fields.issuetype.name",
        "상태": "fields.status.name",
        "심각도": "fields.priority.name",
        "증상": "fields.description",
        "프로젝트 ID": "fields.labels.0",
        "영향 시나리오": "fields.customfield_scenarios",
        "영향 IP": "fields.customfield_ips",
        "교훈": "fields.customfield_lesson",
    },
    "week_columns": {"최근 활동 주차": "fields.updated", "목표 주차": "fields.duedate"},
    "value_maps": {
        "상태": {
            "Open": "open",
            "In Progress": "open",
            "Reopened": "open",
            "Resolved": "resolved",
            "Closed": "closed",
            "Done": "done",
        },
        "심각도": {
            "Highest": "critical",
            "High": "high",
            "Medium": "medium",
            "Low": "low",
            "Lowest": "low",
        },
        "유형": VALUE_MAP_TYPES,
    },
    "constants": {"확신도": "medium"},
}


def week_date(base: date, week: int) -> date:
    return base + timedelta(weeks=week - 1)


def classify_type(text: str) -> str:
    for keyword, type_ko in TYPE_KEYWORDS:
        if keyword.lower() in text.lower():
            return type_ko
    return "결함"


def pick_space(domains: list[str], trigger: str) -> str:
    haystack = " ".join(domains) + " " + trigger
    for keyword, space in DOMAIN_SPACES:
        if keyword in haystack.lower():
            return space
    return "SYS"


def event_number(event_id: str) -> str:
    return event_id.split("-")[-1]


class IssueTimeline:
    """이슈 하나의 주차별 상태 — wave 생성의 단위."""

    def __init__(self, key: str, fields: dict[str, Any], created_week: int) -> None:
        self.key = key
        self.fields = fields
        self.created_week = created_week
        self.status_by_week: dict[int, str] = {created_week: "Open"}

    def set_status(self, week: int, status: str) -> None:
        self.status_by_week[week] = status

    def waves(self) -> list[tuple[int, str]]:
        return sorted(self.status_by_week.items())


def build_issue_timelines(world: dict[str, Any]) -> list[IssueTimeline]:
    activity: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in world.get("activity_log", []):
        activity.setdefault((entry["event"], entry["project"]), []).append(entry)

    timelines: list[IssueTimeline] = []
    for event in world["events"]:
        num = event_number(event["id"])
        type_ko = classify_type(event["trigger"])
        origin = event.get("origin", "U")
        for proj57, span in sorted(event.get("spans", {}).items()):
            project = PROJECT_MAP[proj57]
            key = f"SOC{proj57}-{num}"
            propagated = proj57 != origin
            summary = event["trigger"] + (f" ({origin} 전파)" if propagated else "")
            problem = str(event.get("situation", {}).get("problem", "")).strip()
            description = (
                str(span.get("note", "")).strip()
                if propagated
                else (problem.split(". ")[0] or event["trigger"])
            )
            fields: dict[str, Any] = {
                "summary": summary,
                "issuetype": {"name": type_ko},
                "labels": [project],
                "description": description,
                "duedate_week": span.get("end_w"),
            }
            # 심각도 — 이벤트 priority에서, 일부(끝자리 5·7)는 의도적 누락.
            if not num.endswith(("5", "7")):
                fields["priority"] = {
                    "name": PRIORITY_MAP.get(str(event.get("priority", "P2")), "Medium")
                }
            scenario = PRELINKED_SCENARIOS.get(event["id"])
            if scenario and not propagated:
                fields["customfield_scenarios"] = scenario

            start_week = int(span.get("start_w", 1))
            timeline = IssueTimeline(key, fields, start_week)
            entries = sorted(
                activity.get((event["id"], proj57), []), key=lambda e: e["week"]
            )
            closed_status = "Closed" if int(num) % 3 == 0 else "Resolved"
            for entry in entries:
                stage = entry.get("stage", "")
                week = int(entry["week"])
                if stage == "result":
                    timeline.set_status(week, closed_status)
                    if int(num) % 2 == 0:
                        fields["customfield_lesson"] = (
                            f"{event['trigger']} — 대응 경과를 차기 과제 검토에 반영"
                        )
                elif stage in STAGE_STATUS:
                    timeline.set_status(week, STAGE_STATUS[stage])
            if not entries and propagated:
                # 전파 스팬은 활동 로그가 없다 — 시작 Open, 중간 In Progress.
                timeline.set_status(int(span.get("end_w", start_week)), "In Progress")
            timelines.append(timeline)

        # missing_evidence → 근거 확보 이슈 (대부분 미해결 — 지연 신호 재료).
        for index, need in enumerate(event.get("missing_evidence", []), start=1):
            reduces = need.get("reduces", {})
            proj57 = str(reduces.get("project", origin))
            project = PROJECT_MAP.get(proj57, PROJECT_MAP[origin])
            key = f"SOC{proj57}-9{num[-2:]}{index}"
            type_ko = AXIS_TYPES.get(str(reduces.get("axis", "")), "근거요청")
            fields = {
                "summary": f"[근거 요청] {need['item']}",
                "issuetype": {"name": type_ko},
                "labels": [project],
                "description": f"{need.get('system', '?')} 확보 필요 — {need['item']}",
                "duedate_week": need.get("due_w"),
                "priority": {"name": "Medium"},
            }
            requested = int(need.get("requested_w", 1) or 1)
            timeline = IssueTimeline(key, fields, requested)
            if str(need.get("status", "open")) != "open":
                timeline.set_status(requested + 2, "Resolved")
            timelines.append(timeline)
    return timelines


def squash_late_reporting(timelines: list[IssueTimeline]) -> None:
    """기록 규율 왜곡 심기 — project_v의 W30~37 전이를 W38에 몰아 기록."""
    for timeline in timelines:
        if timeline.fields["labels"][0] != "project_v":
            continue
        moved = {
            week: status
            for week, status in timeline.status_by_week.items()
            if 30 <= week <= 37 and week != timeline.created_week
        }
        if not moved:
            continue
        for week in moved:
            del timeline.status_by_week[week]
        # 마지막 상태만 남는다 — 중간 전이가 통째로 사라진 기록.
        last_status = moved[max(moved)]
        timeline.status_by_week[38] = last_status


def jira_waves(
    timelines: list[IssueTimeline], base: date
) -> dict[int, list[dict[str, Any]]]:
    """주차 → 그 주에 생성/변경된 이슈의 현재 스냅샷 (증분 동기화 시뮬레이션)."""
    waves: dict[int, list[dict[str, Any]]] = {}
    for timeline in timelines:
        status = "Open"
        for week, new_status in timeline.waves():
            status = new_status
            fields = {
                key: value
                for key, value in timeline.fields.items()
                if key != "duedate_week"
            }
            fields["status"] = {"name": status}
            fields["updated"] = week_date(base, week).isoformat()
            due_week = timeline.fields.get("duedate_week")
            if due_week:
                fields["duedate"] = week_date(base, int(due_week)).isoformat()
            waves.setdefault(week, []).append({"key": timeline.key, "fields": fields})
    return waves


def build_confluence_pages(world: dict[str, Any], base: date) -> list[dict[str, Any]]:
    """Confluence = 세부 기술·공식 문서 계층 (설계 25 §1.2)."""
    pages: list[dict[str, Any]] = []
    minutes: dict[int, list[str]] = {}
    for event in world["events"]:
        num = event_number(event["id"])
        origin = event.get("origin", "U")
        project = PROJECT_MAP[origin]
        main_key = f"SOC{origin}-{num}"
        situation = event.get("situation", {})
        space = pick_space(event.get("domains", []), event["trigger"])
        span = event.get("spans", {}).get(origin, {})
        plan_week = int(span.get("start_w", 1))
        result_week = int(span.get("end_w", plan_week))

        # 1) 기술 검토 노트 — JIRA에는 없는 배경/문제/목표 서사.
        role_views = []
        for role, position in sorted(event.get("role_positions", {}).items())[:3]:
            purpose = str(position.get("purpose", "")).strip()
            gap = str(position.get("data_gap", "")).strip()
            role_views.append(f"[{role}] {purpose}\n부족 데이터: {gap}")
        pages.append(
            {
                "id": f"57{num}01",
                "space": space,
                "title": f"{event['trigger']} — 기술 검토 노트",
                "project_id": project,
                "issue_keys": [main_key],
                "updated_week": plan_week,
                "body": (
                    f"배경: {situation.get('background', '')}\n"
                    f"문제: {situation.get('problem', '')}\n"
                    f"목표: {situation.get('goal', '')}\n\n" + "\n\n".join(role_views)
                ),
            }
        )
        # 2) 측정 리포트 — evidence 항목.
        for index, evidence in enumerate(event.get("evidence", []), start=1):
            pages.append(
                {
                    "id": f"57{num}1{index}",
                    "space": space,
                    "title": f"측정 리포트: {evidence.get('text', '')}",
                    "project_id": project,
                    "issue_keys": [main_key],
                    "updated_week": plan_week,
                    "body": (
                        f"{evidence.get('text', '')}\n출처 시스템: "
                        f"{evidence.get('source', '?')} — 측정 조건과 한계를 기록한다."
                    ),
                }
            )
        # 3) 결정 노트 — result 주차.
        decision = event.get("decision", {})
        if decision:
            pages.append(
                {
                    "id": f"57{num}21",
                    "space": space,
                    "title": f"결정 노트: {decision.get('summary', '')}",
                    "project_id": project,
                    "issue_keys": [main_key],
                    "updated_week": result_week,
                    "body": (
                        f"결정: {decision.get('summary', '')} (확신도 "
                        f"{decision.get('confidence', 'M')})\n근거와 미해결 리스크는 "
                        "회의 기록과 측정 리포트를 참조."
                    ),
                }
            )
        # 4) W 프로젝트 아키 이벤트 → 공식 architecture/design 문서.
        if origin == "W":
            pages.append(
                {
                    "id": f"57{num}31",
                    "space": "ARCH",
                    "title": f"[설계문서] {event['trigger']} architecture 검토서",
                    "project_id": "project_w",
                    "issue_keys": [main_key],
                    "updated_week": result_week,
                    "body": (
                        f"{situation.get('goal', '')}\n\n구조 대안·PPA 트레이드오프·"
                        "선행 검증 계획을 담은 공식 설계 문서. 승인 전 초안은 "
                        "기술 검토 노트를 참조한다."
                    ),
                }
            )
        # 주간 회의록 재료 — 역할 발언.
        for position in event.get("role_positions", {}).values():
            say = str(position.get("say_plan", "")).strip()
            if say:
                minutes.setdefault(plan_week, []).append(f"- {say}")

    for week in sorted(minutes)[:8]:
        pages.append(
            {
                "id": f"579{week:02d}0",
                "space": "SYS",
                "title": f"주간 개발 회의록 W{week}",
                "project_id": "",
                "issue_keys": [],
                "updated_week": week,
                "body": "이번 주 역할별 계획 발언:\n" + "\n".join(minutes[week][:8]),
            }
        )
    return pages


def build_decisions(world: dict[str, Any]) -> dict[int, list[dict[str, str]]]:
    """이벤트 결정 → 결정 CSV 행 (result 주차 반입 — 워터마크 리플레이 재료)."""
    by_week: dict[int, list[dict[str, str]]] = {}
    for event in world["events"]:
        decision = event.get("decision", {})
        if not decision:
            continue
        num = event_number(event["id"])
        origin = event.get("origin", "U")
        span = event.get("spans", {}).get(origin, {})
        week = int(span.get("end_w", span.get("start_w", 1)))
        evidence = event.get("evidence", [{}])
        first_evidence = evidence[0] if evidence else {}
        risks = [
            str(need.get("item", "")) for need in event.get("missing_evidence", [])[:2]
        ]
        by_week.setdefault(week, []).append(
            {
                "결정 ID": f"dec_rehearsal_{num}",
                "프로젝트 ID": PROJECT_MAP[origin],
                "회의 이벤트 ID": f"evt_rehearsal_{num}",
                "결정 유형": "review_decision",
                "결정": str(decision.get("summary", "")),
                "트레이드오프 요약": str(event.get("situation", {}).get("goal", ""))[:120],
                "진술": f"{first_evidence.get('text', '근거 검토')} 기반 결정",
                "근거": str(first_evidence.get("source", "회의 기록")),
                "근거 유형": "measurement",
                "확신도": str(decision.get("confidence", "M")),
                "미해결 리스크": ";".join(r for r in risks if r),
            }
        )
    return by_week


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8-sig", newline="")


def build(world_path: Path, out_dir: Path, base: date) -> dict[str, Any]:
    world = yaml.safe_load(world_path.read_text(encoding="utf-8"))
    timelines = build_issue_timelines(world)
    squash_late_reporting(timelines)
    waves = jira_waves(timelines, base)
    pages = build_confluence_pages(world, base)
    decisions = build_decisions(world)

    out_dir.mkdir(parents=True, exist_ok=True)
    plan: list[dict[str, Any]] = []
    page_waves: dict[int, list[dict[str, Any]]] = {}
    for page in pages:
        page_waves.setdefault(int(page["updated_week"]), []).append(page)

    for week in sorted(set(waves) | set(page_waves) | set(decisions)):
        entry: dict[str, Any] = {
            "week": week,
            "date": week_date(base, week).isoformat(),
        }
        if week in waves:
            name = f"jira_wave_W{week:02d}.json"
            (out_dir / name).write_text(
                json.dumps({"issues": waves[week]}, ensure_ascii=False, indent=1),
                encoding="utf-8",
                newline="\n",
            )
            entry["jira"] = name
        if week in page_waves:
            name = f"confluence_wave_W{week:02d}.json"
            (out_dir / name).write_text(
                json.dumps({"pages": page_waves[week]}, ensure_ascii=False, indent=1),
                encoding="utf-8",
                newline="\n",
            )
            entry["confluence"] = name
        if week in decisions:
            name = f"decisions_W{week:02d}.csv"
            write_csv(out_dir / name, decisions[week])
            entry["decisions"] = name
        plan.append(entry)

    (out_dir / "jira_field_map.rehearsal.yaml").write_text(
        yaml.safe_dump(FIELD_MAP_YAML, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )
    plan_doc = {
        "source": str(world_path),
        "base_date": base.isoformat(),
        "issue_count": len(timelines),
        "page_count": len(pages),
        "waves": plan,
    }
    (out_dir / "replay_plan.json").write_text(
        json.dumps(plan_doc, ensure_ascii=False, indent=1),
        encoding="utf-8",
        newline="\n",
    )
    return plan_doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--base-date", type=date.fromisoformat, default=DEFAULT_BASE_DATE)
    args = parser.parse_args()
    plan = build(args.world, args.out_dir, args.base_date)
    print(
        f"리허설 산출: 이슈 타임라인 {plan['issue_count']}건 · 페이지 {plan['page_count']}건 · "
        f"wave {len(plan['waves'])}개 → {args.out_dir}"
    )


if __name__ == "__main__":
    main()
