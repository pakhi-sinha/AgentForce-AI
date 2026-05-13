from abc import ABC, abstractmethod

from app.models.ollama import OllamaClient


class Agent(ABC):
    name: str

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm

    @abstractmethod
    async def run(self, prompt: str) -> str:
        raise NotImplementedError
