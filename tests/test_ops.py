"""Tests for the ops layer — paths, logging, and the CLI glue."""

import json
import logging

from executive_assistant import paths
from executive_assistant.__main__ import main
from executive_assistant.logging_setup import get_logger


class TestPaths:
    def test_data_dir_auto_created_with_gitkeep(self, tmp_path, monkeypatch):
        target = tmp_path / "fresh" / "data"
        monkeypatch.setattr(paths, "DATA_DIR", target)
        d = paths.data_dir()
        assert d.is_dir()
        assert (d / ".gitkeep").exists()

    def test_log_and_audit_paths_under_data(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
        assert paths.log_path().name == "assistant.log"
        assert paths.audit_log_path().name == "approval_log.jsonl"


class TestLoggingSetup:
    def test_idempotent_no_duplicate_handlers(self):
        get_logger("a")
        root = logging.getLogger("executive_assistant")
        n = len(root.handlers)
        get_logger("b")
        assert len(root.handlers) == n      # second call stacks nothing

    def test_returns_namespaced_logger(self):
        assert get_logger("x").name == "executive_assistant.x"


class TestVersionFlag:
    def test_version_prints_and_exits_zero(self, capsys):
        assert main(["--version"]) == 0
        out = capsys.readouterr().out.strip()
        assert out == "0.3.0"

    def test_no_command_prints_help(self, capsys):
        assert main([]) == 1
        assert "usage:" in capsys.readouterr().out


class TestJsonModes:
    """--json turns briefings into pipes for other tools (jq, dashboards)."""

    def _config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_CONFIG", str(tmp_path / "c.yaml"))
        (tmp_path / "c.yaml").write_text(
            'user:\n  name: "W"\n  timezone: "America/Los_Angeles"\n'
            "location:\n  label: Nowhere\n"
            "integrations:\n  email: false\n  calendar: false\n"
            "  weather: false\n  tasks: false\n  github: false\n"
        )

    def test_briefing_json_shape(self, tmp_path, monkeypatch, capsys):
        self._config(tmp_path, monkeypatch)
        assert main(["briefing", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["kind"] == "briefing"
        assert isinstance(payload["sections"], list)

    def test_wrapup_json_shape(self, tmp_path, monkeypatch, capsys):
        self._config(tmp_path, monkeypatch)
        assert main(["wrapup", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["kind"] == "wrapup"


class TestPhrasebankCommand:
    def test_stats_runs(self, capsys):
        assert main(["phrasebank", "--stats"]) == 0
        out = capsys.readouterr().out
        assert "categories" in out
