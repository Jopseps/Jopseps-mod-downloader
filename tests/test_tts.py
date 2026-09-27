# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import json
import os
import struct
import tempfile
import unittest

from jmd.core import models, mods, sync, tts
from jmd.handlers.base import GameContext, disabled_dir


def _bson(doc):
    """Tiny encoder for the types TTS saves use."""
    body = b""
    for key, val in (doc.items() if isinstance(doc, dict) else ((str(i), v) for i, v in enumerate(doc))):
        k = key.encode() + b"\x00"
        if isinstance(val, bool):
            body += b"\x08" + k + (b"\x01" if val else b"\x00")
        elif isinstance(val, int):
            body += b"\x10" + k + struct.pack("<i", val)
        elif isinstance(val, float):
            body += b"\x01" + k + struct.pack("<d", val)
        elif isinstance(val, str):
            s = val.encode() + b"\x00"
            body += b"\x02" + k + struct.pack("<i", len(s)) + s
        elif isinstance(val, bytes):
            body += b"\x05" + k + struct.pack("<i", len(val)) + b"\x00" + val
        elif val is None:
            body += b"\x0a" + k
        else:
            body += (b"\x04" if isinstance(val, list) else b"\x03") + k + _bson(val)
    return struct.pack("<i", len(body) + 5) + body + b"\x00"


SAVE = {"SaveName": "None", "GameMode": "Chess", "Gravity": 0.5, "Hands": True, "Note": None,
        "ObjectStates": [{"Name": "Card", "Transform": {"posX": 1.25}}, {"Name": "Deck"}], "DrawImage": b"\x89PNG"}


def _legacy(root, mod_id, save=SAVE):
    folder = os.path.join(root, "content", str(tts.APP_ID), mod_id)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "12818447706391429287_legacy.bin")
    with open(path, "wb") as f:
        f.write(_bson(save))
    return folder, path


class LegacyPathTest(unittest.TestCase):
    def test_downloader_passes_steamcmd_path(self):
        """SteamCMD reports <id>/<hash>_legacy.bin for legacy items; the handler gets exactly that file."""
        from jmd.core.downloader import Downloader
        with tempfile.TemporaryDirectory() as t:
            _, path = _legacy(t, "3799444051")
            got = []
            d = Downloader("steamcmd", t, tts.APP_ID, [], lambda *a: None, sync=lambda i, p: got.append(p) or p)
            outcome, _ = d._finish("3799444051", path, 123)
            self.assertEqual(outcome, "done")
            self.assertEqual(got, [path])

    def test_sync_item_takes_the_folder(self):
        with tempfile.TemporaryDirectory() as t:
            folder, path = _legacy(t, "5")
            for mode in ("copy", "hardlink", "link"):
                dst = sync.sync_item(path, os.path.join(t, "Mods"), "5" + mode, mode)
                self.assertTrue(os.path.isfile(os.path.join(dst, os.path.basename(path))), mode)

    def test_generic_handler_copies_legacy_folder(self):
        from jmd.handlers import get
        with tempfile.TemporaryDirectory() as t:
            _, path = _legacy(t, "5")
            mod_dir = os.path.join(t, "Mods")
            profile = models.Profile(id="g", name="G", app_id=1, mod_dir=mod_dir)
            dst = get("generic").place_download(profile, "5", path)
            self.assertEqual(dst, os.path.join(disabled_dir(mod_dir), "5"))
            self.assertTrue(os.path.isfile(os.path.join(dst, os.path.basename(path))))

    def test_tts_uses_the_reported_file(self):
        """An update may leave the old <hash>_legacy.bin next to the new one."""
        from jmd.handlers import get
        with tempfile.TemporaryDirectory() as t:
            folder, _ = _legacy(t, "9")
            new = os.path.join(folder, "99999_legacy.bin")
            with open(new, "wb") as f:
                f.write(_bson({"SaveName": "v2"}))
            profile = models.Profile(id="t", name="T", app_id=tts.APP_ID, mod_dir=os.path.join(t, "WS"))
            dst = get("tts").place_download(profile, "9", new)
            self.assertEqual(tts.save_name(dst), "v2")


class BsonTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            _, path = _legacy(t, "1")
            save = tts.load_save(path)
            self.assertEqual(save["ObjectStates"][0]["Transform"]["posX"], 1.25)
            self.assertIs(save["Hands"], True)
            self.assertIsNone(save["Note"])
            self.assertEqual(save["DrawImage"], "iVBORw==")  # base64, like Newtonsoft
            self.assertEqual(list(save)[:3], ["SaveName", "GameMode", "Gravity"])

    def test_json_text_passthrough(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "x_legacy.bin")
            with open(path, "w", encoding="utf-8") as f:
                f.write('\n {"SaveName": "Old upload"}')
            self.assertEqual(tts.load_save(path)["SaveName"], "Old upload")

    def test_length_byte_looks_like_brace(self):
        """A BSON length ending in 0x7B starts with '{' but is still BSON."""
        for pad in range(300):
            data = _bson({"SaveName": "x" * pad})
            if data[0] == 0x7B:
                break
        self.assertEqual(data[0], 0x7B)
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "x_legacy.bin")
            with open(path, "wb") as f:
                f.write(data)
            self.assertEqual(tts.load_save(path)["SaveName"], "x" * pad)

    def test_broken(self):
        with self.assertRaises(tts.TtsError):
            tts.bson_loads(b"\x10\x00\x00\x00\x02ab")

    def test_write_fills_name_and_epoch(self):
        with tempfile.TemporaryDirectory() as t:
            _, path = _legacy(t, "1")
            dst = os.path.join(t, "Workshop", "1.json")
            tts.write_save(path, dst, "Chess Deluxe", 1500000000)
            with open(dst, encoding="utf-8") as f:
                text = f.read()
            save = json.loads(text)
            self.assertEqual(save["SaveName"], "Chess Deluxe")
            self.assertEqual(list(save)[:2], ["SaveName", "EpochTime"])
            self.assertTrue(text.startswith('{\n  "SaveName"'))
            self.assertEqual(tts.save_name(dst), "Chess Deluxe")


class InfosTest(unittest.TestCase):
    TTS_DIR = "C:\\Users\\yusuf\\OneDrive\\Belgeler//My Games//Tabletop Simulator//Mods//Workshop\\"

    def test_entry_id_mixed_separators(self):
        self.assertEqual(tts.entry_id({"Directory": self.TTS_DIR + "260389428.json"}), "260389428")
        self.assertEqual(tts.entry_id({"Directory": "/home/a/Workshop/7.json"}), "7")

    def test_upsert_keeps_tts_style_and_others(self):
        with tempfile.TemporaryDirectory() as t:
            tts.write_infos(t, [{"Directory": self.TTS_DIR + "1.json", "Name": "UNO", "UpdateTime": 5, "X": 1}])
            tts.upsert_info(t, "2", "Chess", 10)
            infos = tts.read_infos(t)
            self.assertEqual(infos[0], {"Directory": self.TTS_DIR + "1.json", "Name": "UNO", "UpdateTime": 5, "X": 1})
            self.assertEqual(infos[1], {"Directory": self.TTS_DIR + "2.json", "Name": "Chess", "UpdateTime": 10})
            tts.upsert_info(t, "1", "UNO!", 11)
            self.assertEqual(len(tts.read_infos(t)), 2)
            with open(os.path.join(t, tts.INFOS), "rb") as f:
                self.assertIn(b"\r\n", f.read())
            self.assertEqual(tts.drop_info(t, "2")["Name"], "Chess")
            self.assertEqual([tts.entry_id(e) for e in tts.read_infos(t)], ["1"])

    def test_missing_or_broken_file(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(tts.read_infos(t), [])
            with open(os.path.join(t, tts.INFOS), "w") as f:
                f.write("{nope")
            self.assertEqual(tts.read_infos(t), [])


class TtsHandlerTest(unittest.TestCase):
    def setUp(self):
        from jmd.handlers import for_app
        self.h = for_app(tts.APP_ID)
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.mod_dir = os.path.join(t, "Workshop")
        self.profile = models.Profile(id="tts", name="TTS", app_id=tts.APP_ID, mod_dir=self.mod_dir, handler="tts")
        self.content = os.path.join(t, "content", str(tts.APP_ID))
        # one mod TTS subscribed itself
        os.makedirs(self.mod_dir)
        with open(os.path.join(self.mod_dir, "100.json"), "w", encoding="utf-8") as f:
            json.dump({"SaveName": "UNO"}, f)
        tts.write_infos(self.mod_dir, [{"Directory": os.path.join(self.mod_dir, "100.json"), "Name": "UNO",
                                        "UpdateTime": 7}])

    def tearDown(self):
        self.tmp.cleanup()

    def _download(self, mod_id="200"):
        folder, path = _legacy(self.tmp.name, mod_id)
        pngs = []

        def save_png(url, dst):
            pngs.append(url)
            with open(dst, "wb") as f:
                f.write(b"png")
        meta = {"title": "Chess", "preview_url": "https://x/p.jpg", "time_updated": 1, "save_png": save_png}
        # SteamCMD's file path goes through the downloader fix first; the handler also accepts the folder
        return self.h.place_download(self.profile, mod_id, folder, meta=meta), pngs

    def _ctx(self):
        installed = {"200": models.InstalledRecord(id="200", title="Chess")}
        return GameContext(self.profile, installed, self.content, [])

    def test_handler_registered(self):
        self.assertEqual(self.h.key, "tts")
        self.assertEqual(self.h.fixed_sync_mode, "copy")

    def test_download_is_active(self):
        dst, pngs = self._download()
        self.assertEqual(dst, os.path.join(self.mod_dir, "200.json"))
        with open(dst, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["SaveName"], "Chess")
        self.assertTrue(os.path.isfile(os.path.join(self.mod_dir, "200.png")))
        self.assertEqual(pngs, ["https://x/p.jpg"])
        names = {tts.entry_id(e): e["Name"] for e in tts.read_infos(self.mod_dir)}
        self.assertEqual(names, {"100": "UNO", "200": "Chess"})

    def test_png_failure_does_not_fail(self):
        folder, _ = _legacy(self.tmp.name, "300")

        def boom(url, dst):
            raise OSError("offline")
        dst = self.h.place_download(self.profile, "300", folder, meta={"title": "T", "preview_url": "u", "save_png": boom})
        self.assertTrue(os.path.isfile(dst))

    def test_scan_toggle_roundtrip(self):
        self._download()
        ctx = self._ctx()
        by_uid, _ = mods.index(self.h.scan(ctx))
        self.assertEqual(by_uid["100"].name, "UNO")
        self.assertEqual(by_uid["100"].source, mods.LOCAL)
        self.assertEqual(by_uid["200"].source, mods.JMM)
        self.assertEqual(by_uid["200"].preview, os.path.join(self.mod_dir, "200.png"))
        self.assertEqual(sorted(self.h.read_active(ctx, by_uid.values())), ["100", "200"])
        # everything off
        self.assertEqual(self.h.write_active(ctx, list(by_uid.values()), []), [])
        off = disabled_dir(self.mod_dir)
        self.assertEqual(sorted(os.listdir(self.mod_dir)), [tts.INFOS])
        self.assertEqual(tts.read_infos(self.mod_dir), [])
        self.assertEqual(sorted(tts.entry_id(e) for e in tts.read_infos(off)), ["100", "200"])
        by_uid, _ = mods.index(self.h.scan(ctx))
        self.assertEqual(self.h.read_active(ctx, by_uid.values()), [])
        self.assertEqual(by_uid["100"].name, "UNO")
        # an update to a switched-off mod stays off
        self._download()
        self.assertFalse(os.path.exists(os.path.join(self.mod_dir, "200.json")))
        # and back on: TTS's own entry comes back with its fields
        self.assertEqual(self.h.write_active(ctx, list(by_uid.values()), ["100", "200"]), [])
        infos = {tts.entry_id(e): e for e in tts.read_infos(self.mod_dir)}
        self.assertEqual(infos["100"]["UpdateTime"], 7)
        self.assertEqual(infos["100"]["Directory"], os.path.join(self.mod_dir, "100.json"))
        self.assertTrue(os.path.isfile(os.path.join(self.mod_dir, "200.png")))
        self.assertEqual(tts.read_infos(off), [])

    def test_remove(self):
        self._download()  # also leaves the SteamCMD copy in content/<app>/200
        ctx = self._ctx()
        by_uid, _ = mods.index(self.h.scan(ctx))
        self.h.remove(ctx, by_uid["200"])
        self.assertEqual(sorted(os.listdir(self.mod_dir)), ["100.json", tts.INFOS])
        self.assertEqual([tts.entry_id(e) for e in tts.read_infos(self.mod_dir)], ["100"])
        self.assertFalse(os.path.exists(os.path.join(self.content, "200")))

    def test_default_folder(self):
        path = self.h.default_mod_dir()
        self.assertTrue(path.endswith(os.path.join("Tabletop Simulator", "Mods", "Workshop")))


if __name__ == "__main__":
    unittest.main()
