# Jopseps Mod Downloader

A lightweight mod downloader for any Steam game. Uses SteamCMD under the hood — no login required, downloads directly from the Steam Workshop server.

- **Windows** → `JopsepsMD.bat`
- **Linux** → `JopsepsMD.py`

---

## Requirements

### SteamCMD
Download and set up SteamCMD before using Mod Downloader.

1. Download SteamCMD:
   - **Windows**: https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip
   - **Linux**: `sudo apt install steamcmd` or download from the same link
2. Extract the zip and run `steamcmd.exe` (Windows) or `./steamcmd.sh` (Linux) once — it will download and set itself up, then you can close it.

### Python (Linux only)
Python 3 is required to run `JopsepsMD.py`. It comes pre-installed on most Linux distributions.

---

## Configuration

Settings are stored in `config.ini`. You can fill them in before launching, or leave them blank — the app will prompt you to enter them at startup.

```ini
APPID=294100
STEAMCMDFOLDER=C:\Users\YourName\Desktop\steamcmd
MOVE_AFTER_DOWNLOAD=0
MOVE_PATH=C:\Users\YourName\Desktop\Mods
```

| Key | Description |
| --- | --- |
| **APPID** | Steam App ID of the game you want mods for. Find it in the store URL: `store.steampowered.com/app/`**294100**`/RimWorld/`. RimWorld's ID is `294100`. |
| **STEAMCMDFOLDER** | Path to the folder where you installed SteamCMD (`steamcmd.exe` or `steamcmd` must be inside). |
| **MOVE_AFTER_DOWNLOAD** | `1` = automatically move downloaded mods to `MOVE_PATH` after downloading. `0` = leave them where SteamCMD saves them. |
| **MOVE_PATH** | Destination folder for mods when `MOVE_AFTER_DOWNLOAD=1`. Example: `C:\Games\RimWorld\Mods` or `/home/user/Games/RimWorld/Mods`. |

> **Tip:** If any required setting is missing or invalid, the app will ask you to enter it when it starts. You'll also be offered the option to save it to `config.ini` for future runs.

---

## How to Use

**1. Launch the app**

- Windows: double-click `JopsepsMD.bat`
- Linux: run `python3 JopsepsMD.py` in a terminal

**2. Enter mod IDs**

You can enter either a raw Workshop ID or a full Steam Workshop URL — both work:

```
Enter Workshop ID or URL (q to quit): 3530446424
Enter Workshop ID or URL (q to quit): https://steamcommunity.com/sharedfiles/filedetails/?id=3530446424
```

You can add as many mods as you like, one per line.

**3. Start the download**

Press `Q` and Enter when you're done adding mods. SteamCMD will download all queued mods.

**4. Find your mods**

After downloading, the app tells you exactly where the files are. If `MOVE_AFTER_DOWNLOAD=1`, mods are automatically moved to your `MOVE_PATH`.

---

## Finding a Mod's Workshop ID

Open the mod's Steam Workshop page. The ID is the number in the URL after `?id=`:

```
https://steamcommunity.com/sharedfiles/filedetails/?id=3530446424
                                                        ^^^^^^^^^^
                                                        This is the ID
```

---

## Finding a Game's App ID

Open the game's Steam store page. The ID is the number in the URL after `/app/`:

```
https://store.steampowered.com/app/294100/RimWorld/
                                   ^^^^^^
                                   This is the App ID
```

---

## Changelog

### Version 1.1 (2026-02-24)
- Added smart config validation at launch — missing or invalid settings are prompted interactively instead of failing silently
- Added save-to-config option — entered values can be saved to `config.ini` for future sessions
- Full URL pasting support (the `&` character in URLs no longer causes issues on Windows)
- Both `.bat` and `.py` now have the same features

### Version 1.0 (2025-10-08)
- Initial release