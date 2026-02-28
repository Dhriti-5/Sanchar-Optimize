# Simple HTTP Server for Testing
# This serves the test page over HTTP so you don't need to enable file URL access

Write-Host "🚀 Starting Sanchar-Optimize Test Server..." -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Python detected: $pythonVersion" -ForegroundColor Green
    Write-Host ""
    Write-Host "📡 Starting HTTP server on port 8000..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "🌐 Open in browser: http://localhost:8000/test-page.html" -ForegroundColor Green
    Write-Host ""
    Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
    Write-Host "----------------------------------------" -ForegroundColor Gray
    Write-Host ""
    
    # Navigate to test folder and start server
    Set-Location -Path "$PSScriptRoot"
    python -m http.server 8000
    
} else {
    Write-Host "❌ Python not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "1. Install Python: https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "2. Or enable file URL access in Chrome (see EXTENSION_NOT_DETECTED_FIX.md)" -ForegroundColor White
    Write-Host "3. Or test directly on YouTube" -ForegroundColor White
    Write-Host ""
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
