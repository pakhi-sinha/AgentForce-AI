from app.agents.base import Agent
from app.core.config import settings
from app.core.types import AgentPlan, Evaluation, StepResult
from app.models.ollama import OllamaUnavailable


class EvaluatorAgent(Agent):
    name = "evaluator"

    async def run(self, prompt: str) -> str:
        return await self.llm.chat(settings.fast_model, [{"role": "user", "content": prompt}])

    async def evaluate(self, goal: str, plan: str, execution: str) -> str:
        prompt = (
            "You are the Evaluator Agent. Validate whether the execution satisfies the goal. "
            "Return PASS or NEEDS_REVISION, then list issues and suggested fixes.\n\n"
            f"Goal:\n{goal}\n\nPlan:\n{plan}\n\nExecution:\n{execution}"
        )
        return await self.run(prompt)

    async def evaluate_results(self, goal: str, plan: AgentPlan, results: list[StepResult]) -> Evaluation:
        execution = "\n".join(f"{item.step_id}: {item.output}" for item in results)
        try:
            raw = await self.evaluate(goal, "\n".join(step.objective for step in plan.steps), execution)
        except OllamaUnavailable:
            failed = [item.objective for item in results if not item.ok]
            return Evaluation(
                status="NEEDS_REVISION" if failed else "PASS",
                issues=failed,
                suggested_fixes=["Start Ollama for model-backed critique."] if failed else [],
            )

        status = "PASS" if "PASS" in raw.upper() and "NEEDS_REVISION" not in raw.upper() else "NEEDS_REVISION"
        issues = [line.strip("- ").strip() for line in raw.splitlines() if line.strip().startswith(("-", "*"))]
        return Evaluation(status=status, issues=issues[:6], suggested_fixes=[])
