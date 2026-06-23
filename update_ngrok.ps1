# ─────────────────────────────────────────────────────────────────────────────
# update_ngrok.ps1 — Grab the current ngrok URL and write it to .env
#
# ngrok generates a NEW random URL every time it restarts (free tier).
# Run this script after restarting ngrok so .env stays in sync.
#
# Usage:
#   .\update_ngrok.ps1                 # auto-detect from ngrok local API
#   .\update_ngrok.ps1 -Url https://xxxx.ngrok-free.app   # paste manually
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$Url = ""
)

$EnvFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $EnvFile)) {
    Write-Host "ERROR: .env file not found at $EnvFile" -ForegroundColor Red
    Write-Host "Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# ── Auto-detect from ngrok local API ─────────────────────────────────────────
if (-not $Url) {
    Write-Host "Querying ngrok local API (http://127.0.0.1:4040)..." -ForegroundColor Yellow
    try {
        $response = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
        $httpsUrl = ($response.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
        if ($httpsUrl) {
            $Url = $httpsUrl
            Write-Host "Detected: $Url" -ForegroundColor Green
        } else {
            Write-Host "No HTTPS tunnel found. Is ngrok running with: ngrok http 8080?" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "Could not reach ngrok API. Make sure ngrok is running." -ForegroundColor Red
        Write-Host "You can also pass the URL manually:" -ForegroundColor Yellow
        Write-Host "  .\update_ngrok.ps1 -Url https://xxxx.ngrok-free.app" -ForegroundColor Cyan
        exit 1
    }
}

# ── Validate URL format ───────────────────────────────────────────────────────
if ($Url -notmatch "^https://") {
    Write-Host "ERROR: URL must start with https://" -ForegroundColor Red
    Write-Host "Got: $Url" -ForegroundColor Red
    exit 1
}

# ── Update NGROK_URL in .env ──────────────────────────────────────────────────
$envContent  = Get-Content $EnvFile -Raw
$newContent  = $envContent -replace "(?m)^NGROK_URL=.*$", "NGROK_URL=$Url"

if ($envContent -notmatch "NGROK_URL=") {
    # Key doesn't exist yet — append it
    $newContent = $envContent.TrimEnd() + "`nNGROK_URL=$Url`n"
}

Set-Content $EnvFile $newContent -NoNewline

Write-Host ""
Write-Host "  .env updated:" -ForegroundColor Green
Write-Host "    NGROK_URL=$Url" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Twilio webhook URLs that will be used:" -ForegroundColor White
Write-Host "    TwiML:     $Url/incoming-call" -ForegroundColor Gray
Write-Host "    WS Stream: $($Url -replace 'https://','wss://')/media-stream" -ForegroundColor Gray
Write-Host "    Recording: $Url/recording-callback" -ForegroundColor Gray
Write-Host ""
Write-Host "  Restart main.py to pick up the new URL." -ForegroundColor Yellow
Write-Host ""