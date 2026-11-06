"""Extra data sources: screen time, GitHub, Stripe revenue, Downloads,
Recycle Bin and a generic background poller."""
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import winapi

IDLE_LIMIT = 300  # seconds without input before screen time pauses


def get_json(url, headers=None, timeout=10):
    req = urllib.request.Request(
        url, headers={"User-Agent": "WindowsBar/0.3", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Poll:
    """Runs fetch() every `every` seconds in a thread. Read .value or .error."""

    def __init__(self, fetch, every):
        self.fetch, self.every = fetch, every
        self.value, self.error = None, None
        self._wake = threading.Event()
        self._stop = False
        threading.Thread(target=self._run, daemon=True).start()

    def refresh(self):
        self._wake.set()

    def stop(self):
        self._stop = True
        self._wake.set()

    def _run(self):
        while not self._stop:
            try:
                self.value = self.fetch()
                self.error = None
            except Exception as e:
                self.error = (str(e) or e.__class__.__name__)[:60]
            self._wake.wait(self.every)
            self._wake.clear()


def github_summary(user):
    if not user:
        raise ValueError("Set GitHub user")
    d = get_json("https://api.github.com/users/" + urllib.parse.quote(user))
    return f"{d['public_repos']} repos · {d['followers']} followers"


def stripe_revenue(key):
    if not key:
        raise ValueError("Set WINDOWSBAR_STRIPE_KEY")
    d = get_json("https://api.stripe.com/v1/balance",
                 headers={"Authorization": "Bearer " + key})
    totals = {}
    for item in d.get("available", []):
        cur = item["currency"]
        totals[cur] = totals.get(cur, 0) + item["amount"]
    if not totals:
        return "0 available"
    cur, cents = max(totals.items(), key=lambda kv: kv[1])
    return f"{cents / 100:,.2f} {cur.upper()} available"


def downloads_summary(folder=None):
    """Returns (files added in last 24h, newest file name)."""
    folder = Path(folder) if folder else Path.home() / "Downloads"
    if not folder.is_dir():
        return 0, None
    cutoff = time.time() - 86400
    files = []
    for e in os.scandir(folder):
        if e.is_file():
            files.append((e.stat().st_mtime, e.name))
    recent = sum(1 for m, _ in files if m >= cutoff)
    newest = max(files)[1] if files else None
    return recent, newest


def fmt_dur(seconds):
    h, m = divmod(int(seconds) // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


# ------------------------------------------------------- extra sources ----
def disk_summary(path=None):
    """(percent_used, free_bytes, total_bytes) for a drive (default C:)."""
    import psutil
    u = psutil.disk_usage(path or os.environ.get("SystemDrive", "C:") + "\\")
    return u.percent, u.free, u.total


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def period_progress(now=None):
    """{'day': 0..1, 'week': 0..1, 'year': 0..1} -- how far through each
    period we are. Week starts on Monday."""
    from datetime import datetime
    now = now or datetime.now()
    day = (now.hour * 3600 + now.minute * 60 + now.second) / 86400
    week = (now.weekday() + day) / 7
    start = now.replace(month=1, day=1, hour=0, minute=0, second=0,
                        microsecond=0)
    nxt = start.replace(year=start.year + 1)
    year = (now - start).total_seconds() / (nxt - start).total_seconds()
    return {"day": day, "week": week, "year": year}


def run_script(command, timeout=30):
    """Run a shell command and return its stdout (the Script widget's data).
    A command that hangs is killed after `timeout` seconds."""
    import subprocess
    if not (command or "").strip():
        raise ValueError("Set a script command")
    out = subprocess.run(command, shell=True, capture_output=True,
                         timeout=timeout)
    text = out.stdout.decode("utf-8", errors="replace").strip()
    if not text and out.returncode != 0:
        err = out.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(err.splitlines()[-1][:60] if err
                         else f"exit {out.returncode}")
    return text


def network_info():
    """(ssid_or_adapter, ipv4) for the active connection, best effort."""
    import subprocess
    name = ""
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                             capture_output=True, timeout=8).stdout
        for line in out.decode("utf-8", errors="replace").splitlines():
            if line.strip().lower().startswith("ssid") and ":" in line \
                    and "bssid" not in line.lower():
                name = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass
    ip = ""
    try:
        import psutil
        for _iface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == 2 and not a.address.startswith(("127.", "169.")):
                    ip = a.address
                    break
            if ip:
                break
    except Exception:
        pass
    return name, ip


def normalize_todos(raw):
    """Todos used to be a list of strings; now they are {'t', 'done'} dicts.
    Accepts both, returns the new shape (open items first is NOT enforced
    here -- order is the user's)."""
    out = []
    for item in raw or []:
        if isinstance(item, str):
            out.append({"t": item, "done": False})
        elif isinstance(item, dict) and item.get("t"):
            out.append({"t": str(item["t"]), "done": bool(item.get("done"))})
    return out


def normalize_notes(legacy_text, raw_list, current=0):
    """Notes used to be one big string; now a list of note strings.
    Returns (notes, current_index) with the legacy text as the first note."""
    notes = [str(n) for n in (raw_list or [])]
    if not notes and (legacy_text or "").strip():
        notes = [legacy_text]
    if not notes:
        notes = [""]
    current = min(max(int(current or 0), 0), len(notes) - 1)
    return notes, current


class ScreenTime:
    """Counts seconds per focused app per day. Idle time is not counted.
    `sampler` and `idle` are injectable so this can be tested anywhere."""

    def __init__(self, path, sampler=winapi.foreground_process,
                 idle=winapi.idle_seconds, start=True):
        self.path = Path(path)
        self.sampler, self.idle = sampler, idle
        self.lock = threading.Lock()
        self.data = self._load()
        self._n = 0
        if start:
            threading.Thread(target=self._run, daemon=True).start()

    def _load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def flush(self):
        with self.lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(self.data), encoding="utf-8")
            except Exception:
                pass

    def sample(self):
        if self.idle() > IDLE_LIMIT:
            return
        name = self.sampler()
        if not name:
            return
        today = date.today()
        with self.lock:
            day = self.data.setdefault(today.isoformat(), {})
            day[name] = day.get(name, 0) + 1
            cutoff = (today - timedelta(days=14)).isoformat()
            for k in [k for k in self.data if k < cutoff]:
                del self.data[k]
            self._n += 1
            save_now = self._n % 30 == 0
        if save_now:
            self.flush()

    def today(self, n=3):
        with self.lock:
            day = dict(self.data.get(date.today().isoformat(), {}))
        total = sum(day.values())
        top = sorted(day.items(), key=lambda kv: -kv[1])[:n]
        return total, top

    def _run(self):
        while True:
            try:
                self.sample()
            except Exception:
                pass
            time.sleep(1)
