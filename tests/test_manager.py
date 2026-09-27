# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import shutil
import tempfile
import unittest

from jmd.core import models, mods, rimworld, sorting, sync, validate
from jmd.core.mods import Dep, ModEntry, ModRef, Modset
from jmd.core.store import Store

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "rimworld")


def entry(uid, **kw):
    kw.setdefault("deps", [])
    return ModEntry(uid=uid, **kw)


class AboutTest(unittest.TestCase):
    def test_real_about_files(self):
        found = {e.uid: e for e in rimworld.scan_folder(os.path.join(FIX, "Mods"), mods.JMM, "1.6")}
        self.assertEqual(set(found), {"sereq.rusticworkbenches", "hyaukyuu.techapparel"})
        rustic = found["sereq.rusticworkbenches"]
        self.assertEqual((rustic.name, rustic.author, rustic.wid), ("Rustic Workbenches", "SereQ", "3761824516"))
        self.assertEqual(rustic.supported, ["1.6"])
        self.assertIn("dankpyon.medieval.overhaul", rustic.load_after)
        self.assertEqual(rustic.incompatible, ["vanillaexpanded.vtexvariations"])
        # this one starts with a UTF-8 BOM
        robe = found["hyaukyuu.techapparel"]
        self.assertEqual(robe.name, "Tech Robe")
        self.assertEqual(robe.mod_version, "Release 1.0 - 22.09.26")
        self.assertIn("ceteam.combatextended", robe.load_after)

    def test_by_version_and_deps(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "About"))
            with open(os.path.join(t, "About", "About.xml"), "w") as f:
                f.write("""<ModMetaData><packageId>A.Mod</packageId><name>A</name>
  <modDependencies><li><packageId>brrainz.harmony</packageId><displayName>Harmony</displayName>
    <steamWorkshopUrl>steam://url/CommunityFilePage/2009463077</steamWorkshopUrl></li></modDependencies>
  <loadAfter><li>old.rule</li></loadAfter>
  <loadAfterByVersion><v1.6><li>New.Rule</li></v1.6></loadAfterByVersion>
  <forceLoadBefore><li>z.mod</li></forceLoadBefore>
</ModMetaData>""")
            e = rimworld.parse_about(t, "1.6")
            self.assertEqual(e.uid, "a.mod")
            self.assertEqual(e.deps, [Dep("brrainz.harmony", "Harmony", "2009463077")])
            self.assertEqual(e.load_after, ["new.rule"])
            self.assertEqual(e.load_before, ["z.mod"])
            self.assertEqual(rimworld.parse_about(t, "1.5").load_after, ["old.rule"])

    def test_broken_xml_falls_back(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "About"))
            with open(os.path.join(t, "About", "About.xml"), "w") as f:
                f.write("<ModMetaData><name>Tom & Jerry</name><packageId>tom.jerry</packageId></ModMetaData>")
            e = rimworld.parse_about(t)
            self.assertEqual((e.uid, e.name), ("tom.jerry", "Tom & Jerry"))


class ModsConfigTest(unittest.TestCase):
    def test_read_write_keeps_rest(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = os.path.join(t, "ModsConfig.xml")
            shutil.copy(os.path.join(FIX, "ModsConfig.xml"), cfg)
            self.assertEqual(rimworld.read_active(cfg)[3], "hyaukyuu.techapparel_steam")
            with open(cfg) as f:
                before = f.read()
            rimworld.write_active(cfg, ["ludeon.rimworld", "sereq.rusticworkbenches"])
            self.assertEqual(rimworld.read_active(cfg), ["ludeon.rimworld", "sereq.rusticworkbenches"])
            with open(cfg) as f:
                after = f.read()
            for keep in ("<version>1.6.4630 rev467</version>", "<knownExpansions>\n    <li>ludeon.rimworld.royalty</li>"):
                self.assertIn(keep, after)
            self.assertIn("  <activeMods>\n    <li>ludeon.rimworld</li>\n", after)
            self.assertEqual(before.split("<activeMods>")[0], after.split("<activeMods>")[0])

    def test_missing_and_empty(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = os.path.join(t, "Config", "ModsConfig.xml")
            self.assertEqual(rimworld.read_active(cfg), [])
            rimworld.write_active(cfg, ["ludeon.rimworld"])
            self.assertEqual(rimworld.read_active(cfg), ["ludeon.rimworld"])
            with open(cfg, "w") as f:
                f.write("<ModsConfigData><activeMods /></ModsConfigData>")
            rimworld.write_active(cfg, ["a", "b"])
            self.assertEqual(rimworld.read_active(cfg), ["a", "b"])

    def test_backup_rotation(self):
        with tempfile.TemporaryDirectory() as t:
            cfg = os.path.join(t, "ModsConfig.xml")
            shutil.copy(os.path.join(FIX, "ModsConfig.xml"), cfg)
            folder = os.path.join(t, "backups")
            os.makedirs(folder)
            for i in range(3):
                open(os.path.join(folder, f"ModsConfig-2000010{i}-000000.xml"), "w").close()
            newest = rimworld.backup(cfg, folder, keep=2)
            self.assertEqual(sorted(os.listdir(folder)), ["ModsConfig-20000102-000000.xml", os.path.basename(newest)])

    def test_version(self):
        self.assertEqual(validate.short_version("1.6.4630 rev467"), "1.6")
        self.assertEqual(validate.short_version(""), "")


class SortTest(unittest.TestCase):
    def test_tiers_and_rules(self):
        es = {u: entry(u) for u in ("x.b", "ludeon.rimworld", "x.a", "brrainz.harmony", "ludeon.rimworld.biotech", "ludeon.rimworld.royalty")}
        es["x.b"].load_after = ["x.a"]
        es["x.a"].load_before = ["ludeon.rimworld"]  # can't beat a pinned tier
        order, cycles = sorting.topo_sort(list(es), es, rimworld.tier)
        self.assertEqual(order, ["brrainz.harmony", "ludeon.rimworld", "ludeon.rimworld.royalty",
                                 "ludeon.rimworld.biotech", "x.a", "x.b"])
        self.assertEqual(cycles, [])

    def test_stable_and_minimal(self):
        es = {u: entry(u) for u in "abcd"}
        es["a"].deps = [Dep("d")]
        order, _ = sorting.topo_sort(["a", "b", "c", "d"], es)
        self.assertEqual(order, ["b", "c", "d", "a"])
        self.assertEqual(sorting.topo_sort(["c", "b"], es)[0], ["c", "b"])

    def test_missing_targets_ignored(self):
        es = {"a": entry("a", load_after=["not.here"])}
        self.assertEqual(sorting.topo_sort(["a"], es)[0], ["a"])

    def test_cycle_keeps_user_order(self):
        es = {u: entry(u) for u in "abc"}
        es["a"].load_after = ["b"]
        es["b"].load_after = ["a"]
        es["c"].load_before = ["b"]
        order, cycles = sorting.topo_sort(["b", "a", "c"], es)
        self.assertEqual([sorted(c) for c in cycles], [["a", "b"]])
        self.assertEqual(len(order), 3)
        self.assertLess(order.index("b"), order.index("a"))


class ValidateTest(unittest.TestCase):
    def test_issues(self):
        es = {
            "core": entry("core"),
            "a": entry("a", deps=[Dep("core"), Dep("gone", "Gone", "123"), Dep("b")], supported=["1.5"]),
            "b": entry("b", incompatible=["c"]),
            "c": entry("c", load_before=["core"]),
        }
        issues = validate.check(["a", "core", "c"], es, "1.6.1 rev1", tier=lambda u: 0 if u == "core" else 1)
        kinds = sorted((i.uid, i.kind) for i in issues)
        self.assertIn(("a", validate.MISSING_DEP), kinds)
        self.assertIn(("a", validate.INACTIVE_DEP), kinds)
        self.assertIn(("a", validate.ORDER), kinds)      # core should be before a
        self.assertEqual(validate.check(["c", "core"], {"c": es["c"], "core": es["core"]}), [])
        self.assertIn(("a", validate.VERSION), kinds)
        self.assertNotIn(validate.ORDER, [k for u, k in kinds if u == "c"])
        missing = next(i for i in issues if i.kind == validate.MISSING_DEP)
        self.assertEqual(missing.fix, ["123"])

    def test_incompatible_one_sided_once(self):
        es = {"a": entry("a", incompatible=["b"]), "b": entry("b", incompatible=["a"])}
        issues = validate.check(["a", "b"], es)
        self.assertEqual([i.kind for i in issues], [validate.INCOMPATIBLE])

    def test_no_version_no_warning(self):
        es = {"a": entry("a", supported=["1.4"])}
        self.assertEqual(validate.check(["a"], es, ""), [])
        self.assertEqual(validate.check(["a"], es, "1.6", check_order=False)[0].kind, validate.VERSION)


class ModsetTest(unittest.TestCase):
    def test_resolve_by_uid_then_wid(self):
        es = [entry("a.mod", wid="11"), entry("b.mod"), entry("c.mod", wid="33")]
        refs = [ModRef(uid="B.Mod_steam"), ModRef(wid="11"), ModRef(wid="99", name="Missing"), ModRef(uid="a.mod")]
        active, missing = mods.resolve(refs, es)
        self.assertEqual(active, ["b.mod", "a.mod"])
        self.assertEqual([m.wid for m in missing], ["99"])

    def test_diff(self):
        d = mods.diff(["a", "b", "c"], ["a", "c", "b", "d"])
        self.assertEqual((d.added, d.removed, d.moved, d.count), (["d"], [], True, 2))
        self.assertEqual(mods.diff(["a"], ["a"]).count, 0)

    def test_store_and_migration(self):
        with tempfile.TemporaryDirectory() as t:
            st = Store(t)
            st.save_modset("rim", Modset("SOS2 run", [ModRef(uid="a", wid="1", name="A")]))
            self.assertEqual(st.modset_names("rim"), ["SOS2 run"])
            self.assertEqual(st.load_modset("rim", "SOS2 run").mods[0], ModRef("a", "1", "A"))
            q = models.QueueState()
            q.add_item("5").title = "Five"
            q.add_item("6").checked = False
            st.save_list("rim", "Old list", q)
            self.assertEqual(st.migrate_lists("rim"), ["Old list"])
            self.assertEqual(st.load_modset("rim", "Old list").mods, [ModRef(wid="5", name="Five")])
            self.assertEqual(st.list_names("rim"), [])
            self.assertTrue(os.path.isfile(os.path.join(t, "profiles", "rim", "lists", "Old list.json.bak")))
            st.save_pending("rim", ["1", "2", "1"])
            self.assertEqual(st.load_pending("rim"), ["1", "2"])


class HardlinkTest(unittest.TestCase):
    def _src(self, t):
        src = os.path.join(t, "cache", "42")
        os.makedirs(os.path.join(src, "About"))
        for rel, body in (("About/About.xml", "a"), ("big.bin", "b")):
            with open(os.path.join(src, rel), "w") as f:
                f.write(body)
        return src

    def test_links_relinks_and_cleans(self):
        with tempfile.TemporaryDirectory() as t:
            src = self._src(t)
            dst = sync.sync_item(src, os.path.join(t, "Mods"), "42", "hardlink")
            self.assertFalse(os.path.islink(dst))
            self.assertTrue(os.path.samefile(os.path.join(src, "big.bin"), os.path.join(dst, "big.bin")))
            # SteamCMD replaces a file (new inode) and drops another
            os.remove(os.path.join(src, "big.bin"))
            with open(os.path.join(src, "big.bin"), "w") as f:
                f.write("v2")
            os.remove(os.path.join(src, "About", "About.xml"))
            sync.sync_item(src, os.path.join(t, "Mods"), "42", "hardlink")
            self.assertTrue(os.path.samefile(os.path.join(src, "big.bin"), os.path.join(dst, "big.bin")))
            self.assertFalse(os.path.exists(os.path.join(dst, "About", "About.xml")))
            # switching the profile back to copy breaks the links
            sync.sync_item(src, os.path.join(t, "Mods"), "42", "copy")
            self.assertFalse(os.path.samefile(os.path.join(src, "big.bin"), os.path.join(dst, "big.bin")))
            with open(os.path.join(dst, "big.bin")) as f:
                self.assertEqual(f.read(), "v2")

    def test_cross_device_falls_back_to_copy(self):
        import errno
        with tempfile.TemporaryDirectory() as t:
            src = self._src(t)
            real, told = os.link, []

            def no_link(*_a, **_k):
                raise OSError(errno.EXDEV, "Invalid cross-device link")
            os.link = no_link
            try:
                dst = sync.sync_item(src, os.path.join(t, "Mods"), "42", "hardlink", on_fallback=told.append)
            finally:
                os.link = real
            self.assertEqual(len(told), 1)
            self.assertTrue(os.path.isfile(os.path.join(dst, "big.bin")))
            self.assertFalse(os.path.samefile(os.path.join(src, "big.bin"), os.path.join(dst, "big.bin")))


def _mod(root, folder, about=None):
    os.makedirs(os.path.join(root, folder, "About"), exist_ok=True)
    if about:
        with open(os.path.join(root, folder, "About", "About.xml"), "w") as f:
            f.write(about)


class GenericHandlerTest(unittest.TestCase):
    def _ctx(self, t, mode):
        from jmd.handlers.base import GameContext
        profile = models.Profile(id="g", name="G", app_id=10, mod_dir=os.path.join(t, "Mods"), sync_mode=mode)
        content = os.path.join(t, "cache", "content", "10")
        lib = os.path.join(t, "lib")
        installed = {"111": models.InstalledRecord(id="111", title="Downloaded")}
        _mod(content, "111")
        _mod(os.path.join(t, "Mods"), "handmade")
        _mod(os.path.join(lib, "steamapps", "workshop", "content", "10"), "222")
        return GameContext(profile, installed, content, [lib])

    def _roundtrip(self, mode):
        from jmd.handlers import get
        with tempfile.TemporaryDirectory() as t:
            ctx = self._ctx(t, mode)
            h = get("generic")
            if mode != "copy":
                sync.sync_item(ctx.cache_path("111"), ctx.mod_dir, "111", mode)
            else:
                shutil.copytree(ctx.cache_path("111"), os.path.join(ctx.mod_dir, "111"))
            by_uid, dups = mods.index(h.scan(ctx))
            self.assertEqual(by_uid["111"].source, mods.JMM)
            self.assertEqual(by_uid["111"].name, "Downloaded")
            self.assertFalse(by_uid["222"].toggleable)
            self.assertEqual(sorted(h.read_active(ctx, by_uid.values())), ["111", "222", "handmade"])
            # everything off
            self.assertEqual(h.write_active(ctx, list(by_uid.values()), ["222"]), [])
            self.assertEqual(os.listdir(ctx.mod_dir), [])
            by_uid, _ = mods.index(h.scan(ctx))
            self.assertEqual(h.read_active(ctx, by_uid.values()), ["222"])
            self.assertTrue(os.path.isdir(ctx.cache_path("111")))
            # and back on
            self.assertEqual(h.write_active(ctx, list(by_uid.values()), ["111", "handmade"]), [])
            self.assertEqual(sorted(os.listdir(ctx.mod_dir)), ["111", "handmade"])
            self.assertEqual(os.path.islink(os.path.join(ctx.mod_dir, "111")), mode == "link")

    def test_copy(self):
        self._roundtrip("copy")

    def test_link(self):
        self._roundtrip("link")

    def test_hardlink(self):
        self._roundtrip("hardlink")


class RimWorldHandlerTest(unittest.TestCase):
    def test_scan_read_write(self):
        from jmd.handlers import get
        from jmd.handlers.base import GameContext
        with tempfile.TemporaryDirectory() as t:
            game = os.path.join(t, "RimWorld")
            os.makedirs(game)
            with open(os.path.join(game, "Version.txt"), "w") as f:
                f.write("1.6.4630 rev467")
            _mod(os.path.join(game, "Data"), "Core", "<ModMetaData><packageId>Ludeon.RimWorld</packageId><name>Core</name></ModMetaData>")
            shutil.copytree(os.path.join(FIX, "Mods"), os.path.join(game, "Mods"))
            lib = os.path.join(t, "lib")
            _mod(os.path.join(lib, "steamapps", "workshop", "content", "294100"), "2009463077",
                 "<ModMetaData><packageId>brrainz.harmony</packageId><name>Harmony</name></ModMetaData>")
            shutil.copytree(os.path.join(FIX, "Mods", "3806038418"),
                            os.path.join(lib, "steamapps", "workshop", "content", "294100", "3806038418"))
            cfg = os.path.join(t, "ModsConfig.xml")
            shutil.copy(os.path.join(FIX, "ModsConfig.xml"), cfg)
            profile = models.Profile(id="r", name="R", app_id=294100, mod_dir=os.path.join(game, "Mods"),
                                     handler="rimworld", game_dir=game, config_path=cfg)
            ctx = GameContext(profile, {"3761824516": models.InstalledRecord(id="3761824516", file_size=5)}, "", [lib])
            h = get("rimworld")
            self.assertEqual(h.game_version(ctx), "1.6.4630 rev467")
            by_uid, dups = mods.index(h.scan(ctx))
            self.assertEqual(by_uid["ludeon.rimworld"].source, mods.BUILTIN)
            self.assertFalse(by_uid["ludeon.rimworld"].toggleable)
            self.assertEqual(by_uid["sereq.rusticworkbenches"].source, mods.JMM)
            self.assertEqual(by_uid["brrainz.harmony"].source, mods.STEAM)
            self.assertEqual(dups, ["hyaukyuu.techapparel"])            # Mods/ copy + Steam copy
            self.assertEqual(by_uid["hyaukyuu.techapparel"].source, mods.LOCAL)
            active = h.read_active(ctx, by_uid)
            self.assertEqual(active[:2], ["brrainz.harmony", "ludeon.rimworld"])
            self.assertIn("hyaukyuu.techapparel", active)              # '_steam' dropped
            order, _ = sorting.topo_sort(["sereq.rusticworkbenches", "ludeon.rimworld", "brrainz.harmony"], by_uid, h.tier)
            self.assertEqual(h.write_active(ctx, list(by_uid.values()), order), [])
            self.assertEqual(rimworld.read_active(cfg), ["brrainz.harmony", "ludeon.rimworld", "sereq.rusticworkbenches"])

    def test_no_config_blocks_apply(self):
        from jmd.handlers import get
        from jmd.handlers.base import GameContext
        profile = models.Profile(id="r", name="R", app_id=294100, handler="rimworld", config_path="")
        h = get("rimworld")
        orig = rimworld.find_config
        rimworld.find_config = lambda libs=(): ""
        try:
            self.assertTrue(h.can_apply(GameContext(profile)))
            self.assertEqual(h.read_active(GameContext(profile), {}), [])
        finally:
            rimworld.find_config = orig


if __name__ == "__main__":
    unittest.main()
