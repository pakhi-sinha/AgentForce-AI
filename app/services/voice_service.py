from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from fastapi import UploadFile
import httpx

from app.core.config import settings
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)


class VoiceService:
    def __init__(self, chat: ChatService | None = None) -> None:
        self.chat = chat
        self.work_dir = Path(settings.voice_work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, file: UploadFile) -> Path:
        suffix = Path(file.filename or "input.wav").suffix or ".wav"
        path = self.work_dir / f"voice-input-{uuid4()}{suffix}"
        with path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        return path

    def capabilities(self) -> dict[str, object]:
        stt_available = self._offline_stt_available() or bool(settings.openai_api_key)
        tts_available = self._offline_tts_available() or bool(settings.openai_api_key)
        return {
            "available": stt_available or tts_available,
            "stt": stt_available,
            "tts": tts_available,
            "message": "Voice is available." if stt_available or tts_available else "Voice not available in deployment",
        }

    def _offline_stt_available(self) -> bool:
        return Path(settings.whisper_model_path).exists() and (
            shutil.which(settings.whisper_binary_path) is not None or Path(settings.whisper_binary_path).exists()
        )

    def _offline_tts_available(self) -> bool:
        return Path(settings.piper_model_path).exists() and (
            shutil.which(settings.piper_binary_path) is not None or Path(settings.piper_binary_path).exists()
        )

    async def transcribe_audio(self, file_path: str | Path) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        model_path = Path(settings.whisper_model_path)
        if not self._offline_stt_available():
            if settings.openai_api_key:
                return await self._openai_transcribe(path)
            raise RuntimeError(
                f"Whisper model not found at {model_path}. Mount a whisper.cpp .bin model or enable OpenAI fallback."
            )

        output_base = self.work_dir / f"transcript-{uuid4()}"
        command = [
            settings.whisper_binary_path,
            "-m",
            str(model_path),
            "-f",
            str(path),
            "-otxt",
            "-of",
            str(output_base),
        ]
        await self._run(command)
        transcript_path = output_base.with_suffix(".txt")
        if not transcript_path.exists():
            raise RuntimeError("Whisper did not produce a transcript file.")
        return transcript_path.read_text(encoding="utf-8", errors="ignore").strip()

    async def generate_speech(self, text: str) -> Path:
        if not text.strip():
            raise ValueError("Text is required for speech synthesis.")

        model_path = Path(settings.piper_model_path)
        if not self._offline_tts_available():
            if settings.openai_api_key:
                return await self._openai_tts(text)
            raise RuntimeError(
                f"Piper voice model not found at {model_path}. Mount a Piper .onnx voice model or enable OpenAI fallback."
            )

        output_path = self.work_dir / f"voice-output-{uuid4()}.wav"
        command = [
            settings.piper_binary_path,
            "--model",
            str(model_path),
            "--output_file",
            str(output_path),
        ]
        await self._run(command, input_text=text)
        if not output_path.exists():
            raise RuntimeError("Piper did not produce an audio file.")
        return output_path

    async def voice_chat_pipeline(
        self,
        audio_file: str | Path,
        user_id: str = "default",
        mode: str = "general",
        model: str | None = None,
    ) -> dict[str, object]:
        if self.chat is None:
            raise RuntimeError("Voice chat requires a ChatService instance.")
        transcript = await self.transcribe_audio(audio_file)
        chat_result = await self.chat.chat(transcript, user_id=user_id, mode=mode, model=model)
        audio_path = await self.generate_speech(str(chat_result["message"]))
        return {
            "transcript": transcript,
            "response": chat_result["message"],
            "audio_base64": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
            "audio_mime_type": "audio/wav",
            "audio_path": str(audio_path),
            "model": chat_result["model"],
            "mode": chat_result["mode"],
        }

    async def _run(self, command: list[str], input_text: str | None = None) -> None:
        if not shutil.which(command[0]) and not Path(command[0]).exists():
            raise RuntimeError(f"Required offline voice executable not found: {command[0]}")

        def run_command() -> None:
            completed = subprocess.run(
                command,
                input=input_text,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                logger.warning("Voice command failed: %s", detail)
                raise RuntimeError(f"Voice command failed: {detail}")

        await asyncio.to_thread(run_command)

    async def _openai_transcribe(self, path: Path) -> str:
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        with path.open("rb") as audio:
            files = {"file": (path.name, audio, "application/octet-stream")}
            data = {"model": "whisper-1"}
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{settings.openai_base_url.rstrip('/')}/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                return str(response.json().get("text", "")).strip()

    async def _openai_tts(self, text: str) -> Path:
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        payload = {"model": "tts-1", "voice": "alloy", "input": text, "response_format": "wav"}
        output_path = self.work_dir / f"voice-output-{uuid4()}.wav"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/audio/speech",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            output_path.write_bytes(response.content)
        return output_path
