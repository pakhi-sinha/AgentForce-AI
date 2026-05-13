# Deployment Guide

## Standard Local Deployment

```powershell
docker-compose up --build
```

Services:

- `api`: FastAPI control plane.
- `ollama`: local model server.
- `postgres`: structured memory.
- `chromadb`: vector database.
- `redis`: local cache and coordination.

## Edge Profile

For low-resource devices:

- Use `phi3`, `gemma:2b`, or another small quantized model.
- Keep `AGENTFORGE_SQLITE_PATH` enabled.
- Disable PostgreSQL, Redis, and ChromaDB if memory is constrained.
- Prefer the built-in SQLite RAG fallback for small private corpora.

## GPU Notes

Ollama automatically uses supported local acceleration when available. For NVIDIA Docker hosts, install the NVIDIA container runtime and expose GPUs to the `ollama` service. For Apple Silicon, run Ollama natively and point `AGENTFORGE_OLLAMA_BASE_URL` to the host Ollama endpoint.

## Air-Gapped Deployment

1. Pre-pull Docker images on an internet-enabled machine.
2. Export images with `docker save`.
3. Copy images, this repository, and `models/ollama` to the target machine.
4. Import images with `docker load`.
5. Run `docker-compose up --build`.
