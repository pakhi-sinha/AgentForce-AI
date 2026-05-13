#!/usr/bin/env sh
set -eu

OLLAMA_PID=""
START_OLLAMA="${AGENTFORGE_START_OLLAMA:-auto}"
OLLAMA_URL="${OLLAMA_BASE_URL:-${AGENTFORGE_OLLAMA_BASE_URL:-}}"

should_start_ollama=false
if [ "$START_OLLAMA" = "true" ]; then
  should_start_ollama=true
elif [ "$START_OLLAMA" = "auto" ]; then
  case "$OLLAMA_URL" in
    ""|*127.0.0.1*|*localhost*) should_start_ollama=true ;;
  esac
fi

if [ "$should_start_ollama" = "true" ] && command -v ollama >/dev/null 2>&1; then
  ollama serve &
  OLLAMA_PID="$!"

  sleep 3
  (ollama pull "${AGENTFORGE_DEFAULT_MODEL:-llama3}" || true) &
fi

uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" &
API_PID="$!"

term_handler() {
  kill "$API_PID" ${OLLAMA_PID:-} 2>/dev/null || true
}

trap term_handler INT TERM
wait "$API_PID"
