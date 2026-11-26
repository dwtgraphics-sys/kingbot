# -*- coding: utf-8 -*-
"""
SEC-02: safe file persistence for Kingbot (atomic writes, locks, validation, rolling backups).

Why: a power cut, a Windows update reboot, Google Drive / antivirus holding a file, or two threads
writing the same file could leave a JSON file half-written. The old loader then silently returned
the default ({}), and the next save overwrote the real data with that default - progress lost.

What this module does
  atomic_write_bytes / atomic_write_json
      write to a unique temp file -> flush() -> os.fsync() -> os.replace() over the real file.
      A reader always sees either the old complete file or the new complete file, never half.
      Retries ride over short "file is in use" locks (Google Drive / antivirus on the VPS).
  FileLock / update_json
      a lock file (create-exclusive) around read-modify-write, shared by every process
      (bot.py, stream_bot.py, telegram thread). A stale lock (crashed process) is taken over,
      and a lock that cannot be taken in time never blocks the bot - it logs and continues.
  safe_load_json
      a missing file -> default (same as before). A damaged/empty file -> it is kept aside as
      backups/<name>.corrupt-<time>, the newest valid backup is restored, and a warning is logged.
  rolling backups
      before a file is replaced, its last good version is copied to backups/<name>.<time>.json
      (at most once every BACKUP_EVERY seconds per file, newest KEEP copies kept).
  schemas
      a few files have a known shape (SCHEMAS). A save whose data does not match is refused and
      logged, so a bug can never replace a good file with garbage.

No Windows-only imports: the module also runs (and is tested) on Linux.
"""
import os, json, time, glob, shutil, threading, datetime

import kb_paths
BASE = kb_paths.base_dir(__file__)   # SEC-04
BACKUP_DIRNAME = "backups"          # git-ignored
KEEP = 5                            # rolling backups kept per file
BACKUP_EVERY = 600                  # seconds: at most one backup of the same file per 10 minutes
LOCK_TIMEOUT = 8.0                  # seconds to wait for another writer
LOCK_STALE = 60.0                   # a lock file older than this belongs to a crashed process

LOG = [None]                        # common.py sets this to log_raw (no import cycle)

_mem_locks = {}
_mem_guard = threading.Lock()
_last_backup = {}

# basename -> (type, required keys). Conservative on purpose: only files whose shape is certain.
SCHEMAS = {
    "version.json": (dict, ("version",)),
    "tasks.json": (dict, ("tasks",)),
    "routines.json": (dict, ()),
    "recovery_state.json": (dict, ("day",)),
    "local_config.json": (dict, ()),
    "smart_schedule_state.json": (dict, ()),
    "rotation_state.json": (dict, ()),
}


def _log(msg):
    fn = LOG[0]
    try:
        if fn:
            fn(msg)
        else:
            print(msg, flush=True)
    except Exception:
        pass


def _mem_lock(path):
    key = os.path.normcase(os.path.abspath(path))
    with _mem_guard:
        lk = _mem_locks.get(key)
        if lk is None:
            lk = _mem_locks[key] = threading.RLock()
        return lk


def _fsync_dir(d):
    """POSIX: make the rename itself durable. Windows has no directory fsync (NTFS journals it)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        pass


# ------------------------------------------------------------------ validation
def validate(path, data):
    """(ok, reason). Only files listed in SCHEMAS are checked; everything else passes."""
    sch = SCHEMAS.get(os.path.basename(path))
    if not sch:
        return True, ""
    typ, required = sch
    if not isinstance(data, typ):
        return False, f"expected {typ.__name__}, got {type(data).__name__}"
    missing = [k for k in required if k not in data]
    if missing:
        return False, "missing key(s): " + ", ".join(missing)
    return True, ""


# ------------------------------------------------------------------ backups
def backup_dir(path):
    return os.path.join(os.path.dirname(os.path.abspath(path)), BACKUP_DIRNAME)


def _stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def list_backups(path):
    """Newest first."""
    name = os.path.basename(path)
    found = glob.glob(os.path.join(backup_dir(path), glob.escape(name) + ".2*.bak"))
    return sorted(found, reverse=True)


def backup(path, force=False):
    """Copy the current file (only if it is valid) to backups/, keep the newest KEEP. Never raises."""
    try:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            return None
        key = os.path.normcase(os.path.abspath(path))
        now = time.time()
        if not force and now - _last_backup.get(key, 0) < BACKUP_EVERY:
            return None
        if path.endswith(".json"):
            try:
                with open(path, encoding="utf-8-sig") as f:
                    json.load(f)
            except Exception:
                return None                          # never back up a damaged file over good backups
        d = backup_dir(path)
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f"{os.path.basename(path)}.{_stamp()}.bak")
        shutil.copy2(path, dst)
        _last_backup[key] = now
        for old in list_backups(path)[KEEP:]:
            try:
                os.remove(old)
            except Exception:
                pass
        return dst
    except Exception as e:
        _log(f"  ! backup of {os.path.basename(path)} failed: {e!r}")
        return None


# ------------------------------------------------------------------ atomic writes
def atomic_write_bytes(path, data, retries=5, make_backup=False):
    """temp file -> flush -> fsync -> os.replace. True on success, False after all retries."""
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    with _mem_lock(path):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        if make_backup:
            backup(path)
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        last = None
        for attempt in range(retries):
            try:
                with open(tmp, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
                _fsync_dir(d)
                return True
            except OSError as e:                     # PermissionError / sharing violation / disk full
                last = e
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                time.sleep(0.4 * (attempt + 1))
        _log(f"  ! could not save {os.path.basename(path)}: {last!r}")
        return False


def atomic_write_text(path, text, **kw):
    return atomic_write_bytes(path, text.encode("utf-8"), **kw)


def atomic_write_json(path, data, indent=2, make_backup=True, check=True, **kw):
    """Validate (SCHEMAS), serialise, then write atomically with a rolling backup."""
    if check:
        ok, why = validate(path, data)
        if not ok:
            _log(f"  ! refused to save {os.path.basename(path)}: {why} (the file on disk was kept)")
            return False
    try:
        text = json.dumps(data, ensure_ascii=False, indent=indent)
    except (TypeError, ValueError) as e:
        _log(f"  ! refused to save {os.path.basename(path)}: not JSON-serialisable ({e})")
        return False
    return atomic_write_text(path, text, make_backup=make_backup, **kw)


# ------------------------------------------------------------------ loading with recovery
class _Corrupt(Exception):
    pass


def _parse(path):
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.strip():
        raise _Corrupt("empty file (an interrupted write)")
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as e:
        raise _Corrupt(str(e)[:120])


def _quarantine(path):
    try:
        d = backup_dir(path)
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f"{os.path.basename(path)}.corrupt-{_stamp()}")
        shutil.copy2(path, dst)
        for old in sorted(glob.glob(os.path.join(d, glob.escape(os.path.basename(path)) + ".corrupt-*")),
                          reverse=True)[3:]:
            os.remove(old)
        return dst
    except Exception:
        return None


def safe_load_json(path, default, required=None, restore=True):
    """Load JSON. Missing -> default. Damaged -> restore the newest valid backup (logged) or default.

    `required`: keys that must be present (else treated as damaged). Files in SCHEMAS are also checked.
    A file that is only briefly locked by another program is retried, not treated as missing.
    """
    if not os.path.exists(path):
        return default
    last_os = None
    for attempt in range(4):
        try:
            data = _parse(path)
            ok, why = validate(path, data)
            if ok and required:
                miss = [k for k in required if not isinstance(data, dict) or k not in data]
                ok, why = (not miss), ("missing key(s): " + ", ".join(miss) if miss else "")
            if not ok:
                raise _Corrupt(why)
            return data
        except _Corrupt as e:
            return _recover(path, default, str(e), restore)
        except FileNotFoundError:
            return default
        except OSError as e:                         # locked by Drive / antivirus: wait a moment
            last_os = e
            time.sleep(0.25 * (attempt + 1))
    _log(f"  ! {os.path.basename(path)} could not be read ({last_os!r}) - using the default for now")
    return default


def _recover(path, default, why, restore):
    name = os.path.basename(path)
    with _mem_lock(path):
        q = _quarantine(path)
        for b in list_backups(path):
            try:
                data = _parse(b)
                if not validate(path, data)[0]:
                    continue
            except Exception:
                continue
            if restore:
                with open(b, "rb") as f:
                    atomic_write_bytes(path, f.read())
            _log(f"! {name} was damaged ({why}) - restored the backup from "
                 f"{os.path.basename(b).split('.')[-2]}" + (f"; damaged copy kept in backups/" if q else ""))
            return data
        _log(f"! {name} was damaged ({why}) and no valid backup exists - starting from the default"
             + (f"; damaged copy kept in backups/" if q else ""))
        return default


# ------------------------------------------------------------------ cross-process lock
class FileLock:
    """Exclusive lock file next to `path`. Never deadlocks the bot: on timeout it logs and proceeds."""

    def __init__(self, path, timeout=LOCK_TIMEOUT, stale=LOCK_STALE):
        self.lockpath = os.path.abspath(path) + ".lock"
        self.timeout, self.stale, self.held = timeout, stale, False
        self._mem = _mem_lock(path)

    def __enter__(self):
        self._mem.acquire()
        end = time.time() + self.timeout
        while True:
            try:
                fd = os.open(self.lockpath, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, f"{os.getpid()} {time.time():.0f}".encode())
                finally:
                    os.close(fd)
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.lockpath) > self.stale:
                        os.remove(self.lockpath)         # the owner crashed: take over
                        continue
                except OSError:
                    pass
            except OSError:
                break                                    # e.g. read-only folder: work without the lock
            if time.time() > end:
                _log(f"  ! {os.path.basename(self.lockpath)} is busy for {self.timeout:.0f}s - continuing without it")
                break
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        try:
            if self.held:
                os.remove(self.lockpath)
        except OSError:
            pass
        self.held = False
        self._mem.release()
        return False


def update_json(path, fn, default=None, **kw):
    """Locked read-modify-write: data = fn(current) (or mutate in place and return None)."""
    with FileLock(path):
        cur = safe_load_json(path, {} if default is None else default)
        new = fn(cur)
        if new is None:
            new = cur
        atomic_write_json(path, new, **kw)
        return new
