# -*- coding: utf-8 -*-
"""Tests for SEC-01 (kb_health), SEC-02 (kb_safeio), SEC-03 (kb_secure), SEC-04 (kb_integrity).
Run:  python -m unittest discover -s tests -v      (no Windows APIs, no game, no network needed)
Token-shaped test strings are built at run time so the repository's secret scan never sees one."""
import os, sys, json, time, shutil, tempfile, threading, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import kb_safeio, kb_secure, kb_health          # noqa: E402

kb_safeio.LOG[0] = lambda m: LOGS.append(m)
LOGS = []


def rj(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def wf(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kbtest_")
        LOGS.clear()
        kb_safeio._last_backup.clear()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def p(self, *a):
        return os.path.join(self.d, *a)


# ------------------------------------------------------------------ SEC-02
class SafeIO(Tmp):
    def test_atomic_write_and_read(self):
        f = self.p("a.json")
        self.assertTrue(kb_safeio.atomic_write_json(f, {"x": 1, "ar": "مرحبا"}))
        self.assertEqual(kb_safeio.safe_load_json(f, None), {"x": 1, "ar": "مرحبا"})
        self.assertEqual([n for n in os.listdir(self.d) if n.endswith(".tmp")], [])

    def test_missing_returns_default(self):
        self.assertEqual(kb_safeio.safe_load_json(self.p("none.json"), {"d": 1}), {"d": 1})

    def test_truncated_file_restored_from_backup(self):
        f = self.p("state.json")
        kb_safeio.atomic_write_json(f, {"gold": 100})
        kb_safeio.atomic_write_json(f, {"gold": 200})          # first save had no file to back up
        kb_safeio._last_backup.clear()
        kb_safeio.atomic_write_json(f, {"gold": 300})          # backs up {"gold": 200}
        wf(f, '{"gold": 3')                                     # power cut in the middle of a write
        data = kb_safeio.safe_load_json(f, {})
        self.assertEqual(data, {"gold": 200})
        self.assertEqual(rj(f), {"gold": 200})    # restored on disk too
        self.assertTrue(any("damaged" in m for m in LOGS))
        self.assertTrue(any(".corrupt-" in n for n in os.listdir(self.p("backups"))))

    def test_empty_file_is_damaged_not_valid(self):
        f = self.p("e.json")
        open(f, "w").close()
        self.assertEqual(kb_safeio.safe_load_json(f, {"def": True}), {"def": True})
        self.assertTrue(any("empty file" in m for m in LOGS))

    def test_backup_rotation_keeps_newest(self):
        f = self.p("r.json")
        for i in range(kb_safeio.KEEP + 4):
            kb_safeio.atomic_write_json(f, {"i": i})
            kb_safeio._last_backup.clear()
            time.sleep(0.002)
        self.assertEqual(len(kb_safeio.list_backups(f)), kb_safeio.KEEP)
        newest = rj(kb_safeio.list_backups(f)[0])
        self.assertEqual(newest["i"], kb_safeio.KEEP + 2)

    def test_damaged_file_never_backed_up(self):
        f = self.p("bad.json")
        wf(f, "{oops")
        self.assertIsNone(kb_safeio.backup(f, force=True))

    def test_schema_refuses_wrong_shape(self):
        f = self.p("tasks.json")
        kb_safeio.atomic_write_json(f, {"tasks": []})
        self.assertFalse(kb_safeio.atomic_write_json(f, ["not", "a", "dict"]))
        self.assertFalse(kb_safeio.atomic_write_json(f, {"loop_minutes": 5}))   # "tasks" missing
        self.assertEqual(rj(f), {"tasks": []})

    def test_schema_mismatch_on_load_uses_backup(self):
        f = self.p("version.json")
        kb_safeio.atomic_write_json(f, {"version": 250})
        kb_safeio._last_backup.clear()
        kb_safeio.atomic_write_json(f, {"version": 251})
        wf(f, '{"nothing": 1}')
        self.assertEqual(kb_safeio.safe_load_json(f, {}), {"version": 250})

    def test_unserialisable_refused(self):
        f = self.p("x.json")
        kb_safeio.atomic_write_json(f, {"ok": 1})
        self.assertFalse(kb_safeio.atomic_write_json(f, {"bad": object()}))
        self.assertEqual(rj(f), {"ok": 1})

    def test_concurrent_update_json_loses_nothing(self):
        f = self.p("counter.json")
        kb_safeio.atomic_write_json(f, {"n": 0}, make_backup=False)

        def worker():
            for _ in range(25):
                kb_safeio.update_json(f, lambda d: {"n": d["n"] + 1}, make_backup=False)
        ts = [threading.Thread(target=worker) for _ in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(rj(f)["n"], 100)
        self.assertFalse(os.path.exists(f + ".lock"))

    def test_stale_lock_is_taken_over(self):
        f = self.p("s.json")
        wf(f + ".lock", "999999 0")
        old = time.time() - 3600
        os.utime(f + ".lock", (old, old))
        t0 = time.time()
        with kb_safeio.FileLock(f) as lk:
            self.assertTrue(lk.held)
        self.assertLess(time.time() - t0, 2)

    def test_busy_lock_never_blocks_forever(self):
        f = self.p("b.json")
        wf(f + ".lock", "1 1")
        with kb_safeio.FileLock(f, timeout=0.3) as lk:
            self.assertFalse(lk.held)
        self.assertTrue(os.path.exists(f + ".lock"))           # someone else's lock is left alone


# ------------------------------------------------------------------ SEC-03
class Secure(Tmp):
    def test_redact_patterns(self):
        gh = "gh" + "p_" + "A1b2" * 9
        pat = "github" + "_pat_" + "Z9_" * 10
        tg = "123456" + "789:" + "AAH" + "x" * 32
        hook = "https://discord.com/api/webhooks/123456/" + "s3cr3t-" * 6
        line = (f"token {gh} and {pat} bot {tg} hook {hook} "
                "url https://vdo.ninja/?view=abc&password=Sup3rS3cret&label=K "
                "Authorization: Bearer abcdefghijklmnop123 "
                '{"KB_PASSPHRASE": "my long phrase"}')
        out = kb_secure.redact(line)
        for secret in (gh[4:], pat[11:], tg.split(":")[1], "s3cr3t-s3cr3t", "Sup3rS3cret",
                       "abcdefghijklmnop123", "my long phrase"):
            self.assertNotIn(secret, out, secret)
        self.assertIn("view=abc", out)                          # non-secret parts stay readable
        self.assertIn("label=K", out)

    def test_redact_exact_registered_values(self):
        kb_secure.add_secret("correct-horse-battery")
        self.assertEqual(kb_secure.redact("x correct-horse-battery y"), "x [hidden] y")

    def test_redact_leaves_normal_lines(self):
        for line in ("! GitHub token in github_token.txt was refused (401)",
                     "> gather (1/4)", "Round started (settings from dashboard).", "قراءة الموارد"):
            self.assertEqual(kb_secure.redact(line), line)

    def test_redact_obj(self):
        o = kb_secure.redact_obj({"DISCORD_WEBHOOK": "https://x", "nested": [{"api_key": "abc123"}],
                                  "name": "Kingbot", "count": 3})
        self.assertEqual(o["DISCORD_WEBHOOK"], "[hidden]")
        self.assertEqual(o["nested"][0]["api_key"], "[hidden]")
        self.assertEqual((o["name"], o["count"]), ("Kingbot", 3))

    def test_safe_join(self):
        base = self.d
        self.assertEqual(kb_secure.safe_join(base, "a", "b.json"), os.path.join(os.path.realpath(base), "a", "b.json"))
        for bad in ("../x", "a/../../x", "/etc/passwd", "C:/Windows/x", "\\\\server\\share", "a\\..\\..\\x", "x\0y"):
            with self.assertRaises(kb_secure.UnsafePath, msg=bad):
                kb_secure.safe_join(base, bad)

    @unittest.skipIf(os.name == "nt", "symlinks need admin rights on Windows")
    def test_safe_join_symlink_escape(self):
        os.symlink("/", self.p("link"))
        with self.assertRaises(kb_secure.UnsafePath):
            kb_secure.safe_join(self.d, "link", "etc")

    def test_safe_name(self):
        self.assertNotIn("/", kb_secure.safe_name("../../evil"))
        for bad in ("..", ".", "CON", "nul.txt", "a/b", "a\\b", ""):
            n = kb_secure.safe_name(bad)
            self.assertNotIn("/", n)
            self.assertNotIn("\\", n)
            self.assertNotIn(n.lower().split(".")[0], ("con", "nul", "", ".", ".."))
        self.assertEqual(kb_secure.safe_name("map_1"), "map_1")

    @unittest.skipIf(os.name == "nt", "POSIX mode bits")
    def test_harden_file_posix(self):
        f = self.p("github_token.txt")
        wf(f, "x")
        os.chmod(f, 0o644)
        self.assertTrue(kb_secure.harden_file(f))
        self.assertEqual(os.stat(f).st_mode & 0o777, 0o600)


# ------------------------------------------------------------------ SEC-01
class Health(Tmp):
    def setUp(self):
        super().setUp()
        self._sf = kb_health.STATE_FILE
        kb_health.STATE_FILE = self.p("recovery_state.json")

    def tearDown(self):
        kb_health.STATE_FILE = self._sf
        super().tearDown()

    def test_no_history_no_delay(self):
        self.assertEqual(kb_health.recovery_delay("restart"), (0, ""))

    def test_backoff_after_burst(self):
        now = time.time()
        st = kb_health._load_state()
        st["restart"] = [now - 300, now - 200, now - 10]
        kb_health._save_state(st)
        wait, why = kb_health.recovery_delay("restart", now)
        self.assertGreater(wait, 0)
        self.assertLessEqual(wait, 60)
        self.assertIn("recoveries", why)
        st["restart"].append(now - 5)
        kb_health._save_state(st)
        wait2, _ = kb_health.recovery_delay("restart", now)
        self.assertGreater(wait2, wait)                         # doubles: 60 s -> 120 s

    def test_daily_cap_turns_into_cooldown(self):
        now = time.time()
        st = kb_health._load_state()
        st["restart"] = [now - 7200 - i * 60 for i in range(kb_health.cap("restart"))]
        kb_health._save_state(st)
        self.assertEqual(kb_health.recovery_delay("restart", now)[0], 0)    # last one 2 h ago -> allowed
        st["restart"].append(now - 60)
        kb_health._save_state(st)
        wait, why = kb_health.recovery_delay("restart", now)
        self.assertTrue(why.startswith("daily cap"))
        self.assertAlmostEqual(wait, kb_health.COOLDOWN - 60, delta=2)

    def test_counts_reset_on_new_game_day(self):
        kb_health.record_recovery("restart", "test")
        self.assertEqual(kb_health.counts()["restart"], 1)
        st = rj(kb_health.STATE_FILE)
        st["day"] = "2000-01-01"
        wf(kb_health.STATE_FILE, json.dumps(st))
        self.assertEqual(kb_health.counts()["restart"], 0)

    def test_notify_once(self):
        self.assertTrue(kb_health.notify_once("restart", "cap"))
        self.assertFalse(kb_health.notify_once("restart", "cap"))

    def test_snapshot_fields_and_classify(self):
        clock = [time.time() - 400]
        kb_health.set_clock(lambda: clock[0])
        kb_health.set_state("stalled", "task: gather")
        kb_health.record_error("! token=abcdef123456 failed")
        h = kb_health.snapshot({"cpu_percent": 50, "memory_percent": 60, "disk_free_gb": 1.5, "disk_total_gb": 100})
        for k in ("heartbeat_age", "process_state", "cpu_percent", "memory_percent", "disk_free_gb", "last_error",
                  "level", "issues", "restarts_today", "uptime_s"):
            self.assertIn(k, h)
        self.assertGreaterEqual(h["heartbeat_age"], 399)
        self.assertEqual(h["level"], "critical")
        self.assertIn("stalled", h["issues"])
        self.assertIn("disk_low", h["issues"])
        self.assertNotIn("abcdef123456", h["last_error"]["text"])
        pub = kb_health.public(h)
        self.assertNotIn("last_error", pub)
        self.assertNotIn("task", pub)
        self.assertIn("last_error_age_s", pub)
        clock[0] = time.time()
        kb_health.set_state("waiting")
        h2 = kb_health.snapshot({"cpu_percent": 10, "memory_percent": 20, "disk_free_gb": 50})
        self.assertIn(h2["level"], ("ok", "warn"))               # "warn" only because of the recent error
        kb_health.set_clock(None)

    def test_paused_bot_is_not_unhealthy(self):
        h = {"heartbeat_age": 5000, "process_state": "paused", "disk_free_gb": 40}
        self.assertEqual(kb_health.classify(h)[0], "ok")

    def test_sys_metrics_shape(self):
        kb_health.sys_metrics()
        m = kb_health.sys_metrics()
        self.assertIn("disk_free_gb", m)
        if "cpu_percent" in m:
            self.assertTrue(0 <= m["cpu_percent"] <= 100)


# ------------------------------------------------------------------ SEC-03: stream password
class StreamPassword(Tmp):
    def setUp(self):
        super().setUp()
        import server_config
        self.sc = server_config
        self._lj, self._le = server_config.LOCAL_JSON, server_config.LOCAL_ENV
        server_config.LOCAL_JSON, server_config.LOCAL_ENV = self.p("local_config.json"), self.p(".env")
        server_config._local.update(data=None, mtime=None)

    def tearDown(self):
        self.sc.LOCAL_JSON, self.sc.LOCAL_ENV = self._lj, self._le
        self.sc._local.update(data=None, mtime=None)
        super().tearDown()

    def _fresh(self):
        import importlib
        sys.modules.pop("stream_bot", None)
        return importlib.import_module("stream_bot")

    def test_generated_once_and_kept_local(self):
        wf(self.p("local_config.json"), '{"SERVER_ID": "vps-03-farms"}')
        sb = self._fresh()
        pw = sb.STREAM_PW
        self.assertGreaterEqual(len(pw), 12)
        self.assertNotIn("ct1q", pw)
        cfg = rj(self.p("local_config.json"))
        self.assertEqual(cfg["STREAM_PASSWORD"], pw)
        self.assertEqual(cfg["SERVER_ID"], "vps-03-farms")            # other settings kept
        self.sc._local.update(data=None, mtime=None)
        self.assertEqual(self._fresh().STREAM_PW, pw)                  # stable across restarts
        self.assertIn(pw, sb.PUSH_URL)
        self.assertIn(pw, sb.VIEW_URL)
        self.assertNotIn(pw, kb_secure.redact("log line " + sb.VIEW_URL))

    def test_own_password_respected(self):
        wf(self.p("local_config.json"), '{"STREAM_PASSWORD": "mine-123456"}')
        self.assertEqual(self._fresh().STREAM_PW, "mine-123456")



# ------------------------------------------------------------------ SEC-02/03/04: updater
class Updater(Tmp):
    def setUp(self):
        super().setUp()
        import updater
        self.u = updater
        self._base, self._vf, self._gh = updater.BASE, updater.VERSION_FILE, updater._gh
        updater.BASE = self.d
        updater.VERSION_FILE = self.p("version.json")
        wf(self.p("version.json"), '{"version": 250}')
        wf(self.p("bot.py"), "print('old')\n")
        wf(self.p("local_config.json"), '{"SERVER_ID": "vps-02-pilot"}')
        wf(self.p("smart_schedule_state.json"), '{"day": "keep"}')

    def tearDown(self):
        self.u.BASE, self.u.VERSION_FILE, self.u._gh = self._base, self._vf, self._gh
        super().tearDown()

    def _zip(self, files):
        import io, zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for name, data in files.items():
                z.writestr("kingbot-abc123/" + name, data)
        return b.getvalue()

    def test_zip_slip_refused(self):
        self.u._gh = lambda url, raw=False: self._zip({"bot.py": "print('new')\n", "../evil.py": "x = 1\n"})
        self.assertFalse(self.u._install_github(251, "abc123", LOGS.append))
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.d), "evil.py")))
        with open(self.p("bot.py")) as f:
            self.assertEqual(f.read(), "print('old')\n")
        self.assertEqual(rj(self.p("version.json"))["version"], 250)

    def test_update_keeps_runtime_files(self):
        self.u._gh = lambda url, raw=False: self._zip({
            "bot.py": "print('new')\n", "kb_new.py": "y = 2\n", "local_config.json": "{}",
            "smart_schedule_state.json": '{"day": "overwritten"}', "tests/test_x.py": "z = 3\n",
            "version.json": '{"version": 251}'})
        self.assertTrue(self.u._install_github(251, "abc123", LOGS.append))
        with open(self.p("bot.py")) as f:
            self.assertEqual(f.read(), "print('new')\n")
        self.assertTrue(os.path.exists(self.p("kb_new.py")))
        self.assertEqual(rj(self.p("local_config.json")), {"SERVER_ID": "vps-02-pilot"})
        self.assertEqual(rj(self.p("smart_schedule_state.json")), {"day": "keep"})
        self.assertFalse(os.path.exists(self.p("tests", "test_x.py")))
        self.assertEqual(rj(self.p("version.json"))["version"], 251)
        self.assertTrue(os.path.exists(self.p("backup_v250", "bot.py")))

    def test_is_runtime(self):
        for r in ("rotation_state.json", "backups/x.json.bak", "templates/a.png", "telegram_owner.txt", "log.txt"):
            self.assertTrue(self.u.is_runtime(r), r)
        for r in ("bot.py", "kb_safeio.py", "builtin_templates/a.png", "tasks.json", "packaging/build_protected.py"):
            self.assertFalse(self.u.is_runtime(r), r)



# ------------------------------------------------------------------ SEC-04: integrity & packaging
class Integrity(Tmp):
    def setUp(self):
        super().setUp()
        import kb_integrity, kb_paths
        self.ki, self.kp = kb_integrity, kb_paths
        self._base, self._code, self._man = kb_integrity.BASE, kb_integrity.CODE, kb_integrity.MANIFEST
        kb_integrity.BASE = kb_integrity.CODE = self.d
        kb_integrity.MANIFEST = self.p("integrity.json")

    def tearDown(self):
        self.ki.BASE, self.ki.CODE, self.ki.MANIFEST = self._base, self._code, self._man
        super().tearDown()

    def test_manifest_roundtrip_and_tamper(self):
        wf(self.p("a.py"), "x = 1\n")
        wf(self.p("b.py"), "y = 2\n")
        out, n = self.ki.build_manifest(code_dir=self.d, out=self.p("integrity.json"))
        self.assertEqual(n, 2)
        warns, checked = self.ki.verify_manifest()
        self.assertEqual((warns, checked), ([], 2))
        wf(self.p("b.py"), "y = 999\n")                         # tampered / half-updated
        warns, checked = self.ki.verify_manifest()
        self.assertTrue(any("b.py" in w and "changed" in w for w in warns))
        os.remove(self.p("a.py"))
        warns, _ = self.ki.verify_manifest()
        self.assertTrue(any("a.py" in w and "missing" in w for w in warns))

    def test_no_manifest_is_silent(self):
        self.assertEqual(self.ki.verify_manifest(), ([], 0))

    def test_dirs_created(self):
        self.assertEqual(self.ki.check_dirs(), [])
        for d in self.kp.MUTABLE_DIRS:
            self.assertTrue(os.path.isdir(self.p(d)), d)

    def test_python_and_disk_ok_here(self):
        self.assertEqual(self.ki.check_python(), [])
        self.assertEqual(self.ki.check_disk(), [])

    def test_missing_core_module_detected(self):
        # CODE has no bot.py etc. -> check_core_modules reports them (script mode)
        probs = self.ki.check_core_modules()
        self.assertTrue(probs and "common.py" in probs[0])

    def test_startup_check_fatal_raises(self):
        import kb_integrity
        orig = kb_integrity.run_checks
        kb_integrity.run_checks = lambda: (["boom"], ["careful"])
        try:
            with self.assertRaises(SystemExit) as cm:
                kb_integrity.startup_check(LOGS.append)
            self.assertEqual(cm.exception.code, 2)
            self.assertTrue(any("boom" in m for m in LOGS))
            self.assertTrue(any("careful" in m for m in LOGS))
        finally:
            kb_integrity.run_checks = orig

    def test_startup_check_passes_when_clean(self):
        import kb_integrity
        orig = kb_integrity.run_checks
        kb_integrity.run_checks = lambda: ([], [])
        try:
            self.assertTrue(kb_integrity.startup_check(LOGS.append))
        finally:
            kb_integrity.run_checks = orig


class Paths(Tmp):
    def test_base_dir_script_mode(self):
        import kb_paths
        self.assertEqual(kb_paths.base_dir("/x/y/z.py"), os.path.dirname(os.path.abspath("/x/y/z.py")))

    def test_kingbot_home_wins(self):
        import kb_paths
        old = os.environ.get("KINGBOT_HOME")
        os.environ["KINGBOT_HOME"] = self.d
        try:
            self.assertEqual(kb_paths.base_dir("/whatever.py"), os.path.abspath(self.d))
        finally:
            os.environ.pop("KINGBOT_HOME", None)
            if old is not None:
                os.environ["KINGBOT_HOME"] = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
