# J Mod Downloader

Download Steam Workshop mods for any game, without subscribing in Steam. Browse the Workshop inside the app, click **+ Add** on mods or whole collections, then download everything in one batch with SteamCMD.

Works on **Windows** and **Linux**.

![J Mod Downloader](images/screenshot.png)

---

**0.** Download **SteamCMD** from https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip 

**1.** Extract the zip file then run `steamcmd.exe`, once it completes downloading itself you can close it 

## Configuration

Settings are stored in `config.ini`. You can fill them in before launching, or leave them blank — the app will prompt you to enter them at startup.

```ini
APPID=294100
STEAMCMDFOLDER=C:\Users\YourName\Desktop\steamcmd
MOVE_AFTER_DOWNLOAD=0
MOVE_PATH=C:\Users\YourName\Desktop\Mods
```

## Features

- **Built-in Workshop browser**: every mod tile, mod page and collection gets a **+ Add** button. Click it again (**✓ In list**) to remove.
- **Collections in one click**: a collection lands in your queue as a group. Untick anything you don't want.
- **Dependencies are added for you**: a mod's *Required items* are queued automatically and shown under it.
- **Batch download** with SteamCMD, with automatic retries for timeouts.
- **Update tracking**: the *Installed* tab shows which mods have updates. *Update all* only re-downloads what changed.
- **Mod lists**: save named lists, import lists (`.txt`, plus RimWorld `.rml`, saves and `ModsConfig.xml`), export to `.txt`.
- **Per-game profiles**: each game has its own mod folder, queue and lists. Find games by name, AppID, or from the ones installed on your PC.
- **Copy or link**: mods are copied into your game's mod folder, or linked (symlink / junction) to save disk space.
- **No setup hunt**: SteamCMD is found automatically, or installed for you on first run.

---

## Download

Grab the latest build from [Releases](https://github.com/Jopseps/Jopseps-mod-downloader/releases):

- **Windows**: `JModDownloader-Windows.zip`. Extract it, run `JModDownloader.exe`.
- **Linux**: `JModDownloader-Linux.tar.gz`. Extract it, run `JModDownloader/JModDownloader`.

### Run from source

Needs Python 3.11+.

```bash
pip install -r requirements.txt
python -m jmd
```

---

## How to use

1. **First run**: the setup finds SteamCMD (or downloads it), then asks which game you mod and where its mod folder is.
2. **Add mods**: browse the Workshop on the right and click **+ Add**. You can also paste Workshop IDs or links into the box on the left (many at once is fine).
3. **Download**: press **Download** at the bottom left. Progress shows on each row, and the SteamCMD log is at the bottom.
4. **Keep them fresh**: open the **Installed** tab, press **Check updates**, then **Update all**.

### Games that need you to own them

Most games let SteamCMD download Workshop items anonymously. Some (Wallpaper Engine, for example) only allow accounts that own the game. Those rows show **Needs login**: click **Log in**, enter your Steam account and your Steam Guard code if asked.

Your password is handed to SteamCMD for that one run and never saved. SteamCMD remembers the session afterwards.

### Where files go

SteamCMD downloads into the app's own cache (`~/.local/share/jmod/cache` on Linux, `%LOCALAPPDATA%\jmod\cache` on Windows), and mods are then copied or linked into the mod folder of your profile, one folder per Workshop ID. Keeping the cache means updates only fetch what changed.

---

## Adding support for a game

Most games work as-is. For games with their own mod list format, add a small handler in `jmd/handlers/`: see [ARCHITECTURE.md](ARCHITECTURE.md#handlers). RimWorld's handler is the example.

## Building

```bash
pip install -r requirements.txt pyinstaller
pyinstaller jmd.spec          # → dist/JModDownloader/
python -m unittest tests.test_core
```

Tagging `v*` builds Windows and Linux releases through GitHub Actions.

---

## Confirmed Steam Workshops That Downloadable
**NOTE:** Theoretically, it can download from any workshop. However, for games that have separate workshop IDs for singleplayer and multiplayer (or use a dedicated server, like Stonehearth), it might not be able to download from them.

- **RimWorld**  `294100`
- **Project Zomboid** `108600`
- **Half Life 2** `220`

---

## Changelog

### Version 2.0 (unreleased)
- New desktop app (PySide6) replaces the terminal scripts.
- Embedded Workshop browser with **+ Add** buttons on mods and collections.
- Collections, automatic dependencies, named lists, import/export.
- Update tracking and *Update all*.
- Per-game profiles, game search and installed-game detection.
- SteamCMD auto-install, retries, login fallback for ownership-gated games.

### Version 1.1 (2026-02-24)
- Added smart config validation.
- Added save to config option and entered values can be saved to `config.ini` for future sessions
- Full URL pasting support (the `&` character in URLs no longer causes issues on Windows)
- `Q` now responds instantly without needing to enter.

### Version 1.0 (2025-10-08)
- Initial release

---

### Special Thanks to
- [Swjeer](https://github.com/Swjeer) for testing the Windows version.
