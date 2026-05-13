from pathlib import Path
import json
from dataclasses import asdict

from app.agents.base import Agent
from app.core.config import settings
from app.core.types import AgentPlan, Evaluation, StepResult, TaskRecord
from app.db.sqlite import connect, migrate
from app.models.ollama import OllamaUnavailable


class MemoryAgent(Agent):
    name = "memory"

    def __init__(self, llm) -> None:
        super().__init__(llm)
        self.memory_path = Path(settings.sqlite_path).with_suffix(".memory.log")
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        migrate()

    async def run(self, prompt: str) -> str:
        return await self.llm.chat(settings.fast_model, [{"role": "user", "content": prompt}])

    async def retrieve(self, query: str) -> str:
        if not self.memory_path.exists():
            return "No prior memory found."

        content = self.memory_path.read_text(encoding="utf-8")
        if not content.strip():
            return "No prior memory found."

        try:
            prompt = (
                "You are the Memory Agent. Extract only memories relevant to the query. "
                "If nothing is relevant, say so briefly.\n\n"
                f"Query:\n{query}\n\nMemory log:\n{content[-8000:]}"
            )
            return await self.run(prompt)
        except OllamaUnavailable:
            return content[-2000:]

    async def store(self, goal: str, plan: str, execution: str, evaluation: str) -> None:
        record = (
            "\n---\n"
            f"GOAL:\n{goal}\n"
            f"PLAN:\n{plan}\n"
            f"EXECUTION:\n{execution}\n"
            f"EVALUATION:\n{evaluation}\n"
        )
        with self.memory_path.open("a", encoding="utf-8") as handle:
            handle.write(record)

    async def store_task(
        self,
        goal: str,
        plan: AgentPlan,
        results: list[StepResult],
        evaluation: Evaluation,
        status: str,
    ) -> str:
        task = TaskRecord()
        plan_json = json.dumps(plan, default=asdict, indent=2)
        result_json = json.dumps(results, default=asdict, indent=2)
        eval_json = json.dumps(evaluation, default=asdict, indent=2)
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, goal, plan, execution, evaluation, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task.id, goal, plan_json, result_json, eval_json, status, task.created_at),
            )
            conn.execute(
                "INSERT INTO memories (kind, content) VALUES (?, ?)",
                ("task_summary", f"Goal: {goal}\nStatus: {status}\nEvaluation: {evaluation.status}"),
            )
        await self.store(goal, plan_json, result_json, eval_json)
        return task.id
