import json
from dataclasses import asdict

from app.agents.evaluator import EvaluatorAgent
from app.agents.executor import ExecutorAgent
from app.agents.memory import MemoryAgent
from app.agents.planner import PlannerAgent
from app.core.types import AgentPlan, Evaluation, StepResult
from app.models.ollama import OllamaClient


class Orchestrator:
    def __init__(self, llm: OllamaClient) -> None:
        self.memory = MemoryAgent(llm)
        self.planner = PlannerAgent(llm)
        self.executor = ExecutorAgent(llm)
        self.evaluator = EvaluatorAgent(llm)

    async def run(self, goal: str) -> dict[str, object]:
        trace: list[dict[str, str]] = []

        memory_context = await self.memory.retrieve(goal)
        trace.append({"agent": "memory", "input": goal, "output": memory_context})

        plan = await self.planner.create_plan(goal, memory_context)
        trace.append({"agent": "planner", "input": goal, "output": self._json(plan)})

        results = await self.executor.execute_plan(goal, plan, memory_context)
        trace.append({"agent": "executor", "input": self._json(plan), "output": self._json(results)})

        evaluation = await self.evaluator.evaluate_results(goal, plan, results)
        trace.append({"agent": "evaluator", "input": self._json(results), "output": self._json(evaluation)})

        status = "completed" if evaluation.status == "PASS" else "completed_with_findings"
        task_id = await self.memory.store_task(goal, plan, results, evaluation, status)
        final_answer = self._final_answer(results, evaluation)

        return {
            "task_id": task_id,
            "goal": goal,
            "status": status,
            "final_answer": final_answer,
            "plan": asdict(plan),
            "evaluation": asdict(evaluation),
            "trace": trace,
        }

    def _json(self, value: AgentPlan | Evaluation | list[StepResult]) -> str:
        return json.dumps(value, default=asdict, indent=2)

    def _final_answer(self, results: list[StepResult], evaluation: Evaluation) -> str:
        body = "\n\n".join(f"{item.objective}\n{item.output}" for item in results)
        if evaluation.issues:
            body += "\n\nEvaluator findings:\n" + "\n".join(f"- {issue}" for issue in evaluation.issues)
        return body
