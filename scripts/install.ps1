param(
    [switch]$SkipModelPull
)

$ErrorActionPreference = "Stop"

Write-Host "AgentForge AI local setup"
Write-Host "Creating local data and model directories..."
New-Item -ItemType Directory -Force -Path "data", "data/postgres", "data/chroma", "models", "models/ollama" | Out-Null

if (-not $SkipModelPull) {
    Write-Host "Model pulls require internet during setup. Re-run with -SkipModelPull for air-gapped installs."
    Write-Host "After Ollama starts, install models with commands like: ollama pull llama3"
}

Write-Host "Starting AgentForge AI..."
docker-compose up --build
