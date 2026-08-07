"""Tests for the markdown task file — parse, mutate, round-trip."""

from datetime import date

import pytest

from executive_assistant.tasks_client import DuplicateTaskError, TaskFile, parse_task_line

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


class TestNewAnnotationsParsing:
    def test_all_new_annotations_parse_and_strip_from_title(self):
        t = parse_task_line(
            "- [ ] Water plants @due(2026-07-20) @repeat(weekly) "
            "@snooze(2026-07-25) @added(2026-07-01) @project(home)"
        )
        assert t.title == "Water plants"
        assert t.due == date(2026, 7, 20)
        assert t.repeat == "weekly"
        assert t.snoozed_until == date(2026, 7, 25)
        assert t.added_on == date(2026, 7, 1)
        assert t.project == "home"

    def test_render_round_trips_new_annotations(self):
        line = (
            "- [ ] Water plants @due(2026-07-20) @priority(high) @project(home) "
            "@repeat(weekly) @snooze(2026-07-25) @added(2026-07-01)"
        )
        t = parse_task_line(line)
        assert t.render() == line

    def test_round_trip_through_save_load(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(
            "# Tasks\n\n## Open\n"
            "- [ ] Stretch @repeat(daily) @added(2026-07-01) @project(health)\n"
        )
        tf = TaskFile.load(p)
        tf.save(p)
        assert "@repeat(daily)" in p.read_text()
        assert "@project(health)" in p.read_text()
        tf2 = TaskFile.load(p)
        t = tf2.open_tasks()[0]
        assert t.repeat == "daily" and t.project == "health" and t.added_on == date(2026, 7, 1)


class TestRepeat:
    def _tf_with(self, line: str, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(f"# Tasks\n\n## Open\n{line}\n")
        return TaskFile.load(p)

    def test_daily_spawns_next_day(self, tmp_path):
        tf = self._tf_with("- [ ] Stretch @due(2026-07-18) @repeat(daily) @added(2026-07-01)", tmp_path)
        done = tf.complete("stretch", TODAY)
        assert done.done
        nxt = tf.open_tasks()[0]
        assert nxt.title == "Stretch" and nxt.due == date(2026, 7, 19)
        assert nxt.repeat == "daily" and nxt.added_on == TODAY

    def test_weekly_spawns_next_week(self, tmp_path):
        tf = self._tf_with("- [ ] Water plants @due(2026-07-18) @repeat(weekly)", tmp_path)
        tf.complete("water", TODAY)
        assert tf.open_tasks()[0].due == date(2026, 7, 25)

    def test_monthly_shifts_one_month(self, tmp_path):
        tf = self._tf_with("- [ ] Pay rent @due(2026-07-31) @repeat(monthly)", tmp_path)
        tf.complete("rent", TODAY)
        assert tf.open_tasks()[0].due == date(2026, 8, 31)

    def test_monthly_clamps_short_month(self, tmp_path):
        tf = self._tf_with("- [ ] Invoice @due(2026-01-31) @repeat(monthly)", tmp_path)
        tf.complete("invoice", TODAY)
        assert tf.open_tasks()[0].due == date(2026, 2, 28)

    def test_repeat_without_due_bases_on_today(self, tmp_path):
        tf = self._tf_with("- [ ] Journal @repeat(daily)", tmp_path)
        tf.complete("journal", TODAY)
        assert tf.open_tasks()[0].due == date(2026, 7, 19)

    def test_non_repeating_complete_still_plain(self, tmp_path):
        tf = self._tf_with("- [ ] One-off thing", tmp_path)
        tf.complete("one-off", TODAY)
        assert tf.open_tasks() == []


class TestSnoozeAndVisibility:
    def test_is_visible_false_until_snooze_date(self):
        t = parse_task_line("- [ ] Later thing @snooze(2026-07-20)")
        assert not t.is_visible(date(2026, 7, 19))
        assert t.is_visible(date(2026, 7, 20))
        assert t.is_visible(date(2026, 7, 21))

    def test_open_tasks_filters_snoozed(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(
            "# Tasks\n\n## Open\n"
            "- [ ] Visible now\n"
            "- [ ] Hidden @snooze(2026-07-30)\n"
        )
        tf = TaskFile.load(p)
        assert len(tf.open_tasks()) == 2                     # no today → unfiltered
        assert [t.title for t in tf.open_tasks(TODAY)] == ["Visible now"]

    def test_snooze_method(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text("# Tasks\n\n## Open\n- [ ] Bug me later\n")
        tf = TaskFile.load(p)
        t = tf.snooze("bug me", date(2026, 7, 30))
        assert t.snoozed_until == date(2026, 7, 30)
        assert tf.open_tasks(TODAY) == []
        assert tf.snooze("nope", date(2026, 7, 30)) is None


class TestAddedAndStale:
    def test_add_stamps_added(self, tmp_path):
        p = tmp_path / "tasks.md"
        tf = TaskFile.load(p)
        t = tf.add("Fresh task", today=TODAY)
        assert t.added_on == TODAY
        tf.save(p)
        assert f"@added({TODAY.isoformat()})" in p.read_text()

    def test_is_stale(self):
        t = parse_task_line("- [ ] Ancient @added(2026-07-01)")
        assert t.is_stale(TODAY, days=14)          # 17 days old
        assert not t.is_stale(date(2026, 7, 10), days=14)
        fresh = parse_task_line("- [ ] No stamp")
        assert not fresh.is_stale(TODAY, days=14)  # no @added → never stale

    def test_done_task_not_stale(self):
        t = parse_task_line("- [x] Old but done @added(2026-01-01) @completed(2026-07-18)")
        assert not t.is_stale(TODAY)


class TestDuplicates:
    def test_duplicate_title_rejected_case_insensitive(self, tmp_path):
        p = tmp_path / "tasks.md"
        tf = TaskFile.load(p)
        tf.add("Buy milk", today=TODAY)
        with pytest.raises(DuplicateTaskError):
            tf.add("buy MILK", today=TODAY)

    def test_same_title_allowed_after_completion(self, tmp_path):
        p = tmp_path / "tasks.md"
        tf = TaskFile.load(p)
        tf.add("Buy milk", today=TODAY)
        tf.complete("milk", TODAY)
        tf.add("Buy milk", today=TODAY)  # no raise
        assert len(tf.open_tasks()) == 1


class TestDeferAndReopen:
    def test_defer_moves_due(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text("# Tasks\n\n## Open\n- [ ] Call dentist @due(2026-07-18)\n")
        tf = TaskFile.load(p)
        t = tf.defer("DENTIST", date(2026, 7, 25))  # case-insensitive
        assert t.due == date(2026, 7, 25)
        assert tf.defer("nope", date(2026, 7, 25)) is None

    def test_reopen_brings_back(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text("# Tasks\n\n## Done\n- [x] File taxes @completed(2026-07-18)\n")
        tf = TaskFile.load(p)
        t = tf.reopen("TAXES", today=TODAY)
        assert not t.done and t.completed_on is None
        assert [x.title for x in tf.open_tasks()] == ["File taxes"]
        assert tf.reopen("taxes") is None  # now open — reopen matches done only


class TestProjectRollup:
    def test_rollup_groups_by_project(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(
            "# Tasks\n\n## Open\n"
            "- [ ] Order supplements @project(clinic)\n"
            "- [ ] Renew license @project(clinic)\n"
            "- [ ] Water plants @project(home)\n"
            "- [ ] Random errand\n"
            "- [ ] Snoozed clinic thing @project(clinic) @snooze(2026-07-30)\n"
        )
        tf = TaskFile.load(p)
        roll = tf.rollup_by_project(TODAY)
        assert sorted(roll) == ["clinic", "home", "inbox"]
        assert [t.title for t in roll["clinic"]] == ["Order supplements", "Renew license"]
        assert [t.title for t in roll["inbox"]] == ["Random errand"]


class TestSuggestAndPriorityList:
    def _tf(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(
            "# Tasks\n\n## Open\n"
            "- [ ] Overdue thing @due(2026-07-10) @added(2026-07-01)\n"
            "- [ ] Due soon thing @due(2026-07-19) @added(2026-07-05)\n"
            "- [ ] High thing @priority(high) @added(2026-07-10)\n"
            "- [ ] Oldest plain @added(2026-07-02)\n"
            "- [ ] Newest plain @added(2026-07-15)\n"
        )
        return TaskFile.load(p)

    def test_suggested_next_ranking(self, tmp_path):
        tf = self._tf(tmp_path)
        titles = [t.title for t in tf.suggested_next(TODAY, n=5)]
        assert titles == [
            "Overdue thing",    # overdue beats everything
            "Due soon thing",   # then due-soon
            "High thing",       # then high priority
            "Oldest plain",     # then oldest added
            "Newest plain",
        ]

    def test_suggested_next_respects_n(self, tmp_path):
        tf = self._tf(tmp_path)
        assert len(tf.suggested_next(TODAY, n=2)) == 2

    def test_suggested_next_skips_snoozed(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(
            "# Tasks\n\n## Open\n"
            "- [ ] Snoozed overdue @due(2026-07-01) @snooze(2026-07-30)\n"
            "- [ ] Normal thing\n"
        )
        tf = TaskFile.load(p)
        assert [t.title for t in tf.suggested_next(TODAY)] == ["Normal thing"]

    def test_list_by_priority(self, tmp_path):
        p = tmp_path / "tasks.md"
        p.write_text(
            "# Tasks\n\n## Open\n"
            "- [ ] Low later @priority(low) @due(2026-07-20)\n"
            "- [ ] High later @priority(high) @due(2026-07-25)\n"
            "- [ ] High sooner @priority(high) @due(2026-07-19)\n"
            "- [ ] Normal thing\n"
        )
        tf = TaskFile.load(p)
        titles = [t.title for t in tf.list_by_priority(TODAY)]
        assert titles == ["High sooner", "High later", "Normal thing", "Low later"]
