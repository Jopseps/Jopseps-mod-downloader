# Claude Design Prompt — J Mod Downloader v2

> Paste everything below the line into Claude Design.

---

## What you're designing

**J Mod Downloader** is a desktop app for Linux and Windows. It downloads Steam Workshop mods for any game through SteamCMD, with no Steam client subscription needed. It will be built in **Python + PySide6**, with an embedded Chromium browser (QWebEngineView) showing real steamcommunity.com Workshop pages. The app injects its own **"+ Add"** buttons into those pages.

The layout takes after RimSort's Workshop downloader: a queue on the left, the embedded Workshop on the right, and a batch **Download** button at the bottom left. On top of that, this app adds:
- **Mod lists**: add a whole Steam Collection in one click, import and export list files, and save named lists.
- **Dependencies**: a mod's "Required items" are added automatically and shown as children of that mod.
- **Update tracking**: "Check updates" and "Update all" for mods that are already installed.
- **Per-game profiles**: each game gets its own AppID, mod folder and queue.
- **Login fallback**: downloads use an anonymous Steam login by default. When a game requires ownership, the app asks for a Steam login, including the Steam Guard step.

Users are PC gamers who mod heavily (RimWorld is the flagship case) and often queue more than 100 mods at a time. It's a utility tool, so it should be fast, clear and dense enough to scan, never cute.

## Deliverable

A **clickable HTML prototype** at **1440×900**, plus a view showing how the layout adapts at the **1100×700 minimum**. Include:
1. The prototype, with these flows wired up (see Flows).
2. A **design token sheet** covering colors, type scale, spacing, radii, borders and status colors. Output it as CSS variables and also as a JSON block, because I'll port it to Qt QSS by hand.
3. A **component sheet** covering the queue row in every status, buttons (primary, secondary, ghost, danger), tabs, dropdown, input and paste box, badge and pill, progress bar, tree group header, dialog shell, and the injected "+ Add" / "✓ In list" pill.

## Hard constraints (QSS portability)

- The design must be buildable in **Qt stylesheets**: flat fills, 1px borders, border-radius and simple linear gradients.
- **No** backdrop blur, glassmorphism, layered or complex shadows (one subtle shadow on dialogs at most), CSS-grid-only tricks or fancy animation.
- Motion is limited to progress bars, a spinner and hover/pressed color changes.
- Everything has to read as a standard desktop widget: tree view, tabs, splitter, combo box, line edit, push button, dialog.
- Every hover, pressed, focus and disabled state must be defined.

## Visual direction

- **Dark theme in Steam's native blue-grays**, so the embedded Workshop pages blend with the app chrome:
  - bg `#171a21` · panel `#1b2838` · raised `#2a475e` · text `#c7d5e0` · Steam blue `#66c0f4`
- **Accent / brand color: you pick.** Constraints:
  - It must stand out against the Steam blue-grays and against Steam's own buttons, so users can tell our controls apart from Steam's.
  - It needs WCAG AA contrast for text on buttons.
  - It must not clash with or be confused for any status color below.
- **Status colors** (must be clearly distinct from each other and from the accent):
  - queued (neutral) · resolving (muted/animated) · downloading (progress) · retrying · done/synced · failed · outdated · needs login
- **Type**: **Inter** for the UI and **JetBrains Mono** for Workshop IDs, paths and the log.
- **Density**: comfortable. Queue rows are about 56px, with a 40px thumbnail, a title line and a sub-line for status, size and "required by X".
- **Branding**: the text wordmark "J Mod Downloader" in the top bar. No logo or icon yet.
- **Microcopy**: plain and terse. Examples: "Download 12", "Retrying 2/3", "Needs login", "Outdated", "Required by Trains of the Rim", "Add collection (179)".

## Main window layout

```
┌─ J Mod Downloader  [Profile ▾ RimWorld]  ................  [⚙] ─┐
│ [Queue | Installed] tabs    │ ← → ⌂ ⟳  steamcommunity.com/...   │
│ List: Current ▾             │                                    │
│ ┌ paste IDs / URLs ──────┐  │                                    │
│ └────────────────────────┘  │     embedded Steam Workshop        │
│ queue tree                  │     (with injected + Add pills)    │
│   ▾ Collection: X (179)     │                                    │
│      ☑ [img] Mod A     ×    │                                    │
│      ☑ [img] Harmony   ×    │                                    │
│         required by Mod A   │                                    │
│ ─────────────────────────── │                                    │
│ [ Download (12) ]  3 failed │                                    │
└─ ▸ SteamCMD log (collapsed dock) ────────────────────────────────┘
```

**Left panel** (resizable splitter, about 360px by default, about 300px at the minimum window size):
- **Tabs**: Queue | Installed
- **List dropdown**: "List: Current ▾" with the menu items Save as… / Load / Import… / Export… / Delete
- **Paste box**: a multi-line field for pasting one or many IDs or URLs; they're added the moment they're pasted
- **Queue tree**:
  - A collection shows as an expandable group node with a count and a checkbox that checks all or none of its items.
  - Dependencies show as indented children tagged "required by X".
- **Each row**: checkbox (skip without removing) · thumbnail · title · sub-line (status, size, required-by) · × remove. There's a retry icon on failed rows and a progress bar inline on rows that are downloading.
- **Bottom-left footer**: the primary **Download (N)** button with a small summary ("3 failed · Retry failed").

**Installed tab**:
- Lists synced mods, each with its last-updated date and an **Outdated** badge where it applies.
- Footer: **Check updates** and **Update all (N)**.

**Right side**:
- A browser nav bar (back, forward, home, reload, read-only URL field) above the embedded Workshop.
- Home is the current profile's Workshop browse page.

**Top bar**:
- Wordmark · profile dropdown (game icon + name; a "New profile…" item at the bottom) · settings gear.

**Log dock**:
- Collapsed by default; when opened it shows raw SteamCMD output in monospace.

## Mock Workshop pages (inside the prototype)

Build simplified, believable Steam Workshop pages in Steam's own style. They are "Steam's content", so they should look slightly foreign to the app chrome. Show our injected pills on them:
1. **Browse grid**: mod tiles, each with a small **"+ Add"** pill overlay at the top right. Tiles already in the queue show **"✓ In list"** in a muted style; clicking that removes the mod.
2. **Mod detail page**: title, preview image and a "Required items" box. Put a large **"+ Add to list"** pill next to Steam's Subscribe button. Mark required items as "will be added automatically".
3. **Collection page**: header with a **"+ Add collection (N)"** pill, plus a per-item "+ Add" on each listed mod.

The injected pill uses the app's accent color so it clearly belongs to the app, not to Steam.

## Other screens

- **First-run onboarding** (a wizard of about 3 steps):
  1. **SteamCMD**: "Found at /usr/bin/steamcmd ✓", or "Not found → [Download SteamCMD automatically] / [Browse…]". Show progress while it installs, and a readable error state (for example, Linux missing 32-bit libs).
  2. **First profile**: game picker (see below), then the mod folder, then the sync mode.
  3. **Done**: lands in the main window with the Workshop loaded.
- **Profile / game picker dialog**:
  - Three ways to pick a game:
    - a search field that returns game results with a capsule image and name
    - a "Detected on this PC" list of installed Steam games
    - a field to paste an AppID or store URL
  - Then:
    - Mod folder path, with Browse… and a suggested default from the game handler.
    - Sync mode: **Copy (recommended)** or **Link** (symlink/junction, which saves disk space; warn that some games dislike links).
    - A read-only line: "Handler: RimWorld (imports .rml, saves, ModsConfig.xml)" or "Generic (.txt)".
- **Settings dialog**:
  - SteamCMD path, with auto-detect and re-install
  - Cache folder: app-managed by default, with an opt-in "Use existing SteamCMD folder"
  - Retries (default 3)
  - Saved Steam username (optional), with a note that the password is never stored
  - A "Clear thumbnail cache" button
- **Steam login dialog** (appears mid-download when a game needs ownership). States:
  1. Username + password
  2. Steam Guard code entry (5 characters)
  3. "Approve on Steam Mobile app…" waiting state with a spinner
  4. Error: wrong password or code
  5. Success

## Main window states to show

1. **Queue with a collection and dependencies**:
   - Expanded "Collection: RimWorld Essentials (179)" with a few items unchecked.
   - "Trains of the Rim" with auto-added children "Vehicle Framework" and "Harmony", tagged "required by Trains of the Rim".
   - Some rows still "Resolving…" (metadata loading, gray thumbnail skeleton).
2. **Downloading**: mixed statuses: queued, downloading at 45% with a bar, done ✓, retrying 2/3, failed with retry, needs login. The Download button turns into "Downloading 4/12… [Cancel]".
3. **Updates available**: the Installed tab with 40 or more mods, 5 of them badged Outdated, and "Update all (5)" active.

## Flows to wire in the prototype

1. Click "+ Add" on a grid tile → the row appears in the queue as "Resolving…", then fills in → the tile pill flips to "✓ In list".
2. On a detail page, "+ Add to list" → the mod and its required items appear as a group.
3. On a collection page, "+ Add collection (N)" → a group node appears, expanded.
4. Paste 3 URLs into the paste box → 3 rows appear.
5. Click Download → rows animate through their statuses → one row fails → it retries → it's marked done.
6. One row reaches "Needs login" → the login dialog opens → Steam Guard step → success → the row continues.
7. Switch to the Installed tab → Check updates → outdated badges appear → Update all.
8. Profile dropdown → New profile… → the game picker dialog.
9. List dropdown → Export… → a small toast: "Exported 12 mods to rimworld_list.txt".

## Sample data (use real names/IDs)

- Harmony `2009463077` · Vehicle Framework `3014915404` · Trains of the Rim `3530446424` (requires VF + Harmony) · Vanilla Expanded Framework `2023507013`
- Collection `3533988679`: about 179 items; invent plausible RimWorld mod names for the rest
- Profiles: RimWorld (294100) · Stellaris (281990) · Garry's Mod (4000)
- SteamCMD log lines, for example:
  - `Success. Downloaded item 2009463077 to "…/steamapps/workshop/content/294100/2009463077" (2154312 bytes)`
  - `ERROR! Download item 3014915404 failed (Timeout).`

## Don'ts

- Don't restyle the Workshop mock to match the app. It is Steam's content.
- No light mode, no mobile layout, and no marketing or landing page.
- No emoji in the UI chrome. Use simple line icons (Lucide-style) that can be exported as SVG.
