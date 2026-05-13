from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone


ToolHandler = Callable[[dict[str, object]], Awaitable[dict[str, object]]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list(self) -> list[dict[str, str]]:
        return [{"name": tool.name, "description": tool.description} for tool in self._tools.values()]

    async def call(self, name: str, payload: dict[str, object]) -> dict[str, object]:
        if name not in self._tools:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        return await self._tools[name].handler(payload)


async def _clock(_: dict[str, object]) -> dict[str, object]:
    return {"ok": True, "utc": datetime.now(timezone.utc).isoformat()}


async def _summarize(payload: dict[str, object]) -> dict[str, object]:
    text = str(payload.get("text", ""))
    return {"ok": True, "summary": text[:800], "characters": len(text)}


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(Tool("clock", "Return the current local UTC timestamp.", _clock))
    registry.register(Tool("summarize_text", "Create a deterministic local extractive summary.", _summarize))
    return registry
