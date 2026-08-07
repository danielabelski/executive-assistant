"""Tests for the tasks CLI — drives main(argv) against a tmp file."""

from datetime import date

import pytest

from executive_assistant import tasks_cli
from executive_assistant.tasks_client import TaskFile


@pytest.fixture
def tasks_file(tmp_path, monkeypatch):
    """Point the CLI at a throwaway tasks.md via the env var."""
    p = tmp_path / "tasks.md"
    monkeypatch.setenv(tasks_cli.ENV_VAR, str(p))
    return p


def _titles(path):
    return [t.title for t in TaskFile.load(path).open_tasks()]


class TestAdd:
    def test_add_creates_file_and_prints(self, tasks_file, capsys):
        rc = tasks_cli.main(["add", "Buy milk", "--due", "2026-07-20", "--priority", "high"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "added: Buy milk" in out and "(due 2026-07-20)" in out and "[high]" in out
        t = TaskFile.load(tasks_file).open_tasks()[0]
        assert t.due == date(2026, 7, 20) and t.priority == "high"
        assert t.added_on == date.today()

    def test_add_with_project_and_repeat(self, tasks_file, capsys):
        rc = tasks_cli.main(["add", "Stretch", "--repeat", "daily", "--project", "health"])
        assert rc == 0
        t = TaskFile.load(tasks_file).open_tasks()[0]
        assert t.repeat == "daily" and t.project == "health"

    def test_add_duplicate_rejected(self, tasks_file, capsys):
        tasks_cli.main(["add", "Buy milk"])
        capsys.readouterr()
        rc = tasks_cli.main(["add", "buy MILK"])
        assert rc == 1
        assert "duplicate" in capsys.readouterr().out.lower()


class TestComplete:
    def test_complete_marks_done(self, tasks_file, capsys):
        tasks_cli.main(["add", "File taxes"])
        capsys.readouterr()
        rc = tasks_cli.main(["complete", "taxes"])
        assert rc == 0
        assert "done: File taxes" in capsys.readouterr().out
        assert TaskFile.load(tasks_file).open_tasks() == []

    def test_complete_repeat_spawns_occurrence(self, tasks_file, capsys):
        tasks_cli.main(["add", "Stretch", "--repeat", "daily"])
        capsys.readouterr()
        rc = tasks_cli.main(["complete", "stretch"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "next occurrence" in out
        open_tasks = TaskFile.load(tasks_file).open_tasks()
        assert len(open_tasks) == 1 and open_tasks[0].repeat == "daily"

    def test_complete_no_match(self, tasks_file, capsys):
        rc = tasks_cli.main(["complete", "ghost"])
        assert rc == 1
        assert "no open task" in capsys.readouterr().out


class TestDeferSnoozeReopen:
    def test_defer(self, tasks_file, capsys):
        tasks_cli.main(["add", "Call dentist", "--due", "2026-07-18"])
        capsys.readouterr()
        rc = tasks_cli.main(["defer", "dentist", "2026-07-25"])
        assert rc == 0
        assert "deferred" in capsys.readouterr().out
        assert TaskFile.load(tasks_file).open_tasks()[0].due == date(2026, 7, 25)

    def test_defer_no_match(self, tasks_file, capsys):
        assert tasks_cli.main(["defer", "ghost", "2026-07-25"]) == 1
        assert "no open task" in capsys.readouterr().out

    def test_snooze_hides_from_list(self, tasks_file, capsys):
        tasks_cli.main(["add", "Bug me later"])
        capsys.readouterr()
        rc = tasks_cli.main(["snooze", "bug me", "2999-01-01"])
        assert rc == 0
        assert "snoozed until 2999-01-01" in capsys.readouterr().out

        tasks_cli.main(["list"])
        assert "(no open tasks)" in capsys.readouterr().out

    def test_reopen(self, tasks_file, capsys):
        tasks_cli.main(["add", "File taxes"])
        tasks_cli.main(["complete", "taxes"])
        capsys.readouterr()
        rc = tasks_cli.main(["reopen", "TAXES"])
        assert rc == 0
        assert "reopened: File taxes" in capsys.readouterr().out
        assert _titles(tasks_file) == ["File taxes"]

    def test_reopen_no_match(self, tasks_file, capsys):
        assert tasks_cli.main(["reopen", "ghost"]) == 1
        assert "no completed task" in capsys.readouterr().out


class TestListAndSuggest:
    def test_list_shows_open_tasks(self, tasks_file, capsys):
        tasks_cli.main(["add", "Alpha"])
        tasks_cli.main(["add", "Beta", "--priority", "high"])
        capsys.readouterr()
        rc = tasks_cli.main(["list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Alpha" in out and "Beta" in out

    def test_list_by_priority_orders_high_first(self, tasks_file, capsys):
        tasks_cli.main(["add", "Alpha"])
        tasks_cli.main(["add", "Beta", "--priority", "high"])
        capsys.readouterr()
        tasks_cli.main(["list", "--by-priority"])
        out = capsys.readouterr().out
        assert out.index("Beta") < out.index("Alpha")

    def test_suggest_ranks_overdue_first(self, tasks_file, capsys):
        tasks_cli.main(["add", "Old thing", "--due", "2000-01-01"])
        tasks_cli.main(["add", "Normal thing"])
        capsys.readouterr()
        rc = tasks_cli.main(["suggest"])
        assert rc == 0
        out = capsys.readouterr().out
        assert out.index("Old thing") < out.index("Normal thing")
        assert "overdue" in out

    def test_suggest_n(self, tasks_file, capsys):
        for name in ["One", "Two", "Three"]:
            tasks_cli.main(["add", name])
        capsys.readouterr()
        tasks_cli.main(["suggest", "-n", "2"])
        out = capsys.readouterr().out.strip().splitlines()
        assert len(out) == 2

    def test_suggest_empty(self, tasks_file, capsys):
        assert tasks_cli.main(["suggest"]) == 0
        assert "(nothing to suggest)" in capsys.readouterr().out


class TestPathResolution:
    def test_default_path_used_without_env(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv(tasks_cli.ENV_VAR, raising=False)
        monkeypatch.chdir(tmp_path)
        rc = tasks_cli.main(["add", "Local task"])
        assert rc == 0
        assert (tmp_path / "tasks.md").exists()
