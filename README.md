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
- **Per-game profiles**: each game has its own mod folder, queue and lists. Find games by name, from the ones installed on your PC, or paste an AppID, a store link or any Workshop link.
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

Most games work as-is. For games with their own mod list format, add a small handler in `jmd/handlers/` by subclassing `jmd.handlers.base.GameHandler` (for frozen builds, also add the module to `hiddenimports` in `jmd.spec`). RimWorld's handler is the example.

## Building

Only Python 3 is needed. The scripts create a `.venv`, install the dependencies there, run the tests and build.

- **Linux:** `./build.sh` → `dist/JModDownloader/JModDownloader` + `dist/JModDownloader-Linux.tar.gz`
- **Windows:** double-click `build.bat` → `dist\JModDownloader\JModDownloader.exe` + `dist\JModDownloader-Windows.zip`

A local build bundles your PC's libraries, so it runs on that PC (and on newer systems). Tagging `v*` builds the Windows and Linux releases through GitHub Actions on older runners, so they run on more systems.

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
- Per-game profiles, game search and installed-game detection. Profiles can also be made from an AppID, a store link or a Workshop link.
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

---

## License

**J Mod Downloader**: Copyright (C) 2025-2026 Yusuf Mert Turan

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with this program (see [LICENSE](LICENSE)). If not, see <https://www.gnu.org/licenses/>.

Contact: [jopsepsmert@gmail.com](mailto:jopsepsmert@gmail.com)

### Third-party
- [Inter](https://rsms.me/inter/) and [JetBrains Mono](https://www.jetbrains.com/lp/mono/) fonts: SIL Open Font License 1.1 (`jmd/assets/fonts/OFL-*.txt`).
- Icon paths from [Lucide](https://lucide.dev) (ISC) and Feather (MIT): `jmd/assets/LICENSE-Lucide.txt`.
