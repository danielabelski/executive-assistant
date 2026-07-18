"""Briefings — the morning "prepare me for today" and evening wrap-up.

RESILIENCE RULE
---------------
A briefing must NEVER fail because one source is down. Every collector is
wrapped: if Google auth is missing or NWS is unreachable, that section
says "⚠ unavailable (reason)" and the rest of the briefing still renders.
A 7 AM message that's 80% useful beats a 7 AM silence.

TESTABILITY
-----------
Collectors are constructor-injected callables. Production passes the real
clients; tests pass fakes. The aggregation + rendering logic (the part
worth testing) is therefore 100% offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from executive_assistant.config import AssistantConfig

# A collector returns a list of ready-to-print lines, or raises.
Collector = Callable[[], list[str]]


@dataclass
class Section:
    title: str
    lines: list[str] = field(default_factory=list)
    error: str | None = None

    def render(self) -> str:
        if self.error:
            return f"**{self.title}**\n⚠ unavailable — {self.error}"
        if not self.lines:
            return f"**{self.title}**\n(nothing to report)"
        body = "\n".join(f"• {line}" for line in self.lines)
        return f"**{self.title}**\n{body}"


def _run(collector: Collector, title: str) -> Section:
    """Execute one collector, converting any failure into a marked section."""
    try:
        return Section(title=title, lines=collector())
    except Exception as exc:  # deliberately broad — see RESILIENCE RULE above
        return Section(title=title, error=str(exc).splitlines()[0][:120])


# --- real collectors, built from config ------------------------------------------
# Each collector factory dispatches on the configured PROVIDER. The providers
# share an interface (see types.py), so the rendering code below never cares
# which one produced the data.


def _calendar_client_for(cfg: AssistantConfig):
    """Build the configured calendar client (all expose .events_today()/.tz)."""
    from executive_assistant.config import CalendarProvider

    if cfg.calendar_provider == CalendarProvider.GOOGLE:
        from executive_assistant.calendar_client import CalendarClient

        return CalendarClient.from_config(cfg)
    if cfg.calendar_provider == CalendarProvider.CALDAV:
        from executive_assistant.caldav_client import CalDavCalendar
        from executive_assistant.secrets import get_secret

        return CalDavCalendar(cfg.caldav_url, cfg.caldav_username,
                              get_secret("calendar_caldav_password"),
                              timezone=cfg.timezone)
    if cfg.calendar_provider == CalendarProvider.LOCAL_ICS:
        from executive_assistant.local_ics_calendar import LocalIcsCalendar

        return LocalIcsCalendar(cfg.ics_file, timezone=cfg.timezone)
    raise ValueError(f"unknown calendar provider: {cfg.calendar_provider}")


def _calendar_collector(cfg: AssistantConfig) -> Collector:
    def collect() -> list[str]:
        client = _calendar_client_for(cfg)
        events = client.events_today()
        return [e.render(client.tz) for e in events] or ["No events today."]

    return collect


def _email_client_for(cfg: AssistantConfig):
    """Build the configured email client (all expose .unread_for_briefing())."""
    from executive_assistant.config import EmailProvider

    if cfg.email_provider == EmailProvider.GMAIL:
        from executive_assistant.gmail_client import GmailClient

        return GmailClient.from_config(cfg)
    if cfg.email_provider == EmailProvider.IMAP:
        from executive_assistant.imap_client import ImapEmailClient
        from executive_assistant.secrets import get_secret

        return ImapEmailClient(
            cfg.imap_host, cfg.imap_username, get_secret("email_imap_password"),
            port=cfg.imap_port, smtp_host=cfg.smtp_host, smtp_port=cfg.smtp_port,
            drafts_folder=cfg.imap_drafts_folder,
            important_senders=cfg.important_senders,
        )
    raise ValueError(f"unknown email provider: {cfg.email_provider}")


def _gmail_collector(cfg: AssistantConfig) -> Collector:
    def collect() -> list[str]:
        client = _email_client_for(cfg)
        unread = client.unread_for_briefing(max_results=cfg.max_emails)
        lines = []
        for e in unread:
            flag = " ⭐" if e.is_important_sender else ""
            lines.append(f"{e.sender} — {e.subject}{flag}")
        return lines or ["Inbox is clear."]

    return collect


def _weather_collector(cfg: AssistantConfig) -> Collector:
    def collect() -> list[str]:
        from executive_assistant.weather_client import WeatherClient

        client = WeatherClient(cfg.weather_lat, cfg.weather_lon, cfg.weather_label)
        return [p.render() for p in client.forecast()]

    return collect


def _tasks_collector(cfg: AssistantConfig) -> Collector:
    def collect() -> list[str]:
        from executive_assistant.tasks_client import TaskFile

        tf = TaskFile.load(cfg.tasks_file)
        today = date.today()
        lines = [f"OVERDUE: {t.title}" for t in tf.overdue(today)]
        lines += [f"due soon: {t.title}" for t in tf.due_soon(today)]
        shown = {id(t) for t in tf.overdue(today)} | {id(t) for t in tf.due_soon(today)}
        for t in tf.prioritized():
            if id(t) not in shown and len(lines) < cfg.max_tasks:
                lines.append(t.title)
        return lines or ["No open tasks."]

    return collect


def _github_collector(cfg: AssistantConfig) -> Collector:
    def collect() -> list[str]:
        from executive_assistant.github_client import GitHubClient

        return [GitHubClient(cfg.github_username, cfg.github_repos).notifications_summary()]

    return collect


# --- the briefings themselves -----------------------------------------------------


class MorningBriefing:
    """"Good morning" — calendar, email, tasks, weather in one message."""

    def __init__(self, config: AssistantConfig, collectors: dict[str, Collector] | None = None,
                 composer=None):
        self.cfg = config
        self._composer = composer  # optional injection (tests); default built lazily
        if collectors is not None:
            self.collectors = collectors  # tests inject fakes here
        else:
            self.collectors = self._default_collectors()

    def _default_collectors(self) -> dict[str, Collector]:
        cfg = self.cfg
        collectors: dict[str, Collector] = {}
        if cfg.calendar_enabled:
            collectors["📅 Today's schedule"] = _calendar_collector(cfg)
        if cfg.email_enabled:
            collectors["📧 Unread email"] = _gmail_collector(cfg)
        if cfg.tasks_enabled:
            collectors["✅ Tasks"] = _tasks_collector(cfg)
        if cfg.weather_enabled:
            collectors["🌦 Weather"] = _weather_collector(cfg)
        if cfg.github_enabled:
            collectors["🐙 GitHub"] = _github_collector(cfg)
        return collectors

    def sections(self) -> list[Section]:
        return [_run(collector, title) for title, collector in self.collectors.items()]

    def render_text(self) -> str:
        greeting = self._greeting()
        header = f"☀️ **{greeting}** {date.today():%A, %B %-d}"
        parts = [header] + [s.render() for s in self.sections()]
        if self.cfg.email_enabled and self.cfg.email_permission != "draft_only":
            parts.append("_Reply here and I can draft email responses for your approval._")
        elif self.cfg.email_enabled:
            parts.append("_Reply here and I can prepare drafts for you to review._")
        return "\n\n".join(parts)

    def _greeting(self) -> str:
        """Greeting from the phrasebank (zero tokens); literal fallback if the
        DB can't be built for any reason — a briefing never dies on this."""
        try:
            if self._composer is None:
                from executive_assistant.composer import BriefingComposer

                self._composer = BriefingComposer(self.cfg)
            return self._composer.greeting()
        except Exception:
            return f"Good morning, {self.cfg.user_name}!"


class EveningWrapUp:
    """The 6 PM review: done today, still open, tomorrow's priorities."""

    def __init__(self, config: AssistantConfig, task_file=None):
        self.cfg = config
        self._task_file = task_file  # tests inject a fake; production loads real

    def _load(self):
        if self._task_file is not None:
            return self._task_file
        from executive_assistant.tasks_client import TaskFile

        return TaskFile.load(self.cfg.tasks_file)

    def render_text(self) -> str:
        today = date.today()
        tf = self._load()
        done = tf.completed_today(today)
        open_tasks = tf.open_tasks()
        top = tf.prioritized()[:3]

        parts = [f"🌙 **Evening wrap-up, {self.cfg.user_name}** — {today:%A, %B %-d}"]
        parts.append(
            "**Accomplished today**\n"
            + ("\n".join(f"• {t.title}" for t in done) if done else "• (nothing marked complete)")
        )
        parts.append(
            f"**Still open:** {len(open_tasks)} task(s)\n"
            + ("\n".join(f"• {t.title}" for t in open_tasks[: self.cfg.max_tasks])
               or "• (inbox zero — nice)")
        )
        if top:
            parts.append(
                "**Suggested focus for tomorrow**\n"
                + "\n".join(f"{i}. {t.title}" for i, t in enumerate(top, 1))
            )
        return "\n\n".join(parts)
