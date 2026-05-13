import json
import asyncio
import logging

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, Depends
from fastapi.responses import FileResponse, StreamingResponse

from app.api.schemas import (
    ChatCreateRequest,
    ChatRequest,
    ChatMemoryRequest,
    ChatMemoryResponse,
    ChatResponse,
    ChatUpdateRequest,
    ExperimentRequest,
    RagIngestPathRequest,
    RagQueryRequest,
    SettingsRequest,
    SettingsResponse,
    TaskRunRequest,
    TaskRunResponse,
    UsageResponse,
    VoiceOutputRequest,
)
from app.core.config import settings
from app.core.auth import get_current_user
from app.core.orchestrator import Orchestrator
from app.models.ollama import OllamaClient
from app.db.usage import get_settings, update_settings, usage_summary
from app.research.tracking import ExperimentRun, ExperimentTracker
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.services.rag_service import RagService
from app.services.voice_service import VoiceService

router = APIRouter()
ollama = OllamaClient()
memory = MemoryService()
orchestrator = Orchestrator(ollama)
rag = RagService(ollama)
chat_service = ChatService(ollama, memory, rag)
voice_service = VoiceService(chat_service)
experiments = ExperimentTracker()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/capabilities")
async def capabilities() -> dict[str, object]:
    models_status = await OllamaClient(timeout=2.0).list_models()
    voice_status = voice_service.capabilities()
    rag_status = rag.capabilities()
    return {
        "chat": {
            "available": bool(models_status.get("models")) or bool(settings.openai_api_key),
            "ollama_base_url_configured": bool(settings.ollama_base_url),
            "openai_fallback": bool(settings.openai_api_key),
            "message": models_status.get("error") or "Chat model endpoint is reachable.",
        },
        "voice": voice_status,
        "rag": rag_status,
    }


@router.get("/models")
async def models() -> dict[str, object]:
    return await ollama.list_models()


@router.get("/settings", response_model=SettingsResponse)
async def read_settings(current_user: dict = Depends(get_current_user)) -> SettingsResponse:
    return SettingsResponse(**get_settings(current_user["id"]))


@router.put("/settings", response_model=SettingsResponse)
async def save_settings(request: SettingsRequest, current_user: dict = Depends(get_current_user)) -> SettingsResponse:
    return SettingsResponse(**update_settings(current_user["id"], request.model_dump(exclude_unset=True)))


@router.get("/usage", response_model=UsageResponse)
async def usage(current_user: dict = Depends(get_current_user)) -> UsageResponse:
    return UsageResponse(**usage_summary(current_user["id"]))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)) -> ChatResponse:
    try:
        result = await chat_service.chat(
            message=request.message,
            user_id=current_user["id"],
            mode=request.mode,
            model=request.model,
            use_rag=request.use_rag,
            use_memory=request.use_memory,
            temperature=request.temperature,
            chat_id=request.chat_id,
        )
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: dict = Depends(get_current_user)) -> StreamingResponse:
    try:
        chat_id, model, sources, stream = await chat_service.stream_chat(
            message=request.message,
            user_id=current_user["id"],
            mode=request.mode,
            model=request.model,
            use_rag=request.use_rag,
            use_memory=request.use_memory,
            temperature=request.temperature,
            chat_id=request.chat_id,
        )
    except Exception as exc:
        logger.exception("Streaming chat setup failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def event_stream():
        yield _sse({"type": "meta", "chat_id": chat_id, "model": model, "sources": sources})
        full = []
        try:
            async with asyncio.timeout(settings.chat_timeout_seconds):
                async for token in stream:
                    full.append(token)
                    yield _sse({"type": "token", "token": token, "done": False})
            yield _sse(
                {
                    "type": "done",
                    "token": "",
                    "done": True,
                    "message": "".join(full),
                    "chat_id": chat_id,
                    "model": model,
                    "sources": sources,
                }
            )
        except TimeoutError:
            logger.warning("Streaming chat timed out after %s seconds", settings.chat_timeout_seconds)
            yield _sse(
                {
                    "type": "error",
                    "done": True,
                    "error": "The model took too long to respond. Try a shorter prompt or a faster model.",
                }
            )
        except Exception as exc:
            logger.exception("Streaming chat failed")
            yield _sse({"type": "error", "done": True, "error": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat/new")
async def create_chat(request: ChatCreateRequest, current_user: dict = Depends(get_current_user)) -> dict[str, object]:
    return await memory.create_chat(
        user_id=current_user["id"],
        title=request.title,
        mode=request.mode,
        model=request.model,
    )


@router.get("/history")
async def history(current_user: dict = Depends(get_current_user), chat_id: str | None = Query(None)) -> dict[str, object]:
    user_id = current_user["id"]
    if chat_id:
        return {"chat_id": chat_id, "messages": await memory.get_chat_messages(chat_id, user_id)}
    return {"chats": await memory.list_chats(user_id)}


@router.patch("/chat/{chat_id}")
async def rename_chat(chat_id: str, request: ChatUpdateRequest, current_user: dict = Depends(get_current_user)) -> dict[str, object]:
    updated = await memory.rename_chat(chat_id, request.title, current_user["id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"id": chat_id, "title": request.title, "status": "updated"}


@router.delete("/chat/{chat_id}")
async def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    deleted = await memory.delete_chat(chat_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"id": chat_id, "status": "deleted"}


@router.delete("/history")
async def delete_history(current_user: dict = Depends(get_current_user)) -> dict[str, object]:
    deleted = await memory.delete_all_chats(current_user["id"])
    return {"status": "deleted", "deleted": deleted}


@router.post("/chat/memory", response_model=ChatMemoryResponse)
async def chat_memory(request: ChatMemoryRequest, current_user: dict = Depends(get_current_user)) -> ChatMemoryResponse:
    if request.clear:
        await memory.clear_history(current_user["id"])
    history = await memory.get_history(current_user["id"])
    return ChatMemoryResponse(user_id=current_user["id"], messages=history)


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict[str, object]:
    if not rag.capabilities()["available"]:
        raise HTTPException(status_code=503, detail="Document AI is unavailable in this deployment.")
    try:
        ingested = await rag.ingest_uploads(files)
        return {"ingested": ingested}
    except Exception as exc:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ask-doc")
async def ask_doc(request: RagQueryRequest) -> dict[str, object]:
    try:
        return await rag.query(request.question, request.model, request.top_k)
    except Exception as exc:
        logger.exception("Document query failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/voice-input")
async def voice_input(file: UploadFile = File(...)) -> dict[str, str]:
    try:
        audio_path = await voice_service.save_upload(file)
        transcript = await voice_service.transcribe_audio(audio_path)
        return {"text": transcript}
    except Exception as exc:
        logger.exception("Voice input failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/voice-output")
async def voice_output(request: VoiceOutputRequest) -> FileResponse:
    try:
        audio_path = await voice_service.generate_speech(request.text)
        return FileResponse(audio_path, media_type="audio/wav", filename="agentforge-response.wav")
    except Exception as exc:
        logger.exception("Voice output failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/voice-chat")
async def voice_chat(
    file: UploadFile = File(...),
    mode: str = Form("general"),
    model: str | None = Form(None),
    current_user: dict = Depends(get_current_user),
) -> dict[str, object]:
    try:
        audio_path = await voice_service.save_upload(file)
        result = await voice_service.voice_chat_pipeline(audio_path, user_id=current_user["id"], mode=mode, model=model)
        return result
    except Exception as exc:
        logger.exception("Voice chat failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/tasks/run", response_model=TaskRunResponse)
async def run_task(request: TaskRunRequest) -> TaskRunResponse:
    result = await orchestrator.run(request.goal)
    return TaskRunResponse(**result)


@router.post("/rag/ingest")
async def ingest(files: list[UploadFile] = File(...)) -> dict[str, object]:
    ingested = await rag.ingest_uploads(files)
    return {"ingested": ingested}


@router.post("/rag/ingest-path")
async def ingest_path(request: RagIngestPathRequest) -> dict[str, object]:
    ingested = await rag.ingest_path(request.path)
    return {"ingested": ingested}


@router.post("/rag/query")
async def rag_query(request: RagQueryRequest) -> dict[str, object]:
    return await rag.query(request.question, request.model, request.top_k)


@router.post("/speech/stt")
async def speech_to_text(file: UploadFile = File(...)) -> dict[str, str]:
    return await voice_input(file)


@router.post("/speech/tts")
async def text_to_speech(request: VoiceOutputRequest) -> FileResponse:
    return await voice_output(request)


@router.get("/research/experiments")
async def list_experiments() -> dict[str, object]:
    return {"experiments": experiments.list()}


@router.post("/research/experiments")
async def log_experiment(request: ExperimentRequest) -> dict[str, object]:
    run = ExperimentRun(
        name=request.name,
        model=request.model,
        dataset=request.dataset,
        notes=request.notes,
    )
    experiment_id = experiments.log(run, request.metrics)
    return {"id": experiment_id, "status": "logged"}
