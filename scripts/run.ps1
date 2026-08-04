$ErrorActionPreference = "Stop"
if (!(Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env. Add your Discord token before running again."
  exit 1
}
py -3.12 -m bot
