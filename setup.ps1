# ─────────────────────────────────────────────────────────────────────────────
# PGAI Voice Bot — Windows Machine Setup Script
# Run once after cloning the repo:  .\setup.ps1
#
# What this script does:
#   1. Checks Python 3.10–3.12 is available
#   2. Creates and activates a Python virtual environment
#   3. Installs pip dependencies (adds audioop-lts if Python 3.13+)
#   4. Creates required output directories
#   5. Copies .env.example to .env (if .env doesn't already exist)
#   6. Checks if ngrok is installed; prints install instructions if not
#   7. Prints next-step instructions
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot   # directory containing this script

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  PGAI Voice Bot — Machine Setup" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Check Python ──────────────────────────────────────────────────────
Write-Host "[1/7] Checking Python version..." -ForegroundColor Yellow

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 10) {
                $pythonCmd = $cmd
                Write-Host "    Found: $ver ($cmd)" -ForegroundColor Green
                if ($minor -ge 13) {
                    Write-Host "    NOTE: Python 3.13+ detected — will install audioop-lts" -ForegroundColor Yellow
                }
                break
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Host "ERROR: Python 3.10+ not found." -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
}

# ── Step 2: Create virtual environment ───────────────────────────────────────
Write-Host ""
Write-Host "[2/7] Creating virtual environment (venv)..." -ForegroundColor Yellow

$venvPath = Join-Path $ProjectRoot "venv"
if (Test-Path $venvPath) {
    Write-Host "    venv already exists — skipping creation" -ForegroundColor Gray
} else {
    & $pythonCmd -m venv $venvPath
    Write-Host "    Created: $venvPath" -ForegroundColor Green
}

# ── Step 3: Activate venv & install dependencies ──────────────────────────────
Write-Host ""
Write-Host "[3/7] Installing Python dependencies..." -ForegroundColor Yellow

$pip = Join-Path $venvPath "Scripts\pip.exe"
if (-not (Test-Path $pip)) {
    Write-Host "ERROR: pip not found at $pip" -ForegroundColor Red
    exit 1
}

& $pip install --upgrade pip --quiet
& $pip install -r (Join-Path $ProjectRoot "requirements.txt")

# For Python 3.13+, audioop was removed from stdlib — install the shim
$pyVer = & (Join-Path $venvPath "Scripts\python.exe") -c "import sys; print(sys.version_info.minor)"
if ([int]$pyVer -ge 13) {
    Write-Host "    Installing audioop-lts for Python 3.13+ compatibility..." -ForegroundColor Yellow
    & $pip install audioop-lts --quiet
}

Write-Host "    Dependencies installed ✓" -ForegroundColor Green

# ── Step 4: Create output directories ────────────────────────────────────────
Write-Host ""
Write-Host "[4/7] Creating output directories..." -ForegroundColor Yellow

foreach ($dir in @("recordings", "transcripts", "logs")) {
    $dirPath = Join-Path $ProjectRoot $dir
    if (-not (Test-Path $dirPath)) {
        New-Item -ItemType Directory -Path $dirPath | Out-Null
        Write-Host "    Created: $dir\" -ForegroundColor Green
    } else {
        Write-Host "    Exists:  $dir\" -ForegroundColor Gray
    }
}

# ── Step 5: Create .env from .env.example ────────────────────────────────────
Write-Host ""
Write-Host "[5/7] Setting up .env file..." -ForegroundColor Yellow

$envFile     = Join-Path $ProjectRoot ".env"
$envExample  = Join-Path $ProjectRoot ".env.example"

if (Test-Path $envFile) {
    Write-Host "    .env already exists — not overwriting" -ForegroundColor Gray
} elseif (Test-Path $envExample) {
    Copy-Item $envExample $envFile
    Write-Host "    .env created from .env.example" -ForegroundColor Green
    Write-Host "    ACTION REQUIRED: Edit .env with your API keys!" -ForegroundColor Magenta
} else {
    Write-Host "    WARNING: .env.example not found — create .env manually" -ForegroundColor Red
}

# ── Step 6: Check ngrok ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "[6/7] Checking ngrok..." -ForegroundColor Yellow

$ngrokFound = $false
try {
    $ngrokVer = & ngrok version 2>&1
    Write-Host "    Found: $ngrokVer" -ForegroundColor Green
    $ngrokFound = $true
} catch { }

if (-not $ngrokFound) {
    Write-Host "    ngrok not found in PATH." -ForegroundColor Yellow
    Write-Host "    Install options:" -ForegroundColor Yellow
    Write-Host "      Option A (winget):    winget install ngrok.ngrok" -ForegroundColor White
    Write-Host "      Option B (Chocolatey): choco install ngrok" -ForegroundColor White
    Write-Host "      Option C (manual):    Download from https://ngrok.com/download" -ForegroundColor White
    Write-Host "                            and place ngrok.exe in this folder or a PATH directory." -ForegroundColor White
    Write-Host "    After installing ngrok, sign up at https://ngrok.com (free) and run:" -ForegroundColor White
    Write-Host "      ngrok config add-authtoken <YOUR_TOKEN>" -ForegroundColor Cyan
}

# ── Step 7: Summary ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[7/7] Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  NEXT STEPS" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Fill in your API keys in .env:" -ForegroundColor White
Write-Host "       TWILIO_ACCOUNT_SID   ← from console.twilio.com" -ForegroundColor Gray
Write-Host "       TWILIO_AUTH_TOKEN     ← from console.twilio.com" -ForegroundColor Gray
Write-Host "       TWILIO_FROM_NUMBER    ← your Twilio phone number (+1XXXXXXXXXX)" -ForegroundColor Gray
Write-Host "       OPENAI_API_KEY        ← from platform.openai.com/api-keys" -ForegroundColor Gray
Write-Host "       DEEPGRAM_API_KEY      ← from console.deepgram.com" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Run the pre-flight check to verify all keys work:" -ForegroundColor White
Write-Host "       venv\Scripts\python.exe verify_setup.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Start ngrok in a separate terminal:" -ForegroundColor White
Write-Host "       ngrok http 8080" -ForegroundColor Cyan
Write-Host "     Then copy the Forwarding URL (https://xxxx.ngrok-free.app)" -ForegroundColor Gray
Write-Host "     and update NGROK_URL in your .env" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Start the bot server:" -ForegroundColor White
Write-Host "       venv\Scripts\python.exe main.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  5. Verify the health endpoint:" -ForegroundColor White
Write-Host "       curl http://localhost:8080/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  6. Place your first test call:" -ForegroundColor White
Write-Host "       venv\Scripts\python.exe run_scenario.py --scenario simple_scheduling" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ACTIVATE venv in your current shell with:" -ForegroundColor Yellow
Write-Host "    venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""
