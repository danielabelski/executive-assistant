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


class WeatherClient:
    """Fetches and formats the NWS forecast for configured coordinates."""

    def __init__(self, lat: float, lon: float, label: str = ""):
        self.lat, self.lon, self.label = lat, lon, label
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
        self._forecast_url: str | None = None  # cached after first lookup

    def _get(self, url: str) -> dict:
        try:
            resp = self._session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise WeatherError(f"NWS request failed: {exc}") from exc

    def _ensure_forecast_url(self) -> str:
        """Gridpoint lookup — cached because it never changes for a location."""
        if not self._forecast_url:
            data = self._get(f"{NWS_BASE}/points/{self.lat},{self.lon}")
            try:
                self._forecast_url = data["properties"]["forecast"]
            except KeyError as exc:
                raise WeatherError(f"NWS points response missing forecast URL: {data!r:.200}") from exc
        return self._forecast_url

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

    def briefing_lines(self) -> list[str]:
        """Human-ready lines for the morning briefing, e.g.
        ['Portland, OR', 'Today: Rain likely, 58°F, 80% precip', ...]"""
        header = self.label or f"{self.lat},{self.lon}"
        return [header] + [p.render() for p in self.forecast()]
