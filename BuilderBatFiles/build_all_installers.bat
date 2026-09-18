@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

:MENU
cls
echo ======================================================================
echo             SATTA ENTEGRASYON - KURULUM DERLEME MERKEZI
echo ======================================================================
echo.
echo   [1] Modern Surum Paketle (.venv - PySide6 / Python 3.12)
echo       ==^> installer\Output\SattaEntegrasyon-Setup.exe
echo.
echo   [2] Legacy Surum Paketle (.venv_legacy - PySide2 / Win7-8 Destekli)
echo       ==^> installer\Output\SattaEntegrasyon-Setup-Legacy.exe
echo.
echo   [3] Her Ikisini de Derle ve Paketle (Hepsi Bir Arada)
echo.
echo   [4] Yalnizca LogoBridge.Console (win-x86) Derle / Yayinla
echo.
echo   [5] Cikis
echo.
echo ======================================================================
set /p SECIM="Lutfen yapmak istediginiz islemi secin [1-5]: "

if "%SECIM%"=="1" goto BUILD_MODERN
if "%SECIM%"=="2" goto BUILD_LEGACY
if "%SECIM%"=="3" goto BUILD_BOTH
if "%SECIM%"=="4" goto BUILD_BRIDGE
if "%SECIM%"=="5" goto CIKIS

echo Gecersiz secim, lutfen tekrar deneyin.
ping 127.0.0.1 -n 3 >nul
goto MENU

:BUILD_MODERN
echo.
call "%~dp0build_installer_modern.bat"
goto MENU

:BUILD_LEGACY
echo.
call "%~dp0build_installer_legacy.bat"
goto MENU

:BUILD_BOTH
echo.
echo ======================================================================
echo   1/2: MODERN SURUM DERLENIYOR...
echo ======================================================================
call "%~dp0build_installer_modern.bat"
echo.
echo ======================================================================
echo   2/2: LEGACY SURUM DERLENIYOR...
echo ======================================================================
call "%~dp0build_installer_legacy.bat"
echo.
echo [TAMAMLANDI] Tum kurulum paketleri basariyla olusturuldu.
pause
goto MENU

:BUILD_BRIDGE
echo.
call "%~dp0..\LogoBridge\publish_x86.bat"
goto MENU

:CIKIS
echo Iyi calismalar.
pause
exit /b 0
