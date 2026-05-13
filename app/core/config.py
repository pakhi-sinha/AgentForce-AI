import os

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTFORGE_", env_file=".env", extra="ignore")

    offline_mode: bool = True
    enable_online_mode: bool = False
    default_model: str = "llama3"
    fast_model: str = "phi3"
    coding_model: str = "deepseek-coder"
    ollama_port: int | None = Field(
        default=None,
        validation_alias=AliasChoices("OLLAMA_PORT", "AGENTFORGE_OLLAMA_PORT"),
    )
    port: int = Field(default=8080, validation_alias=AliasChoices("PORT", "AGENTFORGE_PORT"))
    ollama_base_url: str | None = Field(
        default="http://host.docker.internal:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "AGENTFORGE_OLLAMA_BASE_URL"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "AGENTFORGE_OPENAI_API_KEY"),
    )
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    sqlite_path: str = "data/agentforge.sqlite3"
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 160
    chat_timeout_seconds: int = 180
    max_agent_iterations: int = 2
    postgres_dsn: str | None = None
    chroma_host: str = "127.0.0.1"
    chroma_port: int = 8000
    redis_url: str = "redis://127.0.0.1:6379/0"
    voice_work_dir: str = "data/voice"
    whisper_binary_path: str = "whisper-cli"
    whisper_model_path: str = "models/whisper/ggml-base.en.bin"
    piper_binary_path: str = "piper"
    piper_model_path: str = "models/piper/en_US-lessac-medium.onnx"
    jwt_secret: str = Field(default="change-this-secret", validation_alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_exp_seconds: int = 60 * 60 * 24 * 7  # 7 days

    @model_validator(mode="after")
    def apply_ollama_port_fallback(self) -> "Settings":
        if "OLLAMA_BASE_URL" not in os.environ and "AGENTFORGE_OLLAMA_BASE_URL" not in os.environ:
            if self.ollama_port:
                self.ollama_base_url = f"http://127.0.0.1:{self.ollama_port}"
        return self


settings = Settings()
