# AgentForce AI

AgentForce AI is a production-ready, multi-page AI platform built on the existing FastAPI project. It keeps the current backend stack and upgrades the product into a cleaner SaaS-style app with landing, auth, `/app` workspace routing, chat history, settings, document upload, and model-aware error handling.

## Features

- Landing page at `/`
- Auth pages at `/login` and `/signup`
- Main AI workspace at `/app`
- JWT auth with SQLite and bcrypt
- ChatGPT-style sidebar, chat history, task modes, settings, and logout
- Task modes for General Chat, Study Mode, Research Mode, and Summarizer
- Streaming chat responses, Markdown rendering, copy, regenerate, loading state, and thinking animation
- Document upload with RAG toggle and SQLite fallback
- Docker-friendly Ollama configuration using `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- Clear capability messaging when Ollama is unavailable

## Project Structure

```text
app/
  api/
  core/
  db/
  models/
  services/
frontend/
  index.html
  script.js
  style.css
tests/
Dockerfile
docker-compose.yml
requirements.txt
.env.example
pytest.ini
```

## Local Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PORT=8080
uvicorn app.main:app --host 0.0.0.0 --port $env:PORT
```

Open:

```text
http://localhost:8080/
http://localhost:8080/login
http://localhost:8080/signup
http://localhost:8080/app
```

## Environment

```env
PORT=8080
OLLAMA_BASE_URL=http://host.docker.internal:11434
OPENAI_API_KEY=
AGENTFORGE_START_OLLAMA=auto
AGENTFORGE_DEFAULT_MODEL=llama3
AGENTFORGE_ENABLE_ONLINE_MODE=false
JWT_SECRET=change-this-secret
```

If Ollama is unreachable, the API returns a clear capability error and the frontend shows that model status instead of failing silently.

## Docker

```powershell
docker build -t agentforce-ai .
docker run -p 8080:8080 agentforce-ai
```

The container starts with:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## GitHub

```powershell
git init
git add .
git commit -m "AgentForce AI - production version"
git branch -M main
git remote add origin https://github.com/<username>/agentforge-ai.git
git push -u origin main
```

## Verification

```powershell
py -m compileall app
py -m pytest tests -q
node --check frontend/script.js
```
