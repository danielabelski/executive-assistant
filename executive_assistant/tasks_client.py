"""Local markdown task file — the to-do list the assistant reads and writes.

FORMAT (deliberately plain — it's a file you can edit by hand):

    # Tasks

    ## Open
    - [ ] Renew clinic license @due(2026-08-01) @priority(high)
    - [ ] Order supplements

    ## Done
    - [x] File quarterly taxes @completed(2026-07-15)

Supported annotations (all optional, order-independent):
    @due(YYYY-MM-DD)         — deadline; drives "overdue"/"due soon" in briefings
    @priority(low|normal|high)
    @completed(YYYY-MM-DD)   — stamped automatically by complete()
    @repeat(daily|weekly|monthly) — complete() spawns the next occurrence
    @snooze(YYYY-MM-DD)      — hidden from open_tasks(today) until the date passes
    @added(YYYY-MM-DD)       — stamped automatically by add(); powers is_stale()
    @project(name)           — grouping tag for rollup_by_project()

Everything else on the line is the task title. Unknown lines are preserved
verbatim on save — the parser is lossless about human edits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

TASK_RE = re.compile(r"^- \[(?P<mark>[ xX])\] (?P<body>.*)$")
DUE_RE = re.compile(r"@due\((\d{4}-\d{2}-\d{2})\)")
PRIORITY_RE = re.compile(r"@priority\((low|normal|high)\)")
COMPLETED_RE = re.compile(r"@completed\(\d{4}-\d{2}-\d{2}\)")
REPEAT_RE = re.compile(r"@repeat\((daily|weekly|monthly)\)")
SNOOZE_RE = re.compile(r"@snooze\((\d{4}-\d{2}-\d{2})\)")
ADDED_RE = re.compile(r"@added\((\d{4}-\d{2}-\d{2})\)")
PROJECT_RE = re.compile(r"@project\(([^)]+)\)")

# Every annotation regex, for stripping annotations out of a raw title.
_ANNOTATION_RES = (DUE_RE, PRIORITY_RE, COMPLETED_RE, REPEAT_RE, SNOOZE_RE, ADDED_RE, PROJECT_RE)

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}

# How a repeating task's due date shifts to produce the next occurrence.
_REPEAT_DAYS = {"daily": 1, "weekly": 7}

# Project bucket for tasks without an explicit @project tag.
INBOX_PROJECT = "inbox"


class DuplicateTaskError(ValueError):
    """add() refused because an open task with the same title already exists."""


def _shift_monthly(d: date) -> date:
    """Same day-of-month, one month later, clamped to the month's last day."""
    year, month = d.year, d.month + 1
    if month > 12:
        year, month = year + 1, 1
    # Clamp: Jan 31 → Feb 28/29, etc.
    while True:
        try:
            return date(year, month, d.day)
        except ValueError:
            d = date(d.year, d.month, d.day - 1)


@dataclass
class Task:
    title: str
    done: bool = False
    due: date | None = None
    priority: str = "normal"
    completed_on: date | None = None
    repeat: str | None = None
    snoozed_until: date | None = None
    added_on: date | None = None
    project: str | None = None

    def is_overdue(self, today: date) -> bool:
        return not self.done and self.due is not None and self.due < today

    def is_due_soon(self, today: date, days: int = 2) -> bool:
        return (
            not self.done
            and self.due is not None
            and today <= self.due <= today.fromordinal(today.toordinal() + days)
        )

    def is_visible(self, today: date) -> bool:
        """Open and not snoozed into the future.

        A task snoozed @snooze(2026-07-20) stays hidden while today is before
        that date and reappears once the date arrives.
        """
        return (
            not self.done
            and (self.snoozed_until is None or self.snoozed_until <= today)
        )

    def is_stale(self, today: date, days: int = 14) -> bool:
        """Open and sitting untouched for `days` or more since it was added."""
        return (
            not self.done
            and self.added_on is not None
            and (today - self.added_on).days >= days
        )

    def render(self) -> str:
        """Serialize back to one markdown line (annotations round-trip)."""
        mark = "x" if self.done else " "
        bits = [self.title]
        if self.due:
            bits.append(f"@due({self.due.isoformat()})")
        if self.priority != "normal":
            bits.append(f"@priority({self.priority})")
        if self.project:
            bits.append(f"@project({self.project})")
        if self.repeat:
            bits.append(f"@repeat({self.repeat})")
        if self.snoozed_until:
            bits.append(f"@snooze({self.snoozed_until.isoformat()})")
        if self.added_on:
            bits.append(f"@added({self.added_on.isoformat()})")
        if self.completed_on:
            bits.append(f"@completed({self.completed_on.isoformat()})")
        return f"- [{mark}] " + " ".join(bits)


def _parse_date(text: str) -> date | None:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_task_line(line: str) -> Task | None:
    """One markdown line → Task, or None if the line isn't a task."""
    m = TASK_RE.match(line.strip())
    if not m:
        return None
    body = m.group("body")
    due_m = DUE_RE.search(body)
    pri_m = PRIORITY_RE.search(body)
    comp_m = COMPLETED_RE.search(body)
    rep_m = REPEAT_RE.search(body)
    snz_m = SNOOZE_RE.search(body)
    add_m = ADDED_RE.search(body)
    proj_m = PROJECT_RE.search(body)
    # Strip annotations to recover the clean human title.
    title = body
    for rx in _ANNOTATION_RES:
        title = rx.sub("", title)
    title = re.sub(r"\s+", " ", title).strip()
    return Task(
        title=title,
        done=m.group("mark").lower() == "x",
        due=_parse_date(due_m.group(1)) if due_m else None,
        priority=pri_m.group(1) if pri_m else "normal",
        completed_on=_parse_date(comp_m.group(0)[11:-1]) if comp_m else None,
        repeat=rep_m.group(1) if rep_m else None,
        snoozed_until=_parse_date(snz_m.group(1)) if snz_m else None,
        added_on=_parse_date(add_m.group(1)) if add_m else None,
        project=proj_m.group(1).strip() if proj_m else None,
    )


@dataclass
class TaskFile:
    """In-memory view of tasks.md with load/save.

    Non-task lines (headers, blank lines, your own notes) are kept in
    `other_lines` region-aware so save() reproduces the file faithfully.
    Simplest robust approach: we remember the file as an ordered list of
    ("task", Task) / ("line", str) entries.
    """

    entries: list[tuple[str, object]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "TaskFile":
        if not path.exists():
            # A fresh, friendly starter file.
            tf = cls(entries=[("line", "# Tasks"), ("line", ""), ("line", "## Open")])
            return tf
        entries: list[tuple[str, object]] = []
        for line in path.read_text().splitlines():
            task = parse_task_line(line)
            entries.append(("task", task) if task else ("line", line))
        return cls(entries=entries)

    def save(self, path: Path) -> None:
        lines = []
        for kind, item in self.entries:
            lines.append(item.render() if kind == "task" else item)  # type: ignore[union-attr]
        path.write_text("\n".join(lines).rstrip() + "\n")

    # --- queries used by briefings -----------------------------------------
    def open_tasks(self, today: date | None = None) -> list[Task]:
        """Open tasks; pass `today` to also hide snoozed ones."""
        tasks: list[Task] = [t for k, t in self.entries if k == "task" and not t.done]  # type: ignore[misc]
        if today is not None:
            tasks = [t for t in tasks if t.is_visible(today)]
        return tasks

    def overdue(self, today: date) -> list[Task]:
        return [t for t in self.open_tasks(today) if t.is_overdue(today)]

    def due_soon(self, today: date, days: int = 2) -> list[Task]:
        return [t for t in self.open_tasks(today) if t.is_due_soon(today, days)]

    def completed_today(self, today: date) -> list[Task]:
        return [
            t for k, t in self.entries
            if k == "task" and t.done and t.completed_on == today  # type: ignore[union-attr]
        ]

    def prioritized(self) -> list[Task]:
        """Open tasks sorted: high→low priority, then earliest due date."""
        return sorted(
            self.open_tasks(),
            key=lambda t: (PRIORITY_ORDER.get(t.priority, 1), t.due or date.max),
        )

    def rollup_by_project(self, today: date) -> dict[str, list[Task]]:
        """Visible open tasks grouped by @project (untagged → "inbox")."""
        rollup: dict[str, list[Task]] = {}
        for t in self.open_tasks(today):
            rollup.setdefault(t.project or INBOX_PROJECT, []).append(t)
        return rollup

    def suggested_next(self, today: date, n: int = 3) -> list[Task]:
        """The n tasks most worth doing now.

        Ranking: overdue first, then due-soon, then high-priority, then the
        oldest-added (longest-neglected) tasks. Ties keep file order stable.
        """
        def rank(t: Task) -> tuple:
            return (
                not t.is_overdue(today),
                not t.is_due_soon(today),
                t.priority != "high",
                t.added_on or date.max,
            )

        return sorted(self.open_tasks(today), key=rank)[:n]

    def list_by_priority(self, today: date) -> list[Task]:
        """Visible open tasks: priority → due date → oldest added."""
        return sorted(
            self.open_tasks(today),
            key=lambda t: (
                PRIORITY_ORDER.get(t.priority, 1),
                t.due or date.max,
                t.added_on or date.max,
            ),
        )

    # --- mutations -----------------------------------------------------------
    def add(
        self,
        title: str,
        due: date | None = None,
        priority: str = "normal",
        today: date | None = None,
        project: str | None = None,
        repeat: str | None = None,
    ) -> Task:
        """Append a task, stamping @added(today).

        Raises DuplicateTaskError if an open task with the same title
        (case-insensitive) already exists — duplicates in a to-do list are
        almost always an accident.
        """
        for t in self.open_tasks():
            if t.title.lower() == title.lower():
                raise DuplicateTaskError(f"open task already exists: {t.title!r}")
        task = Task(
            title=title,
            due=due,
            priority=priority,
            added_on=today or date.today(),
            project=project,
            repeat=repeat,
        )
        # Append at the end — the file's ## Open section grows naturally.
        self.entries.append(("task", task))
        return task

    def _find(self, fragment: str, want_done: bool) -> int | None:
        """Index of the first task matching `fragment` (case-insensitive)."""
        frag = fragment.lower()
        for i, (kind, item) in enumerate(self.entries):
            if (
                kind == "task"
                and item.done == want_done  # type: ignore[union-attr]
                and frag in item.title.lower()  # type: ignore[union-attr]
            ):
                return i
        return None

    def complete(self, fragment: str, today: date) -> Task | None:
        """Mark the first open task whose title contains `fragment` done.

        If the task is @repeat(...), the next occurrence is spawned right
        after it with the due date shifted by one interval.
        """
        i = self._find(fragment, want_done=False)
        if i is None:
            return None
        item: Task = self.entries[i][1]  # type: ignore[assignment]
        item.done = True
        item.completed_on = today
        if item.repeat:
            nxt = self._next_occurrence(item, today)
            self.entries.insert(i + 1, ("task", nxt))
        return item

    @staticmethod
    def _next_occurrence(task: Task, today: date) -> Task:
        """The follow-up task a @repeat completion spawns."""
        base = task.due or today
        if task.repeat == "monthly":
            new_due = _shift_monthly(base)
        else:
            new_due = base.fromordinal(base.toordinal() + _REPEAT_DAYS[task.repeat])  # type: ignore[index]
        return Task(
            title=task.title,
            due=new_due,
            priority=task.priority,
            repeat=task.repeat,
            added_on=today,
            project=task.project,
        )

    def defer(self, fragment: str, new_due: date) -> Task | None:
        """Push the first matching open task's due date to `new_due`."""
        i = self._find(fragment, want_done=False)
        if i is None:
            return None
        item: Task = self.entries[i][1]  # type: ignore[assignment]
        item.due = new_due
        return item

    def snooze(self, fragment: str, until: date) -> Task | None:
        """Hide the first matching open task until `until` passes."""
        i = self._find(fragment, want_done=False)
        if i is None:
            return None
        item: Task = self.entries[i][1]  # type: ignore[assignment]
        item.snoozed_until = until
        return item

    def reopen(self, fragment: str, today: date | None = None) -> Task | None:
        """Bring the first matching completed task back to open."""
        i = self._find(fragment, want_done=True)
        if i is None:
            return None
        item: Task = self.entries[i][1]  # type: ignore[assignment]
        item.done = False
        item.completed_on = None
        # A reopened task gets a fresh @added stamp only if it never had one.
        if item.added_on is None and today is not None:
            item.added_on = today
        return item
