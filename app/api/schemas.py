from pydantic import BaseModel, Field

from app.core.config import settings


class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    chat_id: str | None = None
    mode: str = "general"
    model: str = settings.default_model
    use_rag: bool = False
    use_memory: bool = True
    temperature: float = Field(default=0.7, ge=0, le=2)


class ChatResponse(BaseModel):
    chat_id: str | None = None
    user_id: str = "default"
    mode: str = "general"
    model: str
    message: str
    sources: list[str] = Field(default_factory=list)


class ChatCreateRequest(BaseModel):
    user_id: str = "default"
    title: str = "New chat"
    mode: str = "general"
    model: str = settings.default_model


class ChatUpdateRequest(BaseModel):
    user_id: str = "default"
    title: str


class ChatMemoryRequest(BaseModel):
    user_id: str = "default"
    clear: bool = False


class ChatMemoryResponse(BaseModel):
    user_id: str
    messages: list[dict[str, str]]


class TaskRunRequest(BaseModel):
    goal: str = Field(min_length=1)


class AgentStep(BaseModel):
    agent: str
    input: str
    output: str


class TaskRunResponse(BaseModel):
    task_id: str
    goal: str
    status: str
    final_answer: str
    plan: dict
    evaluation: dict
    trace: list[AgentStep]


class RagQueryRequest(BaseModel):
    question: str
    model: str = settings.default_model
    top_k: int = 5


class RagIngestPathRequest(BaseModel):
    path: str


class ExperimentRequest(BaseModel):
    name: str
    model: str
    dataset: str
    notes: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)


class VoiceOutputRequest(BaseModel):
    text: str


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    created_at: str


class SettingsRequest(BaseModel):
    model: str | None = None
    mode: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    memory_enabled: bool | None = None
    voice_enabled: bool | None = None
    rag_enabled: bool | None = None


class SettingsResponse(BaseModel):
    model: str
    mode: str
    temperature: float
    memory_enabled: bool
    voice_enabled: bool
    rag_enabled: bool


class UsageResponse(BaseModel):
    messages: int
    tokens: int
    chats: int
    documents: int
