"""Tests for the NWS weather client — all HTTP mocked, zero network."""

import pytest
import requests

from executive_assistant.weather_client import (
    WeatherClient,
    WeatherError,
    resolve_zip,
    trend_arrow,
    umbrella_line,
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


POINTS_WITH_HOURLY = {
    "properties": {
        "forecast": "https://api.weather.gov/gridpoints/PQR/1,2/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/PQR/1,2/forecast/hourly",
    }
}
HOURLY_PAYLOAD = {
    "properties": {
        "periods": [
            {"startTime": "2026-08-06T15:00:00-07:00",
             "probabilityOfPrecipitation": {"value": 10}},
            {"startTime": "2026-08-06T16:00:00-07:00",
             "probabilityOfPrecipitation": {"value": 40}},
            {"startTime": "2026-08-06T17:00:00-07:00",
             "probabilityOfPrecipitation": {"value": 55}},
            {"startTime": "2026-08-06T18:00:00-07:00",
             "probabilityOfPrecipitation": {"value": None}},
        ]
    }
}
ALERTS_PAYLOAD = {
    "features": [
        {"properties": {"event": "Heat Advisory", "severity": "Moderate"}},
        {"properties": {"event": "Red Flag Warning", "severity": "Severe"}},
    ]
}


class TestPrecipNextHours:
    def _client(self, monkeypatch):
        client = WeatherClient(45.5, -122.6, "Portland, OR")

        def fake_get(url, timeout):
            if "/points/" in url:
                return FakeResponse(POINTS_WITH_HOURLY)
            return FakeResponse(HOURLY_PAYLOAD)

        monkeypatch.setattr(client._session, "get", fake_get)
        return client

    def test_parses_hour_labels_and_probabilities(self, monkeypatch):
        hours = self._client(monkeypatch).precip_next_hours()
        assert hours[:2] == [("3 PM", 10), ("4 PM", 40)]
        assert hours[3] == ("6 PM", 0)  # null PoP → 0, not a crash

    def test_respects_n(self, monkeypatch):
        hours = self._client(monkeypatch).precip_next_hours(n=2)
        assert len(hours) == 2

    def test_never_raises_on_http_error(self, monkeypatch):
        client = WeatherClient(45.5, -122.6)

        def boom(url, timeout):
            raise requests.ConnectionError("no route")

        monkeypatch.setattr(client._session, "get", boom)
        assert client.precip_next_hours() == []
        assert client.last_error is not None

    def test_never_raises_on_malformed_payload(self, monkeypatch):
        client = WeatherClient(45.5, -122.6)
        monkeypatch.setattr(client._session, "get",
                            lambda url, timeout: FakeResponse({"unexpected": 1}))
        assert client.precip_next_hours() == []
        assert client.last_error is not None


class TestAlerts:
    def test_parses_event_and_severity(self, monkeypatch):
        client = WeatherClient(45.5, -122.6)
        monkeypatch.setattr(client._session, "get",
                            lambda url, timeout: FakeResponse(ALERTS_PAYLOAD))
        alerts = client.alerts()
        assert alerts == [
            {"event": "Heat Advisory", "severity": "Moderate"},
            {"event": "Red Flag Warning", "severity": "Severe"},
        ]

    def test_empty_when_no_features(self, monkeypatch):
        client = WeatherClient(45.5, -122.6)
        monkeypatch.setattr(client._session, "get",
                            lambda url, timeout: FakeResponse({"features": []}))
        assert client.alerts() == []

    def test_never_raises_on_http_error(self, monkeypatch):
        client = WeatherClient(45.5, -122.6)

        def boom(url, timeout):
            raise requests.Timeout("slow")

        monkeypatch.setattr(client._session, "get", boom)
        assert client.alerts() == []
        assert client.last_error is not None

    def test_never_raises_on_malformed_payload(self, monkeypatch):
        client = WeatherClient(45.5, -122.6)
        monkeypatch.setattr(client._session, "get",
                            lambda url, timeout: FakeResponse(None))
        assert client.alerts() == []
        assert client.last_error is not None


class TestTrendArrow:
    def test_warming(self):
        assert trend_arrow(70, 60) == "↑"

    def test_cooling(self):
        assert trend_arrow(55, 68) == "↓"

    def test_deadband_is_one_degree(self):
        assert trend_arrow(61, 60) == "→"   # exactly +1°F: not a trend
        assert trend_arrow(59, 60) == "→"   # exactly -1°F: not a trend
        assert trend_arrow(60, 60) == "→"
        assert trend_arrow(61.1, 60) == "↑"  # just past the deadband
        assert trend_arrow(58.9, 60) == "↓"


class TestUmbrellaLine:
    def test_first_hour_over_threshold(self):
        hourly = [("3 PM", 10), ("4 PM", 40), ("5 PM", 70)]
        assert umbrella_line(hourly) == "Umbrella? 40% at 4 PM"

    def test_custom_threshold(self):
        hourly = [("3 PM", 40), ("4 PM", 70)]
        assert umbrella_line(hourly, threshold=50) == "Umbrella? 70% at 4 PM"

    def test_none_when_all_under(self):
        hourly = [("3 PM", 10), ("4 PM", 30)]  # 30 is not OVER 30
        assert umbrella_line(hourly) is None

    def test_none_for_empty(self):
        assert umbrella_line([]) is None
