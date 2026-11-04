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
        url, headers={"User-Agent": "Winyard/0.3", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Poll:
    """Runs fetch() every `every` seconds in a thread. Read .value or .error."""

    def __init__(self, fetch, every):
        self.fetch, self.every = fetch, every
        self.value, self.error = None, None
        self._wake = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def refresh(self):
        self._wake.set()

    def _run(self):
        while True:
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
        raise ValueError("Set WINYARD_STRIPE_KEY")
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
