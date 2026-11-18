"""Background data sources: weather (Open-Meteo), calendar (iCal link),
now-playing (Windows media session). Each runs in its own daemon thread and
exposes plain attributes the UI reads once a second."""
import asyncio
import importlib
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


def http_get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "WindowsBar/0.2"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


class _LifecycleService:
    """Run a polling worker only while its owning widget is enabled."""

    def __init__(self, worker_available=True):
        self._active = False
        self._worker_available = worker_available
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._lifecycle_lock = threading.Lock()

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, enabled):
        enabled = bool(enabled)
        with self._lifecycle_lock:
            self._active = enabled
            if enabled:
                self._stop.clear()
                if (self._worker_available
                        and (self._thread is None or not self._thread.is_alive())):
                    self._start_worker_locked()
                self._wake.set()
            else:
                self._stop.set()
                self._wake.set()
                loop = getattr(self, "loop", None)
                task = getattr(self, "_task", None)
                if loop and task and loop.is_running():
                    loop.call_soon_threadsafe(task.cancel)

    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def _start_worker_locked(self):
        self._thread = threading.Thread(
            target=self._thread_main, name=type(self).__name__, daemon=True)
        self._thread.start()

    def _thread_main(self):
        try:
            self._run()
        finally:
            with self._lifecycle_lock:
                self._thread = None
                if self._active and self._worker_available:
                    self._stop.clear()
                    self._start_worker_locked()


# weather
def wmo_text(code):
    if code == 0: return "Clear"
    if code in (1, 2): return "Partly cloudy"
    if code == 3: return "Overcast"
    if code in (45, 48): return "Fog"
    if 51 <= code <= 57: return "Drizzle"
    if 61 <= code <= 67 or 80 <= code <= 82: return "Rain"
    if 71 <= code <= 77 or code in (85, 86): return "Snow"
    if code >= 95: return "Thunderstorm"
    return "—"


class WeatherService(_LifecycleService):
    def __init__(self, cfg, save):
        self.cfg, self.save = cfg, save
        self.label = "WEATHER"
        self.text = "Set city"
        super().__init__()

    def refresh(self):
        self._wake.set()

    def _run(self):
        while not self._stop.is_set():
            self._wake.clear()
            try:
                self._update()
            except Exception:
                self.text = "Offline"
            self._wake.wait(900)

    def _update(self):
        city = self.cfg.get("weather_city", "").strip()
        if not city:
            self.label, self.text = "WEATHER", "Click to set city"
            return
        geo = self.cfg.get("weather_geo")
        if not geo or geo.get("city") != city:
            q = urllib.parse.urlencode({"name": city, "count": 1})
            res = json.loads(http_get(
                "https://geocoding-api.open-meteo.com/v1/search?" + q))
            if not res.get("results"):
                self.label, self.text = "WEATHER", "City not found"
                return
            r = res["results"][0]
            geo = {"city": city, "lat": r["latitude"], "lon": r["longitude"],
                   "name": r.get("name", city)}
            self.cfg["weather_geo"] = geo
            self.save()
        q = urllib.parse.urlencode({
            "latitude": geo["lat"], "longitude": geo["lon"],
            "current": "temperature_2m,weather_code", "timezone": "auto"})
        cur = json.loads(http_get(
            "https://api.open-meteo.com/v1/forecast?" + q))["current"]
        self.label = geo.get("name", city).upper()
        self.text = f"{cur['temperature_2m']:.0f}°C {wmo_text(cur['weather_code'])}"


# calendar
WD = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _parse_dt(value, params=""):
    value = value.strip()
    if "VALUE=DATE" in params or len(value) == 8:
        return datetime.strptime(value[:8], "%Y%m%d"), True
    utc = value.endswith("Z")
    dt = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
    if utc:
        dt = dt.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    return dt, False   # TZID-tagged times are treated as local time


def _unfold(text):
    """Yield iCal lines with RFC 5545 continuation lines joined."""
    cur = None
    for n, raw in enumerate(text.splitlines()):
        if raw[:1] in (" ", "\t") and cur is not None:
            cur += raw[1:]
        else:
            if cur is not None:
                yield cur
            cur = raw
        if n % 4000 == 3999:
            time.sleep(0.001)          # let the UI thread run on huge calendars
    if cur is not None:
        yield cur


def parse_ics(text, drop_before=None):
    """Timed events only. With drop_before, one-off events that started before
    that moment are discarded early (calendars keep years of history)."""
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur and "start" in cur and not cur.get("allday"):
                if not (drop_before and "rrule" not in cur
                        and cur["start"] < drop_before):
                    events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, _, value = line.partition(":")
            name, _, params = key.partition(";")
            name = name.upper()
            if name == "DTSTART":
                try:
                    cur["start"], cur["allday"] = _parse_dt(value, params)
                except ValueError:
                    pass
            elif name == "SUMMARY":
                cur["summary"] = value.replace("\\,", ",").replace("\\;", ";")
            elif name == "RRULE":
                cur["rrule"] = value
    return events


def occurrences(ev, now, end):
    """Approximate recurrence expansion (DAILY/WEEKLY/MONTHLY/YEARLY with
    INTERVAL, BYDAY, UNTIL). COUNT, EXDATE and edited instances are ignored."""
    start, rule = ev["start"], ev.get("rrule")
    if not rule:
        return [start] if now <= start <= end else []
    parts = dict(p.split("=", 1) for p in rule.split(";") if "=" in p)
    freq = parts.get("FREQ")
    interval = int(parts.get("INTERVAL", "1") or 1)
    until = None
    if "UNTIL" in parts:
        try:
            until = _parse_dt(parts["UNTIL"])[0]
        except ValueError:
            pass
    byday = [WD[re.sub(r"[+\-\d]", "", x)] for x in
             parts.get("BYDAY", "").split(",")
             if re.sub(r"[+\-\d]", "", x) in WD]
    s_monday = start.date() - timedelta(days=start.weekday())

    def matches(d):
        if freq == "DAILY":
            return (d - start.date()).days % interval == 0
        if freq == "WEEKLY":
            weeks = (d - timedelta(days=d.weekday()) - s_monday).days // 7
            return weeks % interval == 0 and d.weekday() in (
                byday or [start.weekday()])
        if freq == "MONTHLY":
            months = (d.year - start.year) * 12 + d.month - start.month
            return d.day == start.day and months % interval == 0
        if freq == "YEARLY":
            return ((d.month, d.day) == (start.month, start.day)
                    and (d.year - start.year) % interval == 0)
        return False

    out, d = [], max(now.date(), start.date())
    while d <= end.date():
        t = datetime.combine(d, start.time())
        if (now <= t <= end and t >= start and (until is None or t <= until)
                and matches(d)):
            out.append(t)
        d += timedelta(days=1)
    return out


class CalendarService(_LifecycleService):
    def __init__(self, cfg):
        self.cfg = cfg
        self.upcoming = []          # sorted [(datetime, summary)]
        self.status = ""
        self._events, self._url, self._fetched = [], None, 0.0
        super().__init__()

    def refresh(self):
        self._url = None
        self._wake.set()

    def next_event(self):
        cutoff = datetime.now() - timedelta(seconds=60)
        for dt, title in self.upcoming:
            if dt >= cutoff:
                return dt, title
        return None

    def events_in_month(self, year, month):
        """{day: [(time, title)]} for the given month -- month popup."""
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        out = {}
        for ev in self._events:
            for t in occurrences(ev, start, end - timedelta(seconds=1)):
                out.setdefault(t.day, []).append(
                    (t, ev.get("summary", "(no title)")))
        for day in out:
            out[day].sort()
        return out

    def _run(self):
        while not self._stop.is_set():
            self._wake.clear()
            try:
                url = self.cfg.get("calendar_url", "").strip()
                if url.startswith("webcal://"):
                    url = "https://" + url[len("webcal://"):]
                if not url:
                    self._events, self.upcoming, self.status = [], [], "Set link"
                elif url != self._url or time.time() - self._fetched > 900:
                    self._events = parse_ics(http_get(url, timeout=20),
                                             drop_before=datetime.now() - timedelta(days=1))
                    self._url, self._fetched = url, time.time()
                    self.status = ""
                now = datetime.now()
                end = now + timedelta(days=14)
                ups = []
                for ev in self._events:
                    for t in occurrences(ev, now - timedelta(minutes=1), end):
                        ups.append((t, ev.get("summary", "(no title)")))
                self.upcoming = sorted(ups)
            except Exception:
                self.status = "Calendar error"
            self._wake.wait(60)


# media
def _media_api():
    """(SessionManager, PlaybackStatus) from `winsdk`, or from its maintained
    successor `winrt`; None when neither is installed."""
    for root in ("winsdk", "winrt"):
        try:
            try:
                importlib.import_module(f"{root}.windows.foundation.collections")
            except Exception:
                pass
            mod = importlib.import_module(f"{root}.windows.media.control")
            return (mod.GlobalSystemMediaTransportControlsSessionManager,
                    mod.GlobalSystemMediaTransportControlsSessionPlaybackStatus)
        except Exception:
            continue
    return None

class MediaService(_LifecycleService):
    """Now-playing via the Windows media session (needs winsdk or winrt)."""

    def __init__(self):
        self.available = False
        self.title = self.artist = ""
        self.playing = False
        self.has_session = False
        self.loop = None
        self._task = None
        self._api = _media_api()
        super().__init__(worker_available=bool(self._api))
        self.available = bool(self._api)

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._task = self.loop.create_task(self._poll())
        try:
            self.loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass
        finally:
            self.loop.close()
            self.loop = None
            self._task = None

    async def _session(self):
        Mgr = self._api[0]
        return (await Mgr.request_async()).get_current_session()

    async def _poll(self):
        PS = self._api[1]
        while not self._stop.is_set():
            try:
                s = await self._session()
                if s is None:
                    self.has_session, self.playing = False, False
                else:
                    props = await s.try_get_media_properties_async()
                    info = s.get_playback_info()
                    self.title = props.title or ""
                    self.artist = props.artist or ""
                    self.playing = info.playback_status == PS.PLAYING
                    self.has_session = True
            except Exception:
                self.has_session = False
            await asyncio.sleep(2)

    def _submit(self, coro_fn):
        if self.active and self.loop:
            asyncio.run_coroutine_threadsafe(coro_fn(), self.loop)

    def toggle(self):
        async def go():
            s = await self._session()
            if s:
                await s.try_toggle_play_pause_async()
        self._submit(go)

    def pause(self):
        async def go():
            s = await self._session()
            if s:
                await s.try_pause_async()
        self._submit(go)


# radios
def _radios_api():
    """(Radio, RadioKind, RadioState) from winsdk or winrt; None if absent."""
    for root in ("winsdk", "winrt"):
        try:
            try:
                importlib.import_module(f"{root}.windows.foundation.collections")
            except Exception:
                pass
            mod = importlib.import_module(f"{root}.windows.devices.radios")
            return mod.Radio, mod.RadioKind, mod.RadioState
        except Exception:
            continue
    return None


class RadioService(_LifecycleService):
    """Wi-Fi / Bluetooth radio states via WinRT (the Quick toggles widget).
    `states` maps 'wifi' / 'bluetooth' -> True/False; missing keys mean the
    radio (or the API) is not available, and the toggle hides itself."""

    def __init__(self):
        self.available = False
        self.states = {}
        self.loop = None
        self._task = None
        self._api = _radios_api()
        self._radios = {}
        super().__init__(worker_available=bool(self._api))
        self.available = bool(self._api)

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._task = self.loop.create_task(self._poll())
        try:
            self.loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass
        finally:
            self.loop.close()
            self.loop = None
            self._task = None

    async def _poll(self):
        Radio, RadioKind, RadioState = self._api
        while not self._stop.is_set():
            try:
                await Radio.request_access_async()
                radios = await Radio.get_radios_async()
                found = {}
                for r in radios:
                    key = None
                    if r.kind == RadioKind.WIFI:
                        key = "wifi"
                    elif r.kind == RadioKind.BLUETOOTH:
                        key = "bluetooth"
                    if key:
                        self._radios[key] = r
                        found[key] = r.state == RadioState.ON
                self.states = found
            except Exception:
                self.states = {}
            await asyncio.sleep(4)

    def set(self, key, on):
        """Toggle one radio; airplane=True turns every radio off/on."""
        async def go():
            _R, _K, RadioState = self._api
            targets = list(self._radios.values()) if key == "airplane" \
                else [self._radios.get(key)]
            for r in targets:
                if r is not None:
                    try:
                        await r.set_state_async(
                            RadioState.ON if on else RadioState.OFF)
                    except Exception:
                        pass
        if self.active and self.loop:
            asyncio.run_coroutine_threadsafe(go(), self.loop)
