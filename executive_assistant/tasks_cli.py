"""Standalone CLI for the markdown task file.

    python -m executive_assistant.tasks_cli add "Buy milk" --due 2026-07-20
    python -m executive_assistant.tasks_cli complete milk
    python -m executive_assistant.tasks_cli defer milk 2026-07-22
    python -m executive_assistant.tasks_cli snooze milk 2026-07-25
    python -m executive_assistant.tasks_cli reopen milk
    python -m executive_assistant.tasks_cli list [--by-priority]
    python -m executive_assistant.tasks_cli suggest [-n 3]

The task file path comes from $EXEC_ASSISTANT_TASKS, defaulting to
./tasks.md. This is a thin shell over tasks_client.TaskFile — all the
logic lives there; here we only parse argv and print.
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from pathlib import Path

from executive_assistant.tasks_client import DuplicateTaskError, TaskFile

DEFAULT_PATH = "tasks.md"
ENV_VAR = "EXEC_ASSISTANT_TASKS"


def _tasks_path() -> Path:
    return Path(os.environ.get(ENV_VAR, DEFAULT_PATH))


def _parse_date(text: str) -> date:
    return datetime.strptime(text, "%Y-%m-%d").date()


def _fmt(task) -> str:
    """One compact display line for a task."""
    bits = [task.title]
    if task.due:
        bits.append(f"(due {task.due})")
    if task.priority != "normal":
        bits.append(f"[{task.priority}]")
    if task.project:
        bits.append(f"#{task.project}")
    if task.repeat:
        bits.append(f"↻{task.repeat}")
    return " ".join(bits)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tasks", description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="add a new task")
    a.add_argument("title")
    a.add_argument("--due", help="YYYY-MM-DD")
    a.add_argument("--priority", choices=["low", "normal", "high"], default="normal")
    a.add_argument("--project")
    a.add_argument("--repeat", choices=["daily", "weekly", "monthly"])

    c = sub.add_parser("complete", help="mark a task done (spawns @repeat occurrences)")
    c.add_argument("fragment")

    d = sub.add_parser("defer", help="push a task's due date")
    d.add_argument("fragment")
    d.add_argument("new_due", help="YYYY-MM-DD")

    s = sub.add_parser("snooze", help="hide a task until a date passes")
    s.add_argument("fragment")
    s.add_argument("until", help="YYYY-MM-DD")

    r = sub.add_parser("reopen", help="bring a completed task back to open")
    r.add_argument("fragment")

    l = sub.add_parser("list", help="list visible open tasks")
    l.add_argument("--by-priority", action="store_true", help="sort by priority")

    g = sub.add_parser("suggest", help="what to do next")
    g.add_argument("-n", type=int, default=3, help="how many to suggest")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = _tasks_path()
    today = date.today()
    tf = TaskFile.load(path)

    if args.command == "add":
        try:
            task = tf.add(
                args.title,
                due=_parse_date(args.due) if args.due else None,
                priority=args.priority,
                today=today,
                project=args.project,
                repeat=args.repeat,
            )
        except DuplicateTaskError as exc:
            print(f"duplicate: {exc}")
            return 1
        tf.save(path)
        print(f"added: {_fmt(task)}")
        return 0

    if args.command == "complete":
        task = tf.complete(args.fragment, today)
        if task is None:
            print(f"no open task matching {args.fragment!r}")
            return 1
        tf.save(path)
        print(f"done: {_fmt(task)}")
        if task.repeat:
            spawned = [t for t in tf.open_tasks() if t.title == task.title]
            if spawned:
                print(f"next occurrence: {_fmt(spawned[-1])}")
        return 0

    if args.command == "defer":
        task = tf.defer(args.fragment, _parse_date(args.new_due))
        if task is None:
            print(f"no open task matching {args.fragment!r}")
            return 1
        tf.save(path)
        print(f"deferred: {_fmt(task)}")
        return 0

    if args.command == "snooze":
        task = tf.snooze(args.fragment, _parse_date(args.until))
        if task is None:
            print(f"no open task matching {args.fragment!r}")
            return 1
        tf.save(path)
        print(f"snoozed until {args.until}: {task.title}")
        return 0

    if args.command == "reopen":
        task = tf.reopen(args.fragment, today=today)
        if task is None:
            print(f"no completed task matching {args.fragment!r}")
            return 1
        tf.save(path)
        print(f"reopened: {_fmt(task)}")
        return 0

    if args.command == "list":
        tasks = tf.list_by_priority(today) if args.by_priority else tf.open_tasks(today)
        if not tasks:
            print("(no open tasks)")
            return 0
        for i, t in enumerate(tasks, 1):
            print(f"{i:2}. {_fmt(t)}")
        return 0

    if args.command == "suggest":
        tasks = tf.suggested_next(today, n=args.n)
        if not tasks:
            print("(nothing to suggest)")
            return 0
        for i, t in enumerate(tasks, 1):
            why = (
                "overdue" if t.is_overdue(today)
                else "due soon" if t.is_due_soon(today)
                else "high priority" if t.priority == "high"
                else "oldest"
            )
            print(f"{i:2}. {_fmt(t)}  — {why}")
        return 0

    return 2  # argparse required=True makes this unreachable


if __name__ == "__main__":
    raise SystemExit(main())
