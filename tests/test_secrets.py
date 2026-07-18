"""Tests for the secrets store — env precedence, file perms, round-trip."""

import os
import stat

from executive_assistant.secrets import get_secret, load_secrets, set_secret


class TestFileStore:
    def test_set_then_get(self, tmp_path):
        p = tmp_path / "secrets.yaml"
        set_secret("email_imap_password", "hunter2", p)
        assert get_secret("email_imap_password", p) == "hunter2"

    def test_preserves_other_keys(self, tmp_path):
        p = tmp_path / "secrets.yaml"
        set_secret("a", "1", p)
        set_secret("b", "2", p)
        assert load_secrets(p) == {"a": "1", "b": "2"}

    def test_file_is_owner_only(self, tmp_path):
        p = tmp_path / "secrets.yaml"
        set_secret("a", "1", p)
        mode = stat.S_IMODE(p.stat().st_mode)
        assert mode == 0o600

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_secrets(tmp_path / "nope.yaml") == {}
        assert get_secret("anything", tmp_path / "nope.yaml") == ""


class TestEnvPrecedence:
    def test_env_var_wins_over_file(self, tmp_path, monkeypatch):
        p = tmp_path / "secrets.yaml"
        set_secret("token", "from-file", p)
        monkeypatch.setenv("EXEC_ASSISTANT_TOKEN", "from-env")
        assert get_secret("token", p) == "from-env"

    def test_env_var_works_without_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXEC_ASSISTANT_TOKEN", "env-only")
        assert get_secret("token", tmp_path / "nope.yaml") == "env-only"
