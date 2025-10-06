@echo off
setlocal enabledelayedexpansion

:: === CONFIG READING ===
set "CONFIG=config.ini"

if defined STEAMCMDFOLDER (
    set "STEAMCMD=%STEAMCMDFOLDER%\steamcmd.exe"
) else (
    set "STEAMCMD=steamcmd.exe"
)

if not exist "%CONFIG%" (
    echo ERROR: %CONFIG% not found!
    echo Create a config.ini file in the same folder.
    pause
    exit /b 1
)


for /f "usebackq tokens=1,* delims==" %%A in ("%CONFIG%") do (
    set "%%A=%%B"
)

:: === Path ===
set "STEAMCMD=%STEAMCMDFOLDER%"
if not "%STEAMCMD:~-1%"=="\" set "STEAMCMD=%STEAMCMD%\"
set "STEAMCMD=%STEAMCMD%steamcmd.exe"

set "DOWNLOAD_PATH=%STEAMCMDFOLDER%\steamapps\workshop\content\%APPID%"
set "MOVE_PATH=%MOVE_PATH%"

:: === Terminal Log ===
echo.
echo [APP] Jopseps Mod Downloader
echo ---------------------------------
echo AppID              : %APPID%
echo SteamCMD Path      : %STEAMCMD%
echo Move After Download: %MOVE_AFTER_DOWNLOAD%
echo Move Path          : %MOVE_PATH%
echo ---------------------------------
echo.

:main
set "SCRIPT=%temp%\steamcmd_script.txt"
echo login anonymous > "%SCRIPT%"

set "firstInput=1"

:loop
set /p ID=Enter Workshop ID (q to quit): 
if /i "!ID!"=="q" (
    if "!firstInput!"=="1" (
        echo Exiting program...
        del "%SCRIPT%" >nul 2>&1
        exit /b
    ) else (
        goto run
    )
)
set "firstInput=0"
if "!ID!"=="" goto loop
echo workshop_download_item %APPID% %ID% validate >> "%SCRIPT%"
goto loop

:run
echo quit >> "%SCRIPT%"
echo.
echo === Starting download... ===
"%STEAMCMD%" +runscript "%SCRIPT%"
echo.
echo === Download completed ===

:: === Moving The Mod Files ===
if "%MOVE_AFTER_DOWNLOAD%"=="1" (
    echo.
    echo === Moving mod folders... ===
    if not exist "%DOWNLOAD_PATH%" (
        echo [ERROR] Download folder not found: %DOWNLOAD_PATH%
        goto after_move
    )

    if not exist "%MOVE_PATH%" (
        echo [INFO] Creating folder: %MOVE_PATH% ...
        mkdir "%MOVE_PATH%" >nul 2>&1
    )

    for /d %%F in ("%DOWNLOAD_PATH%\*") do (
        echo Moving: %%~nxF
        robocopy "%%F" "%MOVE_PATH%\%%~nxF" /E /MOVE >nul
        if errorlevel 1 (
            echo [OK] %%~nxF moved successfully.
        ) else (
            echo [WARNING] %%~nxF could not be moved.
        )
    )
)

:after_move
echo.
goto main