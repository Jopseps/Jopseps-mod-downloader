# Architecture

J Mod Downloader is a PySide6 desktop app. `jmd/core` has no Qt dependency and is unit-tested on its own; `jmd/ui` wraps it.

```
jmd/
  __main__.py        python -m jmd
  app.py             QApplication, fonts, theme, JMD_SMOKE self-check
  paths.py           data/cache/thumbs dirs, bundled assets (works frozen)
  core/              no Qt
    ids.py           Workshop/App ID parsing from IDs and URLs
    models.py        ModItem, Group, Profile, Settings, InstalledRecord, QueueState
    store.py         JSON persistence (atomic writes)
    steam_api.py     keyless Steam Web API + page scrape for Required items, throttled
    resolver.py      ids → collections (expanded) / items; details; dependencies
    steamcmd.py      locate, bootstrap, runscript, output parser, process runner
    downloader.py    batch passes, retry, login classification, progress polling, sync hook
    sync.py          mirror copy / symlink / junction into the mod folder
    library.py       Steam libraries + installed games (VDF parser)
  handlers/          per-game list formats (auto-discovered)
  ui/
    tokens.py        design tokens → QSS (single source)
    controller.py    app state + background work; UI thread owns all mutation
    queue_model.py   flat list models for queue / installed
    delegates.py     painted rows + hit-testing (checkbox, retry, Log in, ×, chevron)
    queue_panel.py   left panel: tabs, list menu, paste box, footers
    browser_pane.py  QWebEngineView + nav bar, installs the injector
    web_bridge.py    QWebChannel object the page script talks to
    log_panel.py     SteamCMD log dock
    main_window.py   top bar, splitter, toast, dialog launchers
    dialogs/         onboarding, game picker, settings, Steam login
  assets/
    inject.js        "+ Add" pills for Workshop pages (all selectors in SELECTORS)
    fonts/           Inter, JetBrains Mono (OFL)
```

## Data

All state is JSON under the data dir (`~/.local/share/jmod`, `%LOCALAPPDATA%\jmod`, or `JMD_DATA_DIR`):

```
settings.json                 SteamCMD path, cache mode, retries, username, current profile
profiles.json                 [{id, name, app_id, mod_dir, sync_mode, handler, capsule_url}]
profiles/<id>/queue.json      queue nodes (items with dependency children, collection groups)
profiles/<id>/lists/*.json    named lists
profiles/<id>/installed.json  {workshop id: {title, time_updated, remote_updated, synced_at, …}}
cache/                        SteamCMD force_install_dir (workshop cache = source of truth)
steamcmd/                     auto-installed SteamCMD
thumbs/  web/  web-cache/     thumbnails, embedded browser profile
```

## Download flow

1. `QueueState.pending()` → `Downloader(items)` on a worker thread.
2. Runscript: `force_install_dir <cache>` → `login anonymous` (or `login <user> [pass] [code]`) → `workshop_download_item <app> <id>`… → `quit`. The script file is 0600 and deleted afterwards.
3. `OutputParser` reads SteamCMD's stdout live (it arrives unbuffered over a pipe). ANSI resets count as line breaks, because SteamCMD often ends messages without `\n`. Echoed `login` lines are redacted.
4. Per item:
   - `Success. Downloaded item <id> to "<path>" (<n> bytes)` → sync into the mod folder → **done**, recorded in `installed.json`.
   - `ERROR! Download item <id> failed (<reason>)`:
     - `Timeout` and other transient reasons → retried in a fresh pass, up to *Retries*.
     - `File Not Found` → **failed**.
     - `Failure` while anonymous → **needs login** (ownership-gated games answer this within a second).
5. Progress: SteamCMD prints no percentage, so the size of `downloads/<app>/<id>` is polled against the API `file_size`.
6. Cancel kills the whole process group. `steamcmd.sh` forks the real binary, which would otherwise keep the pipe open.

## Steam endpoints (no API key)

| Need | Endpoint |
|---|---|
| Titles, sizes, `time_updated`, app | `POST ISteamRemoteStorage/GetPublishedFileDetails/v1` (batched 100) |
| Collection children | `POST ISteamRemoteStorage/GetCollectionDetails/v1` (`filetype 2` = nested, recursed) |
| Required items | item page, `#RequiredItems` links (not in the keyless API); max 4 at a time, spaced out |
| Game search | `store.steampowered.com/api/storesearch` |
| Game by AppID | `store.steampowered.com/api/appdetails` (the answer can be keyed by another id) |

## Workshop injection

`browser_pane` inserts `qwebchannel.js` + `assets/inject.js` as a `QWebEngineScript` in the **ApplicationWorld**. The page's own scripts can't see the bridge. The script:

- adds pills to image links pointing at `filedetails/?id=` (grids and React browse pages, whose class names are hashed), to `#SubscribeItemBtn` on mod pages, and to `.subscribeCollection` and each `.collectionItem` on collection pages;
- tags Required items with "Will be added automatically";
- calls `bridge.add(id)` / `bridge.remove(id)` and repaints from `bridge.queuedChanged(ids)`;
- re-scans on DOM mutations (Steam's browse pages render client-side).

When Steam changes its markup, `SELECTORS` at the top of `inject.js` is the one place to fix.

## Handlers

Subclass `jmd.handlers.base.GameHandler` in a new module under `jmd/handlers/`. The registry imports every module in the package. For frozen builds, also add the module to `hiddenimports` in `jmd.spec`.

```python
class MyGameHandler(GameHandler):
    key = "mygame"
    name = "My Game"
    summary = "imports .modlist"
    app_ids = (123456,)
    import_filters = [("My Game list", "*.modlist")]

    def import_list(self, path): ...          # → [workshop ids]
    def export_list(self, ids, path): ...
    def default_mod_dir(self, game_dir=""): ...
    def post_sync(self, mod_dir, mod_id): ... # e.g. write a descriptor file
```

## Design

The UI follows the Claude Design project (dark Steam blue-grays, rose accent `#f0609e`, Inter / JetBrains Mono). Colors, status colors and sizes live only in `ui/tokens.py`. The stylesheet is generated from those tokens, and the delegates paint with the same dict.

## Testing

- `python -m unittest tests.test_core`: ids, queue, parser (recorded real SteamCMD output), sync, VDF, Required-items scrape, store, RimWorld import.
- `JMD_SMOKE=3000 python -m jmd`: starts, prints `SMOKE ok handlers=… web=… fonts=…`, quits (also written to `smoke.txt`); CI runs it on the frozen build.
- Screenshots without a display: `QT_QPA_PLATFORM=offscreen`, plus `QTWEBENGINE_CHROMIUM_FLAGS=--disable-gpu` for the web view.

## Known gaps

- The Steam login prompt strings (password, Steam Guard, mobile approval) haven't been checked against a real account.
- Windows behaviour (SteamCMD output, junctions) is covered by code paths but not yet tested on a machine.
