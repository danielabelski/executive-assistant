"""Tests for the NWS weather client — all HTTP mocked, zero network."""

import pytest
import requests

from executive_assistant.weather_client import (
    WeatherClient,
    WeatherError,
    resolve_zip,
)


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._payload


POINTS_PAYLOAD = {"properties": {"forecast": "https://api.weather.gov/gridpoints/PQR/1,2/forecast"}}
FORECAST_PAYLOAD = {
    "properties": {
        "periods": [
            {"name": "Today", "shortForecast": "Rain likely", "temperature": 58,
             "temperatureUnit": "F", "isDaytime": True,
             "probabilityOfPrecipitation": {"value": 80}},
            {"name": "Tonight", "shortForecast": "Showers", "temperature": 47,
             "temperatureUnit": "F", "isDaytime": False,
             "probabilityOfPrecipitation": {"value": None}},
        ]
    }
}
ZIP_PAYLOAD = {"places": [{"place name": "Portland", "state abbreviation": "OR",
                           "latitude": "45.5078", "longitude": "-122.6897"}]}


class TestResolveZip:
    def test_happy_path(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(ZIP_PAYLOAD))
        lat, lon, label = resolve_zip("97201")
        assert (lat, lon) == (45.5078, -122.6897)
        assert label == "Portland, OR"

    def test_bad_zip_raises_weather_error(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse({}, status=404))
        with pytest.raises(WeatherError, match="97299"):
            resolve_zip("97299")


class TestForecast:
    def _client(self, monkeypatch):
        client = WeatherClient(45.5, -122.6, "Portland, OR")

        def fake_get(url, timeout):
            # Careful: "gridpoints" CONTAINS "points" — match precisely.
            if "/points/" in url:
                return FakeResponse(POINTS_PAYLOAD)
            return FakeResponse(FORECAST_PAYLOAD)

        monkeypatch.setattr(client._session, "get", fake_get)
        return client

    def test_periods_parsed(self, monkeypatch):
        periods = self._client(monkeypatch).forecast()
        assert periods[0].name == "Today"
        assert periods[0].precip_chance == 80
        assert periods[1].precip_chance is None

    def test_render_includes_rain_chance(self, monkeypatch):
        line = self._client(monkeypatch).forecast()[0].render()
        assert "Today" in line and "58°F" in line and "80% precip" in line

    def test_gridpoint_url_cached(self, monkeypatch):
        client = self._client(monkeypatch)
        calls = []

        original = client._session.get
        monkeypatch.setattr(client._session, "get",
                            lambda url, timeout: (calls.append(url), original(url, timeout))[1])
        client.forecast()
        client.forecast()
        assert sum("/points/" in u for u in calls) == 1  # only one gridpoint lookup

    def test_network_failure_raises_weather_error(self, monkeypatch):
        client = WeatherClient(45.5, -122.6)

        def boom(url, timeout):
            raise requests.ConnectionError("no route")

        monkeypatch.setattr(client._session, "get", boom)
        with pytest.raises(WeatherError, match="NWS request failed"):
            client.forecast()
