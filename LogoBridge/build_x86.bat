@echo off
echo ===================================================
echo LogoBridge x86 (32-bit) Derleme
echo ===================================================
cd /d "%~dp0"
dotnet build src\LogoBridge.Console\LogoBridge.Console.csproj -c Release -r win-x86
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Derleme basarisiz oldu!
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo [BASARILI] LogoBridge x86 derlemesi tamamlandi.
pause
