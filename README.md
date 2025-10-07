# Jopseps Mod Downloader
is a basic mod downloader for any Steam game that uses terminal / cmd to download from Steam workshop server

## Setup

0. Download SteamCMD from https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip 

1. Extract the zip file then run `steamcmd.exe`, once it completes downloading itself you can close it 

## Configuration
*Example*:

    APPID=294100
    STEAMCMDFOLDER=C:\Users\Jopseps\Desktop\steamcmd
    MOVE_AFTER_DOWNLOAD=0
    MOVE_PATH=C:\Users\Jopseps\Desktop\Mods

| Key                     | Description                                                                                                                                                                       |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **APPID**               | The Steam App ID of the game you want mods for (e.g. RimWorld = `294100`). You can find it in the game’s Steam store URL: `https://store.steampowered.com/app/294100/` → `294100` |
| **STEAMCMDFOLDER**      | The folder where you installed **SteamCMD** (`steamcmd.exe` should be inside this folder).                                                                                        |
| **MOVE_AFTER_DOWNLOAD** | Set to `1` if you want the downloader to automatically move mods to another folder after downloading. Set to `0` to keep them where SteamCMD saves them.                          |
| **MOVE_PATH**           | The folder where mods should be moved (only used if `MOVE_AFTER_DOWNLOAD=1`). Example: `C:\Games\RimWorld\Mods`                                                                   |


## How to use it



**0.** Adjust the config.ini file to your needs, you must have to change the paths in the config and the game id if needed, the default config is for Rimworld

**1.** First open **JopsepsMD.bat** to run it.

**2.** Enter the desired **Steam Workshop id** of the mod/item you want *( You can find it on the **mod's Steam page link** such as 3530446424 from `https://steamcommunity.com/sharedfiles/filedetails/?id=3530446424&searchtext=` after the `?id=` part. )* then press **"Enter/Return"**.


**3.** After entering **single or multiple mod id's** press **"Q"** to finish the entry process and download the files.

**4.** Right after downloading, **you will be informed where your files are located**, you can move the mods manually or configure the auto move after download in `config.ini` file.


