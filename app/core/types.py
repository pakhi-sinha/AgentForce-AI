from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class PlanStep:
    id: str
    objective: str
    success_criteria: str
    tool_hint: str = "local_reasoning"


@dataclass(slots=True)
class AgentPlan:
    goal: str
    steps: list[PlanStep]
    assumptions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StepResult:
    step_id: str
    objective: str
    output: str
    tool_used: str = "local_reasoning"
    ok: bool = True


@dataclass(slots=True)
class Evaluation:
    status: str
    issues: list[str] = field(default_factory=list)
    suggested_fixes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TaskRecord:
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
