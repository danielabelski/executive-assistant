"""Tests for config loading, validation, and the save/load round-trip."""

import pytest

from executive_assistant.config import (
    AssistantConfig,
    CalendarProvider,
    ConfigError,
    EmailPermission,
    EmailProvider,
    load_config,
    save_config,
)


class TestDefaults:
    def test_missing_config_raises_with_guidance(self, tmp_path):
        """No silent defaults: a missing config says exactly what to do next."""
        with pytest.raises(ConfigError, match="onboard"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_constructed_defaults_are_safe(self):
        cfg = AssistantConfig()
        assert cfg.email_permission == EmailPermission.DRAFT_ONLY   # safest default
        assert cfg.email_provider == EmailProvider.NONE
        assert cfg.calendar_provider == CalendarProvider.NONE
        assert cfg.gmail_enabled is False
        assert cfg.calendar_enabled is False
        assert cfg.llm_local_only is False            # cloud policy is the default
        assert cfg.ollama_model == "qwen2.5:3b"
        assert "11434" in cfg.ollama_host
        assert cfg.tasks_enabled is True

    def test_llm_defaults_are_cloud_mode(self):
        cfg = AssistantConfig()
        assert cfg.llm_local_only is False          # cloud is the default policy
        assert cfg.thinking_model == "kimi-k3"
        assert cfg.ollama_model == "qwen2.5:3b"
        assert cfg.ollama_host == "http://localhost:11434"


class TestValidation:
    def test_explicitly_enabled_weather_requires_coordinates(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("integrations:\n  weather: true\nweather:\n  latitude: 0.0\n")
        with pytest.raises(ConfigError, match="weather"):
            load_config(p)


class TestLegacyMapping:
    def test_legacy_integrations_booleans_map_to_providers(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("integrations:\n  gmail: true\n  calendar: true\n")
        cfg = load_config(p)
        assert cfg.email_provider == EmailProvider.GMAIL
        assert cfg.calendar_provider == CalendarProvider.GOOGLE


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

    def test_llm_policy_round_trips(self, tmp_path):
        p = tmp_path / "config.yaml"
        save_config(AssistantConfig(
            llm_local_only=True, ollama_model="gemma2:2b",
            ollama_host="http://jetson:11434",
            thinking_model="kimi-k3", weather_enabled=False), p)
        loaded = load_config(p)
        assert loaded.llm_local_only is True
        assert loaded.ollama_model == "gemma2:2b"
        assert loaded.ollama_host == "http://jetson:11434"
        assert loaded.thinking_model == "kimi-k3"   # kept, just unused in local mode

    def test_llm_defaults_when_section_absent(self, tmp_path):
        p = tmp_path / "config.yaml"
        p.write_text("version: 2\nuser: {name: W}\n")
        loaded = load_config(p)
        assert loaded.llm_local_only is False
        assert loaded.ollama_model == "qwen2.5:3b"
        assert "11434" in loaded.ollama_host

    def test_example_config_loads(self):
        """The committed config.example.yaml must always stay valid."""
        from executive_assistant.config import PROJECT_ROOT

        cfg = load_config(PROJECT_ROOT / "config.example.yaml")
        assert cfg.email_permission in EmailPermission.ALL
        assert cfg.email_provider in EmailProvider.ALL
