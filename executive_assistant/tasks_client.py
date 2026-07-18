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

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


@dataclass
class Task:
    title: str
    done: bool = False
    due: date | None = None
    priority: str = "normal"
    completed_on: date | None = None

    def is_overdue(self, today: date) -> bool:
        return not self.done and self.due is not None and self.due < today

    def is_due_soon(self, today: date, days: int = 2) -> bool:
        return (
            not self.done
            and self.due is not None
            and today <= self.due <= today.fromordinal(today.toordinal() + days)
        )

    def render(self) -> str:
        """Serialize back to one markdown line."""
        mark = "x" if self.done else " "
        bits = [self.title]
        if self.due:
            bits.append(f"@due({self.due.isoformat()})")
        if self.priority != "normal":
            bits.append(f"@priority({self.priority})")
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
    # Strip annotations to recover the clean human title.
    title = DUE_RE.sub("", body)
    title = PRIORITY_RE.sub("", title)
    title = COMPLETED_RE.sub("", title).strip()
    return Task(
        title=title,
        done=m.group("mark").lower() == "x",
        due=_parse_date(due_m.group(1)) if due_m else None,
        priority=pri_m.group(1) if pri_m else "normal",
        completed_on=_parse_date(comp_m.group(0)[11:-1]) if comp_m else None,
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
    def open_tasks(self) -> list[Task]:
        return [t for k, t in self.entries if k == "task" and not t.done]  # type: ignore[misc]

    def overdue(self, today: date) -> list[Task]:
        return [t for t in self.open_tasks() if t.is_overdue(today)]

    def due_soon(self, today: date, days: int = 2) -> list[Task]:
        return [t for t in self.open_tasks() if t.is_due_soon(today, days)]

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

    # --- mutations -----------------------------------------------------------
    def add(self, title: str, due: date | None = None, priority: str = "normal") -> Task:
        task = Task(title=title, due=due, priority=priority)
        # Append at the end — the file's ## Open section grows naturally.
        self.entries.append(("task", task))
        return task

    def complete(self, fragment: str, today: date) -> Task | None:
        """Mark the first open task whose title contains `fragment` done."""
        frag = fragment.lower()
        for i, (kind, item) in enumerate(self.entries):
            if kind == "task" and not item.done and frag in item.title.lower():  # type: ignore[union-attr]
                item.done = True  # type: ignore[union-attr]
                item.completed_on = today  # type: ignore[union-attr]
                self.entries[i] = ("task", item)
                return item  # type: ignore[return-value]
        return None
