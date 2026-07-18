"""Tests for onboarding — scripted answers drive the whole wizard."""

import pytest

import executive_assistant.onboarding as onboarding
from executive_assistant.config import (
    CalendarProvider,
    EmailProvider,
    EmailPermission,
    load_config,
)
from executive_assistant.onboarding import run_onboarding


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Never hit the network or the real secrets file in wizard tests."""
    monkeypatch.setattr(onboarding, "resolve_zip",
                        lambda z: (45.5, -122.6, f"Testville for {z}"))
    written = {}
    monkeypatch.setattr(onboarding, "set_secret",
                        lambda key, value: written.update({key: value}))
    return written


def scripted(answers: list[str]):
    it = iter(answers)
    return lambda prompt: next(it, "")


class TestGooglePath:
    def test_gmail_and_google_calendar(self, tmp_path, monkeypatch):
        cfg_path = tmp_path / "config.yaml"
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(cfg_path))
        answers = [
            "Walker", "",        # name, timezone
            "1",                  # email: Gmail
            "1",                  # permission: draft_only
            "",                   # important senders
            "1",                  # calendar: Google
            "y", "y", "n",        # tasks, weather, github
            "97201",              # zip
            "",                   # thinking model (default)
            "", "",               # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None)
        assert cfg.email_provider == EmailProvider.GMAIL
        assert cfg.calendar_provider == CalendarProvider.GOOGLE
        assert cfg.email_permission == EmailPermission.DRAFT_ONLY
        assert load_config(cfg_path).email_provider == EmailProvider.GMAIL


class TestImapCalDavPath:
    def test_full_alternative_stack(self, tmp_path, monkeypatch, fakes):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "config.yaml"))
        answers = [
            "Walker", "",
            "2",                        # email: IMAP
            "imap.fastmail.com", "",    # host, port
            "", "",                     # smtp host (derived), port
            "me@fastmail.com",          # username
            "",                         # drafts folder (default)
            "secretpw",                 # password → secrets
            "3",                        # permission: auto_send_routine
            "news@x.com, bot@y.com",    # routine senders
            "",                         # important senders
            "2",                        # calendar: CalDAV
            "https://caldav.fastmail.com/dav/calendars/user/me/1/",  # url
            "me@fastmail.com",          # caldav username
            "calpw",                    # caldav password → secrets
            "y", "n", "n",              # tasks, weather, github
            "",                         # thinking model (default)
            "", "",                     # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None)
        assert cfg.email_provider == EmailProvider.IMAP
        assert cfg.imap_host == "imap.fastmail.com"
        assert cfg.smtp_host == "smtp.fastmail.com"   # derived default
        assert cfg.email_permission == EmailPermission.AUTO_SEND_ROUTINE
        assert cfg.routine_senders == ["news@x.com", "bot@y.com"]
        assert cfg.calendar_provider == CalendarProvider.CALDAV
        assert cfg.caldav_url.endswith("/1/")
        # Passwords went to the secrets store, never to config.yaml:
        assert fakes == {"email_imap_password": "secretpw",
                         "calendar_caldav_password": "calpw"}
        raw = (tmp_path / "config.yaml").read_text()
        assert "secretpw" not in raw and "calpw" not in raw


class TestMinimalPaths:
    def test_no_email_no_calendar_skips_detail_questions(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "config.yaml"))
        answers = [
            "Walker", "",
            "3",            # email: none
            "4",            # calendar: none
            "y", "n", "n",  # tasks, weather, github
            "",             # thinking model (default)
            "", "",         # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None)
        assert cfg.email_provider == EmailProvider.NONE
        assert cfg.calendar_provider == CalendarProvider.NONE
        assert cfg.email_permission == EmailPermission.DRAFT_ONLY  # untouched

    def test_local_ics_calendar(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "config.yaml"))
        ics_path = tmp_path / "my.ics"
        answers = [
            "Walker", "",
            "3",                # email: none
            "3",                # calendar: local .ics
            str(ics_path),      # calendar file path
            "y", "n", "n",      # tasks, weather, github
            "",                 # thinking model (default)
            "", "",             # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None)
        assert cfg.calendar_provider == CalendarProvider.LOCAL_ICS
        assert "BEGIN:VCALENDAR" in ics_path.read_text()   # starter file created
