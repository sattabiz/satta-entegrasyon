@echo off
setlocal enabledelayedexpansion

echo ======================================================================
echo   SATTA ENTEGRASYON - MODERN SURUM PAKETLEME (.venv - PySide6)
echo ======================================================================
echo.

cd /d "%~dp0.."

:: 0. Versiyon Tespiti (versiyon.py)
set "APP_VERSION=1.2.8"
for /f "tokens=2 delims==" %%A in ('findstr /i "APP_VERSION" versiyon.py') do (
    set "TMP_VER=%%A"
    set "TMP_VER=!TMP_VER: =!"
    set "TMP_VER=!TMP_VER:"=!"
    set "APP_VERSION=!TMP_VER!"
)

echo [BILGI] Uygulama Versiyonu: %APP_VERSION%
echo #define MyAppVersion "%APP_VERSION%" > "installer\version.iss"

:: 1. Inno Setup Derleyici (ISCC.exe) Tespiti
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC for /f "tokens=*" %%i in ('where iscc 2^>nul') do set "ISCC=%%i"

if defined ISCC goto HAS_ISCC
echo [HATA] Inno Setup 6 derleyicisi (ISCC.exe) bulunamadi.
echo Lutfen Inno Setup 6'nin kurulu oldugundan emin olun.
pause
exit /b 1

:HAS_ISCC
echo [BILGI] Inno Setup Derleyicisi: "%ISCC%"

:: 2. LogoBridge (win-x86) Derleme Kontrolu
echo.
echo [1/3] LogoBridge.Console (win-x86 self-contained) hazirlaniyor...
where dotnet >nul 2>nul
if %ERRORLEVEL% NEQ 0 goto DOTNET_MISSING
echo dotnet publish calistiriliyor...
dotnet publish LogoBridge\src\LogoBridge.Console\LogoBridge.Console.csproj -c Release -r win-x86 --self-contained true -o LogoBridge\publish
goto CHECK_BRIDGE

:DOTNET_MISSING
echo [BILGI] dotnet CLI bulunamadi, mevcut on derlenmis dosyalar kullanilacak.

:CHECK_BRIDGE
if exist "LogoBridge\publish\LogoBridge.Console.exe" goto BRIDGE_OK
echo [HATA] LogoBridge\publish\LogoBridge.Console.exe bulunamadi.
pause
exit /b 1

:BRIDGE_OK
echo [OK] LogoBridge x86 hazir.

:: 3. PyInstaller Derlemesi (.venv)
echo.
echo [2/3] PyInstaller ile SattaEntegrasyon derleniyor (.venv)...
set "PYINSTALLER_CMD="
if exist ".venv\Scripts\pyinstaller.exe" set "PYINSTALLER_CMD=.venv\Scripts\pyinstaller.exe"
if not defined PYINSTALLER_CMD set "PYINSTALLER_CMD=pyinstaller"

echo Calistiriliyor: %PYINSTALLER_CMD% --noconfirm --clean SattaEntegrasyon.spec
call %PYINSTALLER_CMD% --noconfirm --clean SattaEntegrasyon.spec
if %ERRORLEVEL% NEQ 0 goto PY_ERROR

if not exist "dist\SattaEntegrasyon\SattaEntegrasyon.exe" goto PY_MISSING
echo [OK] PyInstaller derlemesi tamamlandi.
goto RUN_INNO

:PY_ERROR
echo [HATA] PyInstaller derlemesi basarisiz oldu.
pause
exit /b %ERRORLEVEL%

:PY_MISSING
echo [HATA] dist\SattaEntegrasyon\SattaEntegrasyon.exe olusturulamadi.
pause
exit /b 1

:: 4. Inno Setup ile Paketleme
:RUN_INNO
echo.
echo [3/3] Inno Setup ile kurulum paketi olusturuluyor (setup.iss, v%APP_VERSION%)...
"%ISCC%" /DMyAppVersion="%APP_VERSION%" "installer\setup.iss"
if %ERRORLEVEL% NEQ 0 goto INNO_ERROR

echo.
echo ======================================================================
echo   [BASARILI] Modern Kurulum Paketi Basariyla Olusturuldu.
echo   Versiyon     : %APP_VERSION%
echo   Cikti Dosyasi: installer\Output\SattaEntegrasyon-Setup.exe
echo ======================================================================
echo.
pause
exit /b 0

:INNO_ERROR
echo [HATA] Inno Setup derlemesi basarisiz oldu.
pause
exit /b %ERRORLEVEL%
