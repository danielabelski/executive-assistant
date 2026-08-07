"""Weather via the US National Weather Service (api.weather.gov).

WHY NWS: free, no API key, no account — and the user is in Oregon.
(The API is US-only; the config validation notes this.)

Flow:
    1. Onboarding turns a ZIP code into lat/lon via zippopotam.us
       (also free, no key) and stores it in config.yaml — done once.
    2. WeatherClient asks NWS for the "gridpoint" for those coordinates
       (done once per process, then cached).
    3. The gridpoint gives us the forecast endpoint for the user's exact
       area, and we fetch the named periods (Today, Tonight, ...).

NWS etiquette: they ask every client to send a descriptive User-Agent.
Ours identifies the project + repo, per their API docs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import requests

NWS_BASE = "https://api.weather.gov"
ZIP_BASE = "https://api.zippopotam.us/us"
USER_AGENT = "(executive-assistant, github.com/drwjkirkpatrick-web/executive-assistant)"
TIMEOUT = 15  # seconds — weather should never hang a briefing


class WeatherError(Exception):
    """Raised when weather data can't be fetched; briefing shows a fallback."""


@dataclass
class Period:
    """One named forecast period (e.g. 'Today', 'Tonight')."""

    name: str
    short_forecast: str
    temperature: int
    temperature_unit: str
    is_daytime: bool
    precip_chance: int | None  # percent, or None if NWS didn't say

    def render(self) -> str:
        rain = f", {self.precip_chance}% precip" if self.precip_chance is not None else ""
        return f"{self.name}: {self.short_forecast}, {self.temperature}°{self.temperature_unit}{rain}"


def resolve_zip(zip_code: str) -> tuple[float, float, str]:
    """ZIP code → (latitude, longitude, 'City, ST') via zippopotam.us.

    Called once during onboarding; the result is stored in config.yaml so
    briefings never do this lookup again.
    """
    try:
        resp = requests.get(f"{ZIP_BASE}/{zip_code}", timeout=TIMEOUT)
        resp.raise_for_status()
        place = resp.json()["places"][0]
    except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
        raise WeatherError(f"Could not resolve ZIP {zip_code!r}: {exc}") from exc
    label = f"{place['place name']}, {place['state abbreviation']}"
    return float(place["latitude"]), float(place["longitude"]), label


def trend_arrow(today_high: float, yesterday_high: float) -> str:
    """'↑' warming, '↓' cooling, '→' flat — with a 1°F deadband so a
    half-degree wobble doesn't pretend to be a trend."""
    if today_high > yesterday_high + 1:
        return "↑"
    if today_high < yesterday_high - 1:
        return "↓"
    return "→"


def umbrella_line(hourly: list[tuple[str, int]], threshold: int = 30) -> str | None:
    """'Umbrella? 40% at 5 PM' for the FIRST hour over the precip threshold,
    or None when the whole window stays dry enough. One line is all a
    briefing has room for — the earliest risk is the actionable one."""
    for label, pct in hourly:
        if pct > threshold:
            return f"Umbrella? {pct}% at {label}"
    return None


def _hour_label(iso_start: str) -> str:
    """NWS ISO startTime ('2026-08-06T15:00:00-07:00') → '3 PM'.
    Falls back to the raw string if it isn't parseable ISO."""
    try:
        return datetime.fromisoformat(iso_start).strftime("%-I %p")
    except ValueError:
        return iso_start or "?"


class WeatherClient:
    """Fetches and formats the NWS forecast for configured coordinates."""

    def __init__(self, lat: float, lon: float, label: str = ""):
        self.lat, self.lon, self.label = lat, lon, label
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
        self._forecast_url: str | None = None  # cached after first lookup
        self._hourly_url: str | None = None    # ditto
        self.last_error: str | None = None     # set by the never-raise methods

    def _get(self, url: str) -> dict:
        try:
            resp = self._session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise WeatherError(f"NWS request failed: {exc}") from exc

    def _ensure_urls(self) -> None:
        """Gridpoint lookup — cached because it never changes for a location.
        Fills BOTH the daily and hourly forecast URLs in one request."""
        if not self._forecast_url or not self._hourly_url:
            data = self._get(f"{NWS_BASE}/points/{self.lat},{self.lon}")
            try:
                props = data["properties"]
                self._forecast_url = props["forecast"]
                # Older/mock payloads may omit forecastHourly — derive it.
                self._hourly_url = props.get("forecastHourly") or props["forecast"] + "/hourly"
            except KeyError as exc:
                raise WeatherError(f"NWS points response missing forecast URL: {data!r:.200}") from exc

    def _ensure_forecast_url(self) -> str:
        self._ensure_urls()
        return self._forecast_url  # type: ignore[return-value]

    def forecast(self, max_periods: int = 4) -> list[Period]:
        """The next few named periods (Today, Tonight, Tomorrow, ...)."""
        data = self._get(self._ensure_forecast_url())
        periods = []
        for p in data.get("properties", {}).get("periods", [])[:max_periods]:
            pop = p.get("probabilityOfPrecipitation") or {}
            periods.append(
                Period(
                    name=p.get("name", "?"),
                    short_forecast=p.get("shortForecast", ""),
                    temperature=int(p.get("temperature", 0)),
                    temperature_unit=p.get("temperatureUnit", "F"),
                    is_daytime=bool(p.get("isDaytime", True)),
                    precip_chance=pop.get("value"),
                )
            )
        if not periods:
            raise WeatherError("NWS returned no forecast periods.")
        return periods

    def precip_next_hours(self, n: int = 6) -> list[tuple[str, int]]:
        """Next n hours of precipitation probability as ('3 PM', 40) pairs,
        from the NWS hourly gridpoint forecast.

        NEVER RAISES: a briefing must survive a flaky network. On any
        failure we return [] and record why in self.last_error.
        """
        try:
            self._ensure_urls()
            data = self._get(self._hourly_url)  # type: ignore[arg-type]
            out = []
            for p in data.get("properties", {}).get("periods", [])[:n]:
                pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
                out.append((_hour_label(p.get("startTime", "")), int(pop or 0)))
            return out
        except Exception as exc:  # noqa: BLE001 — deliberate never-raise
            self.last_error = f"precip_next_hours failed: {exc}"
            return []

    def alerts(self) -> list[dict]:
        """Active NWS alerts for our point, each as
        {'event': ..., 'severity': ...} from the alert's properties.

        NEVER RAISES — same briefing-survival contract as precip_next_hours.
        """
        try:
            data = self._get(f"{NWS_BASE}/alerts/active?point={self.lat},{self.lon}")
            return [
                {
                    "event": f.get("properties", {}).get("event", "?"),
                    "severity": f.get("properties", {}).get("severity", "?"),
                }
                for f in data.get("features", [])
            ]
        except Exception as exc:  # noqa: BLE001 — deliberate never-raise
            self.last_error = f"alerts failed: {exc}"
            return []

    def briefing_lines(self) -> list[str]:
        """Human-ready lines for the morning briefing, e.g.
        ['Portland, OR', 'Today: Rain likely, 58°F, 80% precip', ...]"""
        header = self.label or f"{self.lat},{self.lon}"
        return [header] + [p.render() for p in self.forecast()]
