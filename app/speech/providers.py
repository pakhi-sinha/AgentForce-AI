class SpeechToTextProvider:
    async def transcribe(self, audio_path: str, language: str | None = None) -> str:
        raise NotImplementedError("Wire this to whisper.cpp or Vosk.")


class TextToSpeechProvider:
    async def synthesize(self, text: str, voice: str, output_path: str) -> str:
        raise NotImplementedError("Wire this to Piper TTS.")
