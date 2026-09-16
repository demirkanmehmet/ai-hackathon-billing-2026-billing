@echo off
REM S-A1 Alarm Firtinasi - Windows baslatici (cmd.exe / PowerShell / cift tiklama).
REM   run.cmd          arayuzu ac
REM   run.cmd cli      boru hattini terminalde kos
REM   run.cmd test     kurulumu dogrula
REM Harici bagimlilik yok; yalnizca Python 3.9+ gerekir.
setlocal enabledelayedexpansion

set "DIZIN=%~dp0"
set "AYGIT="
REM Cift tiklama argumansizdir; betikle cagrilan "cmd /c run.cmd test" degildir.
REM Bu ayrim olmadan otomasyon pause'da sonsuza kadar bekler.
set "ARGVAR=%~1"

REM Once py launcher, sonra PATH'teki python. Surum kontrolu calisma zamaninda
REM yapilmali; blok icinde %errorlevel% ayristirma aninda genisledigi icin
REM "if errorlevel" veya gecikmeli genisletme kullaniliyor.
py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1
if not errorlevel 1 set "AYGIT=py -3"

if not defined AYGIT (
    python -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>&1
    if not errorlevel 1 set "AYGIT=python"
)

if not defined AYGIT (
    echo HATA: Python 3.9+ bulunamadi.
    echo Kurulum: https://www.python.org/downloads/
    call :duraklat
    exit /b 1
)

%AYGIT% "%DIZIN%run.py" %*
set "SONUC=%errorlevel%"
call :duraklat
exit /b %SONUC%

:duraklat
REM Cift tiklamayla acildiysa pencere hemen kapanmasin. Saf batch dize
REM karsilastirmasi; harici komut (find/findstr) cagirmaz.
REM Uc kosulun HEPSI gerekli, yoksa otomasyon pause'da asili kalir:
REM   /c ile baslatilmis  +  betik adi komut satirinda  +  arguman verilmemis
if defined S_A1_NO_PAUSE goto :eof
if defined ARGVAR goto :eof
set "CL=%cmdcmdline%"
if "!CL!"=="!CL:/c=!" goto :eof
if "!CL!"=="!CL:%~nx0=!" goto :eof
echo.
pause
goto :eof
