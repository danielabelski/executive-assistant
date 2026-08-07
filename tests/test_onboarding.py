"""Tests for onboarding — scripted answers drive the whole wizard offline."""

import pytest

import executive_assistant.onboarding as onboarding
from executive_assistant.config import (
    CalendarProvider,
    EmailProvider,
    EmailPermission,
    load_config,
)
from executive_assistant.config import AssistantConfig, save_config
from executive_assistant.onboarding import run_onboarding, run_section


#: The full google-path answer script (matches TestFullPaths), ending with
#: an explicit "yes" at the review screen. Reused by the review tests.
GOOGLE_PATH_ANSWERS = [
    "Walker", "",           # name, timezone
    "1",                    # email: Gmail
    "1",                    # permission: draft_only
    "",                     # important senders
    "1",                    # calendar: Google
    "y", "y", "n",          # tasks, weather, github
    "97201",                # zip
    "",                     # thinking: menu → cloud (default)
    "",                     # thinking: model id (default)
    "", "",                 # briefing times
    "y",                    # review: yes, write it
]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Never hit the network or the real secrets file in wizard tests.

    Returns the dict capturing set_secret() calls so tests can assert on it.
    """
    monkeypatch.setattr(onboarding, "resolve_zip",
                        lambda z: (45.5, -122.6, f"Testville for {z}"))
    written: dict = {}
    monkeypatch.setattr(onboarding, "set_secret",
                        lambda key, value: written.update({key: value}))
    return written


def scripted(answers: list[str]):
    it = iter(answers)
    return lambda prompt: next(it, "")


class TestFullPaths:
    def test_google_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "config.yaml"))
        answers = [
            "Walker", "",           # name, timezone
            "1",                    # email: Gmail
            "1",                    # permission: draft_only
            "",                     # important senders
            "1",                    # calendar: Google
            "y", "y", "n",          # tasks, weather, github
            "97201",                # zip
            "",                     # thinking: menu → cloud (default)
            "",                     # thinking: model id (default)
            "", "",                 # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None)
        assert cfg.email_provider == EmailProvider.GMAIL
        assert cfg.calendar_provider == CalendarProvider.GOOGLE
        assert cfg.email_permission == EmailPermission.DRAFT_ONLY
        assert cfg.llm_local_only is False
        assert cfg.weather_zip == "97201"
        assert cfg.weather_label == "Testville for 97201"

    def test_imap_caldav_path(self, tmp_path, monkeypatch, fakes):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "config.yaml"))
        answers = [
            "Walker", "",
            "2",                        # email: IMAP
            "imap.fastmail.com",        # imap host
            "", "",                     # imap port, smtp host (defaults)
            "",                         # smtp port (default)
            "me@fastmail.com",          # username
            "",                         # drafts folder (default)
            "secretpw",                 # password → secrets
            "3",                        # permission: auto_send_routine
            "news@x.com",               # routine senders
            "",                         # important senders
            "2",                        # calendar: CalDAV
            "https://caldav.fastmail.com/x/",  # url
            "me@fastmail.com",          # caldav username
            "calpw",                    # caldav password → secrets
            "y", "n", "n",              # tasks, weather, github
            "",                         # thinking: menu → cloud
            "",                         # thinking: model id (default)
            "", "",                     # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None)
        assert cfg.email_provider == EmailProvider.IMAP
        assert cfg.calendar_provider == CalendarProvider.CALDAV
        assert cfg.email_permission == EmailPermission.AUTO_SEND_ROUTINE
        assert cfg.routine_senders == ["news@x.com"]
        assert cfg.imap_host == "imap.fastmail.com"
        assert cfg.caldav_url == "https://caldav.fastmail.com/x/"
        # passwords went to the secrets store, never the config
        assert fakes == {"email_imap_password": "secretpw",
                         "calendar_caldav_password": "calpw"}


class TestMinimalPaths:
    def test_none_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "config.yaml"))
        answers = [
            "Walker", "",
            "3",            # email: none
            "4",            # calendar: none
            "y", "n", "n",  # tasks, weather, github
            "",             # thinking: menu → cloud
            "",             # thinking: model id (default)
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
            "",                 # thinking: menu → cloud
            "",                 # thinking: model id (default)
            "", "",             # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None)
        assert cfg.calendar_provider == CalendarProvider.LOCAL_ICS
        assert cfg.local_ics_path == str(ics_path)
        assert ics_path.exists()          # empty calendar file created

    def test_local_only_ollama_path(self, tmp_path, monkeypatch):
        cfg_path = tmp_path / "config.yaml"
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(cfg_path))
        answers = [
            "Walker", "",
            "3",              # email: none
            "4",              # calendar: none
            "y", "n", "n",    # tasks, weather, github
            "2",              # thinking: LOCAL OLLAMA ONLY
            "",               # ollama model (default qwen2.5:3b)
            "",               # ollama host (default)
            "", "",           # briefing times
        ]
        cfg = run_onboarding(input_func=scripted(answers), out=lambda s: None,
                             probe_services=False)
        assert cfg.llm_local_only is True
        assert cfg.ollama_model == "qwen2.5:3b"
        assert cfg.ollama_host == "http://localhost:11434"
        # and the local-only choice round-trips through the saved YAML
        loaded = load_config(cfg_path)
        assert loaded.llm_local_only is True
        assert loaded.ollama_model == "qwen2.5:3b"


class TestReviewScreen:
    """The wizard shows its whole contract before writing a byte."""

    def test_review_shown_and_yes_writes(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "c.yaml"))
        out_lines = []
        answers = iter(GOOGLE_PATH_ANSWERS)
        cfg = run_onboarding(input_func=lambda _p: next(answers),
                             out=out_lines.append, save=False,
                             probe_services=False)
        review = [l for l in out_lines if "REVIEW" in l]
        assert review, "expected a review screen before save"
        assert cfg.user_name == "Walker"

    def test_declining_review_restarts_wizard(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "c.yaml"))
        # First pass ends 'n' at review; wizard restarts; second pass ends 'y'.
        out_lines = []
        first = GOOGLE_PATH_ANSWERS[:-1] + ["n"]
        answers = iter(first + GOOGLE_PATH_ANSWERS)
        cfg = run_onboarding(input_func=lambda _p: next(answers),
                             out=out_lines.append, save=False,
                             probe_services=False)
        reviews = [l for l in out_lines if "REVIEW" in l]
        assert len(reviews) == 2               # asked twice = restarted once
        assert cfg.user_name == "Walker"


class TestRunSection:
    """`onboard --only weather` shouldn't re-ask your name."""

    def _existing(self, tmp_path, monkeypatch):
        # weather off: the dataclass default enables it without coordinates,
        # which (correctly) fails load-time validation.
        cfg = AssistantConfig(user_name="Walker", weather_enabled=False)
        path = tmp_path / "config.yaml"
        save_config(cfg, path)
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(path))
        return path

    def test_tasks_section_preserves_everything_else(self, tmp_path, monkeypatch):
        path = self._existing(tmp_path, monkeypatch)
        answers = iter(["n"])                    # tasks? no.
        cfg = run_section("tasks", input_func=lambda _p: next(answers),
                          out=lambda _s: None)
        assert cfg.tasks_enabled is False
        assert cfg.user_name == "Walker"         # untouched
        assert "tasks" in path.read_text()       # saved back

    def test_llm_section_switches_to_local(self, tmp_path, monkeypatch):
        self._existing(tmp_path, monkeypatch)
        answers = iter(["2", "qwen2.5:3b", "http://localhost:11434"])
        cfg = run_section("llm", input_func=lambda _p: next(answers),
                          out=lambda _s: None)
        assert cfg.llm_local_only is True
        assert cfg.ollama_model == "qwen2.5:3b"

    def test_unknown_section_raises(self):
        import pytest

        with pytest.raises(ValueError):
            run_section("nonsense", input_func=lambda _p: "", out=lambda _s: None)
