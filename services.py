"""Background data sources: weather (Open-Meteo), calendar (iCal link),
now-playing (Windows media session). Each runs in its own daemon thread and
exposes plain attributes the UI reads once a second."""
import asyncio
import json
import re
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


def http_get(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "Winyard/0.2"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# -------------------------------------------------------------- weather ----
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


class WeatherService:
    def __init__(self, cfg, save):
        self.cfg, self.save = cfg, save
        self.label = "WEATHER"
        self.text = "Set city"
        self._wake = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def refresh(self):
        self._wake.set()

    def _run(self):
        while True:
            try:
                self._update()
            except Exception:
                self.text = "Offline"
            self._wake.wait(900)
            self._wake.clear()

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


# ------------------------------------------------------------- calendar ----
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


def parse_ics(text):
    lines = re.sub(r"\r?\n[ \t]", "", text).splitlines()
    events, cur = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur and "start" in cur and not cur.get("allday"):
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


class CalendarService:
    def __init__(self, cfg):
        self.cfg = cfg
        self.upcoming = []          # sorted [(datetime, summary)]
        self.status = ""
        self._events, self._url, self._fetched = [], None, 0.0
        self._wake = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def refresh(self):
        self._url = None
        self._wake.set()

    def next_event(self):
        cutoff = datetime.now() - timedelta(seconds=60)
        for dt, title in self.upcoming:
            if dt >= cutoff:
                return dt, title
        return None

    def _run(self):
        import time
        while True:
            try:
                url = self.cfg.get("calendar_url", "").strip()
                if url.startswith("webcal://"):
                    url = "https://" + url[len("webcal://"):]
                if not url:
                    self._events, self.upcoming, self.status = [], [], "Set link"
                elif url != self._url or time.time() - self._fetched > 900:
                    self._events = parse_ics(http_get(url, timeout=20))
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
            self._wake.clear()


# ---------------------------------------------------------------- media ----
class MediaService:
    """Now-playing via the Windows media session (needs: pip install winsdk)."""

    def __init__(self):
        self.available = False
        self.title = self.artist = ""
        self.playing = False
        self.has_session = False
        self.loop = None
        try:
            import winsdk.windows.media.control  # noqa: F401
            self.available = True
            threading.Thread(target=self._run, daemon=True).start()
        except Exception:
            pass

    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._poll())

    async def _session(self):
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Mgr)
        return (await Mgr.request_async()).get_current_session()

    async def _poll(self):
        from winsdk.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PS)
        while True:
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
        if self.loop:
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
