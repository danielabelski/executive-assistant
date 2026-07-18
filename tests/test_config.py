"""Tests for config loading, validation, and the save/load round-trip."""

import pytest

from executive_assistant.config import (
    AssistantConfig,
    CalendarProvider,
    ConfigError,
    EmailProvider,
    EmailPermission,
    load_config,
    save_config,
)


class TestDefaults:
    def test_safe_defaults(self):
        cfg = AssistantConfig()
        assert cfg.email_permission == EmailPermission.DRAFT_ONLY
        assert cfg.email_provider == EmailProvider.NONE    # opt-in, never default-on
        assert cfg.gmail_enabled is False                  # derived property
        assert cfg.calendar_enabled is False
        assert cfg.github_enabled is False

    def test_derived_properties(self):
        cfg = AssistantConfig(email_provider=EmailProvider.GMAIL,
                              calendar_provider=CalendarProvider.LOCAL_ICS)
        assert cfg.gmail_enabled and cfg.email_enabled and cfg.calendar_enabled

    def test_resolve_relative_path(self):
        cfg = AssistantConfig(tasks_path="tasks.md")
        assert cfg.tasks_file.name == "tasks.md"
        assert cfg.tasks_file.is_absolute()


class TestLoad:
    def test_missing_file_raises_with_guidance(self, tmp_path):
        with pytest.raises(ConfigError, match="onboard"):
            load_config(tmp_path / "nope.yaml")

    def test_invalid_permission_rejected(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("email:\n  provider: gmail\n  permission: yolo_mode\n")
        with pytest.raises(ConfigError, match="draft_only"):
            load_config(p)

    def test_invalid_provider_rejected(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("email:\n  provider: protonmail\n")
        with pytest.raises(ConfigError, match="none"):
            load_config(p)

    def test_imap_requires_host_and_username(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("email:\n  provider: imap\n")
        with pytest.raises(ConfigError, match="imap.host"):
            load_config(p)

    def test_caldav_requires_url_and_username(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("calendar:\n  provider: caldav\n")
        with pytest.raises(ConfigError, match="caldav.url"):
            load_config(p)

    def test_weather_enabled_requires_coordinates(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("integrations:\n  weather: true\nweather:\n  latitude: 0\n  longitude: 0\n")
        with pytest.raises(ConfigError, match="latitude"):
            load_config(p)

    def test_legacy_integrations_booleans_map_to_providers(self, tmp_path):
        """Pre-provider config files (integrations.gmail: true) still load."""
        p = tmp_path / "config.yaml"
        p.write_text("integrations:\n  gmail: true\n  calendar: true\n")
        cfg = load_config(p)
        assert cfg.email_provider == EmailProvider.GMAIL
        assert cfg.calendar_provider == CalendarProvider.GOOGLE
        assert cfg.gmail_enabled and cfg.calendar_enabled

    def test_bad_yaml(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("{{{{ not yaml")
        with pytest.raises(ConfigError):
            load_config(p)


class TestRoundTrip:
    def test_save_then_load_preserves_choices(self, tmp_path):
        p = tmp_path / "config.yaml"
        original = AssistantConfig(
            user_name="Walker",
            email_provider=EmailProvider.IMAP,
            calendar_provider=CalendarProvider.CALDAV,
            email_permission=EmailPermission.AUTO_SEND_ROUTINE,
            routine_senders=["news@x.com"],
            important_senders=["client@y.com"],
            imap_host="imap.fastmail.com",
            imap_username="walker@fastmail.com",
            caldav_url="https://caldav.fastmail.com/dav/calendars/user/w/1/",
            caldav_username="walker@fastmail.com",
            weather_lat=45.5, weather_lon=-122.6,
        )
        save_config(original, p)
        loaded = load_config(p)
        assert loaded.user_name == "Walker"
        assert loaded.email_provider == EmailProvider.IMAP
        assert loaded.calendar_provider == CalendarProvider.CALDAV
        assert loaded.email_permission == EmailPermission.AUTO_SEND_ROUTINE
        assert loaded.routine_senders == ["news@x.com"]
        assert loaded.imap_host == "imap.fastmail.com"
        assert loaded.caldav_url.endswith("/1/")
        assert loaded.weather_lat == pytest.approx(45.5)

    def test_local_ics_path_round_trips(self, tmp_path):
        p = tmp_path / "config.yaml"
        save_config(AssistantConfig(calendar_provider=CalendarProvider.LOCAL_ICS,
                                    local_ics_path="cal/mine.ics",
                                    weather_enabled=False), p)
        assert load_config(p).local_ics_path == "cal/mine.ics"

    def test_example_config_loads(self):
        """The committed config.example.yaml must always stay valid."""
        from executive_assistant.config import PROJECT_ROOT

        cfg = load_config(PROJECT_ROOT / "config.example.yaml")
        assert cfg.email_permission in EmailPermission.ALL
        assert cfg.email_provider in EmailProvider.ALL
