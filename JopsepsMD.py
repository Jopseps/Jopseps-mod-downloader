import os
import sys
import re
import shutil
import tempfile
import subprocess
import termios
import tty

def readline_with_instant_quit(prompt):
    """Read a line of input. Pressing 'q' as the first key quits the program instantly."""
    sys.stdout.write(prompt)
    sys.stdout.flush()

    fd = sys.stdin.fileno()

    # Fallback if stdin is not a TTY (e.g. piped input)
    if not os.isatty(fd):
        line = sys.stdin.readline().rstrip('\n')
        if line.lower() == 'q':
            sys.exit(0)
        return line

    old_settings = termios.tcgetattr(fd)
    chars = []

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ('\r', '\n'):
                sys.stdout.write('\r\n')
                sys.stdout.flush()
                break
            elif ch in ('\x7f', '\x08'):  # Backspace
                if chars:
                    chars.pop()
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif ch == '\x03':  # Ctrl+C
                sys.stdout.write('\r\n')
                sys.stdout.flush()
                raise KeyboardInterrupt
            else:
                if not chars and ch.lower() == 'q':
                    sys.stdout.write('q\r\n')
                    sys.stdout.flush()
                    return 'q'
                chars.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return ''.join(chars)


def load_config(config_path):
    if not os.path.exists(config_path):
        print(f"ERROR: {config_path} not found!")
        input("Press Enter to exit...")
        sys.exit(1)

    config = {}
    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines or comments
            if not line or line.startswith((';', '#', '::')):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config

def save_config(config_path, updates):
    """Rewrite config.ini in-place, updating changed keys while preserving comments."""
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith((';', '#', '::')) and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # Append any keys that weren't already in the file
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    with open(config_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

def validate_config(config, config_path):
    """Validate config values and prompt user for corrections if invalid."""
    changed = {}  # Track which values were entered by the user

    # --- APPID ---
    appid = config.get('APPID', '')
    while not appid or not appid.isdigit():
        print("[CONFIG] APPID not found or invalid in config.ini.")
        appid = input("Enter a valid Steam App ID: ").strip()
        if not appid.isdigit():
            print("[ERROR] App ID must be a number. Please try again.")
            appid = ''
    if appid != config.get('APPID', ''):
        changed['APPID'] = appid
    config['APPID'] = appid

    # --- STEAMCMDFOLDER ---
    steamcmd_folder = config.get('STEAMCMDFOLDER', '')
    while not steamcmd_folder or not os.path.isdir(steamcmd_folder):
        print("[CONFIG] STEAMCMDFOLDER not found or invalid in config.ini.")
        steamcmd_folder = input("Enter the path to your steamcmd folder: ").strip()
        if not os.path.isdir(steamcmd_folder):
            print(f"[ERROR] Directory not found: {steamcmd_folder}")
            steamcmd_folder = ''
    if steamcmd_folder != config.get('STEAMCMDFOLDER', ''):
        changed['STEAMCMDFOLDER'] = steamcmd_folder
    config['STEAMCMDFOLDER'] = steamcmd_folder

    # --- MOVE_PATH (only when MOVE_AFTER_DOWNLOAD=1) ---
    if config.get('MOVE_AFTER_DOWNLOAD', '0') == '1':
        move_path = config.get('MOVE_PATH', '')
        while not move_path or not os.path.isdir(move_path):
            print("[CONFIG] MOVE_PATH not found or invalid in config.ini.")
            move_path = input("Enter the destination path for mods: ").strip()
            if not os.path.isdir(move_path):
                print(f"[ERROR] Directory not found: {move_path}")
                move_path = ''
        if move_path != config.get('MOVE_PATH', ''):
            changed['MOVE_PATH'] = move_path
        config['MOVE_PATH'] = move_path

    # --- Ask to save if anything changed ---
    if changed:
        print("\n[CONFIG] The following settings were entered:")
        for key, value in changed.items():
            print(f"  {key} = {value}")
        save = input("Save these settings to config.ini? (y/n): ").strip().lower()
        if save == 'y':
            save_config(config_path, changed)
            print("[CONFIG] Settings saved to config.ini.")
        else:
            print("[CONFIG] Settings not saved. Using for this session only.")

    return config

def extract_mod_id(raw_input):
    match = re.search(r'id=(\d+)', raw_input)
    if match:
        return match.group(1)

    # If no 'id=' is found, check if the input itself is just a numeric ID
    match = re.search(r'^(\d+)$', raw_input.strip())
    if match:
        return match.group(1)

    return None

def main():
    # === CONFIG READING ===
    config_path = 'config.ini'
    config = load_config(config_path)
    config = validate_config(config, config_path)

    appid = config.get('APPID', '')
    steamcmd_folder = config.get('STEAMCMDFOLDER', '')
    move_after_download = config.get('MOVE_AFTER_DOWNLOAD', '0')
    move_path = config.get('MOVE_PATH', '')

    # === FIX PATH ===
    steamcmd = os.path.join(steamcmd_folder, 'steamcmd')
    download_path = os.path.join(os.path.expanduser("~"), ".local/share/Steam/", 'steamapps', 'workshop', 'content', appid)

    while True:
        print("\n[APP] Jopseps Mod Downloader (Linux)")
        print("-" * 33)
        print(f"AppID               : {appid}")
        print(f"SteamCMD Path       : {steamcmd}")
        print(f"Download Path       : {download_path}")
        print(f"Move After Download : {move_after_download}")
        print(f"Move Path           : {move_path}")
        print("-" * 33)
        print()

        ids_to_download = set()

        # === INPUT LOOP ===
        while True:
            raw_input = readline_with_instant_quit("Enter Workshop ID or URL (q to quit/start download): ").strip()

            if raw_input.lower() == 'q':
                if ids_to_download:
                    break  # Start download
                print("Exiting program...")
                sys.exit(0)

            if not raw_input:
                continue

            # Extract numeric ID
            mod_id = extract_mod_id(raw_input)

            if mod_id:
                if mod_id not in ids_to_download:
                    ids_to_download.add(mod_id)
                    print(f"[ADDED] {mod_id}")
                else:
                    print(f"[INFO] ID {mod_id} already queued.")
            else:
                print("[ERROR] Could not detect a valid Workshop ID. Please try again.")

        if not ids_to_download:
            continue

        # === CREATE STEAMCMD SCRIPT ===
        print("\n=== Starting download... ===")

        # Using a temp file
        fd, script_path = tempfile.mkstemp(suffix=".txt", text=True)
        with os.fdopen(fd, 'w') as f:
            f.write("login anonymous\n")
            for mod_id in ids_to_download:
                f.write(f"workshop_download_item {appid} {mod_id} validate\n")
            f.write("quit\n")

        # === RUN STEAMCMD ===
        subprocess.run([steamcmd, "+runscript", script_path])

        # Clean up temp file
        os.remove(script_path)

        print("\n=== Download completed ===")

        # === MOVE MODS ===
        if move_after_download == "1":
            print("\n=== Moving downloaded mods... ===")
            os.makedirs(move_path, exist_ok=True)

            for mod_id in ids_to_download:
                src_dir = os.path.join(download_path, mod_id)
                dest_dir = os.path.join(move_path, mod_id)

                if os.path.exists(src_dir):
                    print(f"Moving: {mod_id}")
                    try:
                        # robocopy 
                        shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)
                        # Remove the original folder
                        shutil.rmtree(src_dir)
                        print(f"[OK] {mod_id} moved successfully.")
                    except Exception as e:
                        print(f"[WARNING] {mod_id} could not be moved. Error: {e}")
                else:
                    print(f"[INFO] Folder for ID {mod_id} not found: {src_dir}")

            print("=== Downloaded mods have been moved ===")
            print(f"Find the mods in {move_path}")
        else:
            print(f"Find the mods in {download_path}")

if __name__ == "__main__":
    main()
