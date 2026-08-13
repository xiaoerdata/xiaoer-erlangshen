"""Serializable harness plan used by the standalone CLI advice workflow."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field


@dataclass
class ClientHarnessStep:
    step_id: str
    title: str
    agent: str
    depends_on: tuple[str, ...] = ()
    status: str = "pending"
    attempts: int = 0
    evidence_required: bool = False
    error: str = ""


@dataclass
class ClientHarnessPlan:
    run_id: str
    query: str
    route: str
    steps: list[ClientHarnessStep] = field(default_factory=list)
    status: str = "pending"


class ClientHarnessPlanPolicy:
    STAGES = (
        ("intent", "理解任务、解析标的并规划工具", "planner", ()),
        ("evidence", "采集并核验 MCP/web 证据", "researcher", ("intent",)),
        ("cognition", "获取服务端受保护认知映射", "router", ("intent",)),
        ("synthesis", "综合证据与认知形成回答", "synthesizer", ("evidence", "cognition")),
        ("completion_audit", "校验回答契约、风险和证据缺口", "reviewer", ("synthesis",)),
    )

    def build(self, query: str, intent_plan: dict) -> ClientHarnessPlan:
        return ClientHarnessPlan(
            run_id=f"run_{uuid.uuid4().hex}",
            query=query,
            route=str(intent_plan.get("intent") or "general_investment"),
            steps=[ClientHarnessStep(
                step_id=step_id,
                title=title,
                agent=agent,
                depends_on=depends_on,
                evidence_required=step_id == "evidence" and bool(intent_plan.get("needs_mcp")),
            ) for step_id, title, agent, depends_on in self.STAGES],
        )

    def mark(self, plan: ClientHarnessPlan, step_id: str, status: str, *, error: str = "") -> None:
        step = next(item for item in plan.steps if item.step_id == step_id)
        step.status = status
        step.error = error
        if status == "running":
            step.attempts += 1
        statuses = {item.status for item in plan.steps}
        if statuses == {"completed"}:
            plan.status = "completed"
        elif "failed" in statuses:
            plan.status = "partial" if "completed" in statuses else "failed"
        elif statuses.intersection({"running", "completed"}):
            plan.status = "running"

    def to_dict(self, plan: ClientHarnessPlan) -> dict:
        value = asdict(plan)
        for index, step in enumerate(plan.steps):
            value["steps"][index]["depends_on"] = list(step.depends_on)
        return value

    def from_dict(self, value: dict) -> ClientHarnessPlan:
        return ClientHarnessPlan(
            run_id=str(value.get("run_id") or ""),
            query=str(value.get("query") or ""),
            route=str(value.get("route") or "general_investment"),
            status=str(value.get("status") or "pending"),
            steps=[ClientHarnessStep(
                step_id=str(row.get("step_id") or ""),
                title=str(row.get("title") or ""),
                agent=str(row.get("agent") or ""),
                depends_on=tuple(row.get("depends_on") or ()),
                status=str(row.get("status") or "pending"),
                attempts=int(row.get("attempts") or 0),
                evidence_required=bool(row.get("evidence_required")),
                error=str(row.get("error") or ""),
            ) for row in value.get("steps") or []],
        )
