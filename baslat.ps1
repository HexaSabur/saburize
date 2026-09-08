# ============================================================
#  Otonom Ajan — Tek Tık Başlatıcı
#  Kullanım: Sağ tık > "PowerShell ile Çalıştır"
# ============================================================

$Host.UI.RawUI.WindowTitle = "Otonom Ajan Başlatıcı"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║      🤖  OTONOM AJAN BAŞLATIYOR          ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python kontrolü ───────────────────────────────────
Write-Host "▶ Python kontrol ediliyor..." -ForegroundColor Yellow
try {
    $pyVer = python --version 2>&1
    Write-Host "  ✅ $pyVer bulundu." -ForegroundColor Green
} catch {
    Write-Host "  ❌ Python bulunamadı! Lütfen Python 3.10+ kurun." -ForegroundColor Red
    Read-Host "Çıkmak için Enter'a basın"
    exit 1
}

# ── 2. Bağımlılıkları kur ────────────────────────────────
Write-Host ""
Write-Host "▶ Python bağımlılıkları yükleniyor..." -ForegroundColor Yellow
pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Bağımlılık yükleme başarısız!" -ForegroundColor Red
    Read-Host "Çıkmak için Enter'a basın"
    exit 1
}
Write-Host "  ✅ Bağımlılıklar hazır." -ForegroundColor Green

# ── 3. API Key kontrolü ──────────────────────────────────
Write-Host ""
if ([string]::IsNullOrEmpty($env:GEMINI_API_KEY)) {
    Write-Host "  ⚠️  GEMINI_API_KEY ortam değişkeni bulunamadı." -ForegroundColor Yellow
    Write-Host "     API anahtarınızı panelden girebilirsiniz (localStorage'da saklanır)." -ForegroundColor DarkGray
} else {
    $maskedKey = $env:GEMINI_API_KEY.Substring(0, [Math]::Min(8, $env:GEMINI_API_KEY.Length)) + "..."
    Write-Host "  ✅ GEMINI_API_KEY bulundu: $maskedKey" -ForegroundColor Green
}

# ── 4. Port kontrolü ─────────────────────────────────────
Write-Host ""
Write-Host "▶ Port 8000 kontrol ediliyor..." -ForegroundColor Yellow
$portKullanim = netstat -ano 2>$null | Select-String ":8000 "
if ($portKullanim) {
    Write-Host "  ⚠️  Port 8000 zaten kullanımda." -ForegroundColor Yellow
    $devam = Read-Host "  Yine de başlatılsın mı? (E/H)"
    if ($devam -ne "E" -and $devam -ne "e") { exit 0 }
} else {
    Write-Host "  ✅ Port 8000 müsait." -ForegroundColor Green
}

# ── 5. Sunucuyu başlat ───────────────────────────────────
Write-Host ""
Write-Host "▶ FastAPI sunucusu başlatılıyor (http://localhost:8000)..." -ForegroundColor Cyan
Write-Host "  Durdurmak için: Ctrl+C" -ForegroundColor DarkGray
Write-Host ""

# 2 saniye bekle, sonra tarayıcıyı aç
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:8000"
} | Out-Null

# Sunucuyu başlat (ana pencerede, log görünür)
uvicorn app:app --reload --host 0.0.0.0 --port 8000
