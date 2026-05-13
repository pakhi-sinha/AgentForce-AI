import json

from app.agents.base import Agent
from app.core.config import settings
from app.core.types import AgentPlan, PlanStep
from app.models.ollama import OllamaUnavailable


class PlannerAgent(Agent):
    name = "planner"

    async def run(self, prompt: str) -> str:
        return await self.llm.chat(settings.default_model, [{"role": "user", "content": prompt}])

    async def plan(self, goal: str, memory_context: str) -> str:
        prompt = (
            "You are the Planner Agent in an offline local multi-agent system. "
            "Break the user goal into ordered subtasks with success criteria. "
            "Use only local tools and local models. Return compact JSON with keys: "
            "assumptions and steps. Each step must have objective, success_criteria, and tool_hint.\n\n"
            f"Goal:\n{goal}\n\nRelevant memory:\n{memory_context}"
        )
        return await self.run(prompt)

    async def create_plan(self, goal: str, memory_context: str) -> AgentPlan:
        try:
            raw = await self.plan(goal, memory_context)
        except OllamaUnavailable:
            raw = ""

        parsed = self._parse_plan(goal, raw)
        if parsed.steps:
            return parsed

        return AgentPlan(
            goal=goal,
            assumptions=["Ollama was unavailable or returned unstructured output; using deterministic local fallback."],
            steps=[
                PlanStep(
                    id="step-1",
                    objective=f"Clarify the deliverable for: {goal}",
                    success_criteria="The response states the concrete outcome and constraints.",
                ),
                PlanStep(
                    id="step-2",
                    objective="Produce the best offline answer using local memory and reasoning.",
                    success_criteria="The answer is actionable, traceable, and does not depend on cloud APIs.",
                ),
                PlanStep(
                    id="step-3",
                    objective="Check the result against the original goal.",
                    success_criteria="Gaps, risks, and next actions are identified.",
                ),
            ],
        )

    def _parse_plan(self, goal: str, raw: str) -> AgentPlan:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return AgentPlan(goal=goal, steps=[])

        steps: list[PlanStep] = []
        for index, item in enumerate(data.get("steps", []), start=1):
            if not isinstance(item, dict):
                continue
            objective = str(item.get("objective", "")).strip()
            success_criteria = str(item.get("success_criteria", "")).strip()
            if objective and success_criteria:
                steps.append(
                    PlanStep(
                        id=str(item.get("id") or f"step-{index}"),
                        objective=objective,
                        success_criteria=success_criteria,
                        tool_hint=str(item.get("tool_hint") or "local_reasoning"),
                    )
                )
        assumptions = [str(value) for value in data.get("assumptions", []) if str(value).strip()]
        return AgentPlan(goal=goal, steps=steps, assumptions=assumptions)
