@echo off
setlocal enabledelayedexpansion

:: === CONFIG READING ===
set "CONFIG=config.ini"
if not exist "%CONFIG%" (
    echo ERROR: %CONFIG% not found!
    pause
    exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in ("%CONFIG%") do (
    set "%%A=%%B"
)

:: === FIX PATH ===
if "%STEAMCMDFOLDER:~-1%"=="\" (
    set "STEAMCMD=%STEAMCMDFOLDER%steamcmd.exe"
) else (
    set "STEAMCMD=%STEAMCMDFOLDER%\steamcmd.exe"
)

set "DOWNLOAD_PATH=%STEAMCMDFOLDER%\steamapps\workshop\content\%APPID%"
set "MOVE_PATH=%MOVE_PATH%"

echo.
echo [APP] Jopseps Mod Downloader
echo ---------------------------------
echo AppID              : %APPID%
echo SteamCMD Path      : %STEAMCMD%
echo Download Path      : %DOWNLOAD_PATH%
echo Move After Download: %MOVE_AFTER_DOWNLOAD%
echo Move Path          : %MOVE_PATH%
echo ---------------------------------
echo.

:main
set "SCRIPT=%temp%\steamcmd_script.txt"
set "IDLIST=%temp%\jopseps_ids.txt"

if exist "%SCRIPT%" del "%SCRIPT%" >nul
echo login anonymous > "%SCRIPT%"

if exist "%IDLIST%" del "%IDLIST%" >nul
type nul > "%IDLIST%"

set "firstInput=1"

:loop
set /p "RAWINPUT=Enter Workshop ID or URL (q to quit): "
if /i "!RAWINPUT!"=="q" (
    if "!firstInput!"=="1" (
        echo Exiting program...
        exit /b
    ) else (
        goto run
    )
)
set "firstInput=0"
if "!RAWINPUT!"=="" goto loop

:: === ESCAPE '&' karakteri ===
set "RAWINPUT=!RAWINPUT:^&=^&!"

:: === Extract numeric ID ===
for /f "tokens=2 delims==&" %%X in ("!RAWINPUT!") do set "RAWINPUT=%%X"
for /f "tokens=1 delims=&? " %%Z in ("!RAWINPUT!") do set "ID=%%Z"

:: === Add to list ===
findstr /x /c:"!ID!" "%IDLIST%" >nul 2>&1
if errorlevel 1 (
    echo !ID!>>"%IDLIST%"
    echo workshop_download_item %APPID% !ID! validate >> "%SCRIPT%"
    echo [ADDED] !ID!
) else (
    echo [INFO] ID !ID! already queued.
)

goto loop

:run
echo quit >> "%SCRIPT%"
echo.
echo === Starting download... ===
"%STEAMCMD%" +runscript "%SCRIPT%"
echo.
echo === Download completed ===


:: === Move Mods ===
if "%MOVE_AFTER_DOWNLOAD%"=="1" (
    echo.
    echo === Moving downloaded mods... ===
    if not exist "%MOVE_PATH%" mkdir "%MOVE_PATH%" >nul 2>&1

    for /f "usebackq delims=" %%I in ("%IDLIST%") do (
        set "MODDIR=%DOWNLOAD_PATH%\%%I"
        if exist "!MODDIR!\" (
            echo Moving: %%I
            robocopy "!MODDIR!" "%MOVE_PATH%\%%I" /E /MOVE >nul
            if exist "%MOVE_PATH%\%%I\" (
                echo [OK] %%I moved successfully.
            ) else (
                echo [WARNING] %%I could not be moved.
            )
        ) else (
            echo [INFO] Folder for ID %%I not found: !MODDIR!
        )
    )
    echo === Downloaded mods have been moved ===
    echo Find the mods in %MOVE_PATH%
) else (
    echo Find the mods in %DOWNLOAD_PATH%
)

del "%SCRIPT%" >nul 2>&1
del "%IDLIST%" >nul 2>&1
echo.
goto main
    