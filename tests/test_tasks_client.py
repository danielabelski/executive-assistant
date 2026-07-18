"""Tests for the markdown task file — parse, mutate, round-trip."""

from datetime import date

from executive_assistant.tasks_client import TaskFile, parse_task_line

TODAY = date(2026, 7, 18)
YESTERDAY = date(2026, 7, 17)
TOMORROW = date(2026, 7, 19)

SAMPLE = """# Tasks

## Open
- [ ] Renew clinic license @due(2026-07-17) @priority(high)
- [ ] Order supplements @due(2026-07-19)
- [ ] Read that paper
Some freeform note the human wrote.

## Done
- [x] File taxes @completed(2026-07-18)
"""


class TestParsing:
    def test_parse_full_task(self):
        t = parse_task_line("- [ ] Renew clinic license @due(2026-07-17) @priority(high)")
        assert t.title == "Renew clinic license"
        assert t.due == YESTERDAY
        assert t.priority == "high"
        assert not t.done

    def test_non_task_lines_return_none(self):
        assert parse_task_line("## Open") is None
        assert parse_task_line("just a note") is None

    def test_annotations_stripped_from_title(self):
        t = parse_task_line("- [x] Done thing @completed(2026-07-18)")
        assert t.title == "Done thing"
        assert t.done and t.completed_on == TODAY


class TestQueries:
    def setup_method(self):
        import tempfile, pathlib

        self.tmp = pathlib.Path(tempfile.mkdtemp()) / "tasks.md"
        self.tmp.write_text(SAMPLE)
        self.tf = TaskFile.load(self.tmp)

    def test_open_tasks(self):
        assert len(self.tf.open_tasks()) == 3

    def test_overdue(self):
        assert [t.title for t in self.tf.overdue(TODAY)] == ["Renew clinic license"]

    def test_due_soon(self):
        assert [t.title for t in self.tf.due_soon(TODAY, days=2)] == ["Order supplements"]

    def test_completed_today(self):
        assert [t.title for t in self.tf.completed_today(TODAY)] == ["File taxes"]

    def test_prioritized_high_first_then_due_date(self):
        titles = [t.title for t in self.tf.prioritized()]
        assert titles[0] == "Renew clinic license"   # high priority wins despite overdue
        assert titles[1] == "Order supplements"       # has a due date
        assert titles[2] == "Read that paper"         # no due date sorts last


class TestMutationAndRoundTrip:
    def test_add_and_complete_survive_save_load(self, tmp_path):
        p = tmp_path / "tasks.md"
        tf = TaskFile.load(p)          # missing file → starter structure
        tf.add("Buy milk", due=TOMORROW, priority="low")
        tf.save(p)

        tf2 = TaskFile.load(p)
        assert [t.title for t in tf2.open_tasks()] == ["Buy milk"]

        done = tf2.complete("milk", TODAY)
        assert done and done.completed_on == TODAY
        tf2.save(p)

        tf3 = TaskFile.load(p)
        assert tf3.open_tasks() == []
        assert [t.title for t in tf3.completed_today(TODAY)] == ["Buy milk"]

    def test_human_notes_preserved(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(SAMPLE)
        tf = TaskFile.load(p)
        tf.save(p)
        assert "Some freeform note the human wrote." in p.read_text()

    def test_complete_returns_none_on_no_match(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(SAMPLE)
        tf = TaskFile.load(p)
        assert tf.complete("nonexistent", TODAY) is None
