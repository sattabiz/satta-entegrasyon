@echo off
echo ===================================================
echo LogoBridge x86 (32-bit) Self-Contained Yayimlama
echo ===================================================
cd /d "%~dp0"
dotnet publish src\LogoBridge.Console\LogoBridge.Console.csproj -c Release -r win-x86 --self-contained true -o publish
if %ERRORLEVEL% NEQ 0 (
    echo [HATA] Derleme veya yayimlama basarisiz oldu!
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo [BASARILI] LogoBridge.Console.exe x86 olarak publish klasorune olusturuldu.
pause
