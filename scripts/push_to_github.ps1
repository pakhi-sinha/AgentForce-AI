param(
  [Parameter(Mandatory = $true)]
  [string]$RemoteUrl,
  [string]$Message = "Initial commit - AgentForge AI"
)

if (-not (Test-Path ".git")) {
  git init
}

git add .
git commit -m $Message
git branch -M main

if (git remote get-url origin 2>$null) {
  git remote set-url origin $RemoteUrl
} else {
  git remote add origin $RemoteUrl
}

git push -u origin main
