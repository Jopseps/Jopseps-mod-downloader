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
    set "line=%%A"
    if not "!line:~0,1!"==";" if not "!line:~0,1!"=="#" (
        set "%%A=%%B"
    )
)

:: === VALIDATE CONFIG ===
set "CHANGED="

:: --- APPID ---
:validate_appid
if not defined APPID goto prompt_appid
echo !APPID!| findstr /r "^[0-9][0-9]*$" >nul 2>&1
if errorlevel 1 goto prompt_appid
goto appid_ok

:prompt_appid
echo [CONFIG] APPID not found or invalid in config.ini.
set /p "APPID=Enter a valid Steam App ID: "
echo !APPID!| findstr /r "^[0-9][0-9]*$" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] App ID must be a number. Please try again.
    set "APPID="
    goto prompt_appid
)
set "CHANGED=!CHANGED!APPID,"
:appid_ok

:: --- STEAMCMDFOLDER ---
:validate_steamcmd
if not defined STEAMCMDFOLDER goto prompt_steamcmd
if not exist "!STEAMCMDFOLDER!\*" goto prompt_steamcmd
goto steamcmd_ok

:prompt_steamcmd
echo [CONFIG] STEAMCMDFOLDER not found or invalid in config.ini.
set /p "STEAMCMDFOLDER=Enter the path to your steamcmd folder: "
if not exist "!STEAMCMDFOLDER!\*" (
    echo [ERROR] Directory not found: !STEAMCMDFOLDER!
    set "STEAMCMDFOLDER="
    goto prompt_steamcmd
)
set "CHANGED=!CHANGED!STEAMCMDFOLDER,"
:steamcmd_ok

:: --- MOVE_PATH (only when MOVE_AFTER_DOWNLOAD=1) ---
if not "%MOVE_AFTER_DOWNLOAD%"=="1" goto movepath_ok

:validate_movepath
if not defined MOVE_PATH goto prompt_movepath
if not exist "!MOVE_PATH!\*" goto prompt_movepath
goto movepath_ok

:prompt_movepath
echo [CONFIG] MOVE_PATH not found or invalid in config.ini.
set /p "MOVE_PATH=Enter the destination path for mods: "
if not exist "!MOVE_PATH!\*" (
    echo [ERROR] Directory not found: !MOVE_PATH!
    set "MOVE_PATH="
    goto prompt_movepath
)
set "CHANGED=!CHANGED!MOVE_PATH,"
:movepath_ok

:: === ASK TO SAVE ===
if not defined CHANGED goto skip_save

echo.
echo [CONFIG] The following settings were entered:
echo !CHANGED! | findstr /c:"APPID" >nul && echo   APPID = !APPID!
echo !CHANGED! | findstr /c:"STEAMCMDFOLDER" >nul && echo   STEAMCMDFOLDER = !STEAMCMDFOLDER!
echo !CHANGED! | findstr /c:"MOVE_PATH" >nul && echo   MOVE_PATH = !MOVE_PATH!

set /p "SAVECHOICE=Save these settings to config.ini? (y/n): "
if /i "!SAVECHOICE!"=="y" (
    call :save_config
    echo [CONFIG] Settings saved to config.ini.
) else (
    echo [CONFIG] Settings not saved. Using for this session only.
)
:skip_save

:: === FIX PATH ===
if "%STEAMCMDFOLDER:~-1%"=="\" (
    set "STEAMCMD=%STEAMCMDFOLDER%steamcmd.exe"
) else (
    set "STEAMCMD=%STEAMCMDFOLDER%\steamcmd.exe"
)

set "DOWNLOAD_PATH=%STEAMCMDFOLDER%\steamapps\workshop\content\%APPID%"

:main
echo.
echo [APP] Jopseps Mod Downloader (Windows)
echo ---------------------------------
echo AppID              : %APPID%
echo SteamCMD Path      : %STEAMCMD%
echo Download Path      : %DOWNLOAD_PATH%
echo Move After Download: %MOVE_AFTER_DOWNLOAD%
echo Move Path          : %MOVE_PATH%
echo ---------------------------------
echo.

set "SCRIPT=%temp%\steamcmd_script.txt"
set "IDLIST=%temp%\jopseps_ids.txt"

if exist "%SCRIPT%" del "%SCRIPT%" >nul
echo login anonymous > "%SCRIPT%"

if exist "%IDLIST%" del "%IDLIST%" >nul
type nul > "%IDLIST%"

set "firstInput=1"

:loop
set "RAWINPUT="
set /p "RAWINPUT=Enter Workshop ID or URL (q to quit): "
if /i "!RAWINPUT!"=="q" (
    if "!firstInput!"=="1" (
        echo Exiting program...
        exit /b
    ) else (
        goto run
    )
)
if "!RAWINPUT!"=="" goto loop
set "firstInput=0"

:: === Extract numeric ID ===
:: Try to extract id= parameter from URL
echo !RAWINPUT! | findstr /i "id=" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=2 delims==&" %%X in ("!RAWINPUT!") do set "RAWINPUT=%%X"
    for /f "tokens=1 delims=&? " %%Z in ("!RAWINPUT!") do set "ID=%%Z"
    goto check_id
)

:: Otherwise check if the input is a plain numeric ID
echo !RAWINPUT! | findstr /r "^[0-9][0-9]*$" >nul 2>&1
if not errorlevel 1 (
    set "ID=!RAWINPUT!"
    goto check_id
)

echo [ERROR] Could not detect a valid Workshop ID. Please try again.
goto loop

:check_id
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

:: === SAVE CONFIG FUNCTION ===
:save_config
:: Create a temp file with updated config
set "TMPCONFIG=%temp%\config_tmp.ini"
if exist "%TMPCONFIG%" del "%TMPCONFIG%" >nul

set "SAVED_APPID=0"
set "SAVED_STEAMCMDFOLDER=0"
set "SAVED_MOVE_PATH=0"

for /f "usebackq delims=" %%L in ("%CONFIG%") do (
    set "cfgline=%%L"

    :: Check if this line is a key=value for a changed key
    set "replaced=0"

    echo !CHANGED! | findstr /c:"APPID" >nul
    if not errorlevel 1 if "!SAVED_APPID!"=="0" (
        echo !cfgline! | findstr /b /c:"APPID=" >nul 2>&1
        if not errorlevel 1 (
            echo APPID=!APPID!>>"%TMPCONFIG%"
            set "SAVED_APPID=1"
            set "replaced=1"
        )
    )

    if "!replaced!"=="0" (
        echo !CHANGED! | findstr /c:"STEAMCMDFOLDER" >nul
        if not errorlevel 1 if "!SAVED_STEAMCMDFOLDER!"=="0" (
            echo !cfgline! | findstr /b /c:"STEAMCMDFOLDER=" >nul 2>&1
            if not errorlevel 1 (
                echo STEAMCMDFOLDER=!STEAMCMDFOLDER!>>"%TMPCONFIG%"
                set "SAVED_STEAMCMDFOLDER=1"
                set "replaced=1"
            )
        )
    )

    if "!replaced!"=="0" (
        echo !CHANGED! | findstr /c:"MOVE_PATH" >nul
        if not errorlevel 1 if "!SAVED_MOVE_PATH!"=="0" (
            echo !cfgline! | findstr /b /c:"MOVE_PATH=" >nul 2>&1
            if not errorlevel 1 (
                echo MOVE_PATH=!MOVE_PATH!>>"%TMPCONFIG%"
                set "SAVED_MOVE_PATH=1"
                set "replaced=1"
            )
        )
    )

    if "!replaced!"=="0" (
        echo !cfgline!>>"%TMPCONFIG%"
    )
)

:: Append any keys that weren't found in the original file
echo !CHANGED! | findstr /c:"APPID" >nul
if not errorlevel 1 if "!SAVED_APPID!"=="0" echo APPID=!APPID!>>"%TMPCONFIG%"

echo !CHANGED! | findstr /c:"STEAMCMDFOLDER" >nul
if not errorlevel 1 if "!SAVED_STEAMCMDFOLDER!"=="0" echo STEAMCMDFOLDER=!STEAMCMDFOLDER!>>"%TMPCONFIG%"

echo !CHANGED! | findstr /c:"MOVE_PATH" >nul
if not errorlevel 1 if "!SAVED_MOVE_PATH!"=="0" echo MOVE_PATH=!MOVE_PATH!>>"%TMPCONFIG%"

:: Replace original config with updated one
copy /y "%TMPCONFIG%" "%CONFIG%" >nul
del "%TMPCONFIG%" >nul 2>&1
goto :eof