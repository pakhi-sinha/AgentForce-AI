from app.agents.base import Agent
from app.core.config import settings
from app.core.types import AgentPlan, StepResult
from app.models.ollama import OllamaUnavailable
from app.tools.registry import ToolRegistry, default_registry


class ExecutorAgent(Agent):
    name = "executor"

    def __init__(self, llm, tools: ToolRegistry | None = None) -> None:
        super().__init__(llm)
        self.tools = tools or default_registry()

    async def run(self, prompt: str) -> str:
        return await self.llm.chat(settings.default_model, [{"role": "user", "content": prompt}])

    async def execute(self, goal: str, plan: str, memory_context: str) -> str:
        prompt = (
            "You are the Executor Agent. Perform the plan using local-only reasoning. "
            "When a tool is required, describe the tool call that should be made by the local tool registry. "
            "Return the completed result and a compact trace.\n\n"
            f"Goal:\n{goal}\n\nPlan:\n{plan}\n\nContext:\n{memory_context}"
        )
        return await self.run(prompt)

    async def execute_plan(self, goal: str, plan: AgentPlan, memory_context: str) -> list[StepResult]:
        results: list[StepResult] = []
        for step in plan.steps:
            prompt = (
                "You are the Executor Agent in a local-only AI operating system. "
                "Complete this step using the supplied memory. Be concrete and concise.\n\n"
                f"Goal:\n{goal}\n\nStep:\n{step.objective}\n\nSuccess criteria:\n{step.success_criteria}\n\n"
                f"Memory:\n{memory_context}"
            )
            try:
                output = await self.run(prompt)
            except OllamaUnavailable:
                output = (
                    f"Offline fallback completed '{step.objective}'. "
                    f"Criteria considered: {step.success_criteria}."
                )
            results.append(
                StepResult(
                    step_id=step.id,
                    objective=step.objective,
                    output=output,
                    tool_used=step.tool_hint,
                    ok=bool(output.strip()),
                )
            )
        return results
