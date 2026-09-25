import os
import tempfile
import unittest

from jmd.core import ids, models, steamcmd, sync, library, steam_api
from jmd.core.store import Store


class IdsTest(unittest.TestCase):
    def test_mod_id(self):
        self.assertEqual(ids.extract_mod_id("3530446424"), "3530446424")
        self.assertEqual(ids.extract_mod_id("https://steamcommunity.com/sharedfiles/filedetails/?id=3530446424&searchtext=Trains"), "3530446424")
        self.assertEqual(ids.extract_mod_id("https://steamcommunity.com/workshop/filedetails/?l=en&id=2009463077"), "2009463077")
        self.assertIsNone(ids.extract_mod_id("hello"))

    def test_multi(self):
        text = "2009463077\nhttps://steamcommunity.com/sharedfiles/filedetails/?id=3014915404, 2009463077 junk"
        self.assertEqual(ids.extract_ids(text), ["2009463077", "3014915404"])

    def test_app_id(self):
        self.assertEqual(ids.extract_app_id("https://store.steampowered.com/app/294100/RimWorld/"), "294100")
        self.assertEqual(ids.extract_app_id("294100"), "294100")


class QueueTest(unittest.TestCase):
    def test_add_group_dep_remove_roundtrip(self):
        q = models.QueueState()
        a = q.add_item("1")
        a.title = "Trains"
        self.assertIsNone(q.add_item("1"))
        dep = q.add_dep(a, "2", "Harmony")
        self.assertEqual(dep.required_by, "Trains")
        g = q.add_group("9", "Coll", ["1", "3", "4"])
        self.assertEqual([i.id for i in g.items], ["3", "4"])
        self.assertEqual([i.id for i in q.items()], ["1", "2", "3", "4"])
        q2 = models.QueueState.from_list(q.to_list())
        self.assertEqual([i.id for i in q2.items()], ["1", "2", "3", "4"])
        q2.remove_id("2")
        self.assertFalse(q2.has("2"))
        q2.remove_id("9")
        self.assertEqual([i.id for i in q2.items()], ["1"])

    def test_skipped(self):
        item = models.ModItem(id="1", status=models.QUEUED, checked=False)
        self.assertEqual(item.display_status, models.SKIPPED)


class ParserTest(unittest.TestCase):
    # chunks recorded from a real SteamCMD run
    CHUNKS = [
        b"\x1b[1mworkshop_download_item 294100 2009463077\n\x1b[0m",
        b"Downloading item 2009463077 ...\x1b[0m",
        b'Success. Downloaded item 2009463077 to "/c/steamapps/workshop/content/294100/2009463077" (5729526 bytes) \x1b[0m',
        b"\x1b[1mworkshop_download_item 294100 1234\n\x1b[0m",
        b"Downloading item 1234 ...\x1b[0m",
        b"\n\x1b[0mERROR! Download item 1234 failed (File Not Found).\x1b[0m",
        b"Logging in user 'bob' to Steam Public...\nSteam Guard code:",
    ]

    def test_events(self):
        events = []
        p = steamcmd.OutputParser(lambda *e: events.append(e))
        for c in self.CHUNKS:
            p.feed(c)
        kinds = [e for e in events if e[0] != "log"]
        self.assertIn(("item_start", "2009463077"), kinds)
        self.assertIn(("item_done", "2009463077", "/c/steamapps/workshop/content/294100/2009463077", 5729526), kinds)
        self.assertIn(("item_error", "1234", "File Not Found"), kinds)
        self.assertIn(("prompt", "guard"), kinds)

    def test_login_echo_redacted(self):
        events = []
        p = steamcmd.OutputParser(lambda *e: events.append(e))
        p.feed(b"\x1b[1mlogin bob hunter2 AB12C\n\x1b[0m")
        self.assertIn(("log", "login bob ********"), events)
        self.assertFalse(any("hunter2" in str(e) for e in events))

    def test_script(self):
        s = steamcmd.build_script("/cache", 294100, ["1", "2"])
        self.assertEqual(s, 'force_install_dir "/cache"\nlogin anonymous\nworkshop_download_item 294100 1\nworkshop_download_item 294100 2\nquit\n')


class SyncTest(unittest.TestCase):
    def test_mirror_and_link(self):
        with tempfile.TemporaryDirectory() as t:
            src = os.path.join(t, "src")
            os.makedirs(os.path.join(src, "About"))
            with open(os.path.join(src, "About", "About.xml"), "w") as f:
                f.write("a")
            mods = os.path.join(t, "Mods")
            dst = sync.sync_item(src, mods, "42", "copy")
            with open(os.path.join(dst, "stale.txt"), "w") as f:
                f.write("x")
            sync.mirror_copy(src, dst)
            self.assertFalse(os.path.exists(os.path.join(dst, "stale.txt")))
            self.assertTrue(os.path.exists(os.path.join(dst, "About", "About.xml")))
            with self.assertRaises(sync.SyncError):
                sync.link(src, dst)
            dst2 = sync.sync_item(src, mods, "43", "link")
            self.assertTrue(sync.is_link(dst2))
            sync.mirror_copy(src, dst2)  # copy over a link replaces the link
            self.assertFalse(sync.is_link(dst2))


class VdfTest(unittest.TestCase):
    def test_parse(self):
        text = '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"C:\\\\Steam"\n\t\t"apps"\n\t\t{\n\t\t\t"294100"\t\t"1"\n\t\t}\n\t}\n}'
        data = library.parse_vdf(text)
        self.assertEqual(data["libraryfolders"]["0"]["path"], "C:\\Steam")
        self.assertEqual(data["libraryfolders"]["0"]["apps"]["294100"], "1")


class RequiredItemsTest(unittest.TestCase):
    def test_parse_page(self):
        page = '''<div class="requiredItemsContainer" id="RequiredItems">
            <a href="https://steamcommunity.com/workshop/filedetails/?id=3014915404" target="_blank" data-subscribed="0">
                <div class="requiredItem">
                    Vehicle Framework                                   </div>
            </a>
            <a href="https://steamcommunity.com/workshop/filedetails/?id=2009463077" target="_blank" data-subscribed="0">
                <div class="requiredItem">
                    Harmony &amp; Co                                   </div>
            </a>
                    </div>
        </div>'''
        self.assertEqual(steam_api.parse_required_items(page), [("3014915404", "Vehicle Framework"), ("2009463077", "Harmony & Co")])


class StoreTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            st = Store(t)
            s = st.load_settings()
            s.retries = 5
            st.save_settings(s)
            self.assertEqual(st.load_settings().retries, 5)
            q = models.QueueState()
            q.add_item("1")
            st.save_list("rim", "My run", q)
            self.assertEqual(st.list_names("rim"), ["My run"])
            self.assertEqual([i.id for i in st.load_list("rim", "My run").items()], ["1"])


if __name__ == "__main__":
    unittest.main()
