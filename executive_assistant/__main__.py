"""Command-line interface:  python -m executive_assistant <command>

Commands:
    onboard    — the setup wizard (integration + permission chooser)
    auth       — Google OAuth walkthrough (headless paste-the-URL flow)
    doctor     — verify config, credentials, and network reachability
    briefing   — print the morning briefing now
    wrapup     — print the evening wrap-up now
    tasks      — manage the local task file (list/add/done)

Hermes cron calls `briefing` and `wrapup`; you use the rest.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from executive_assistant.config import (
    PROJECT_ROOT,
    ConfigError,
    EmailPermission,
    config_path,
    load_config,
)


def _cmd_onboard(_args) -> int:
    from executive_assistant.onboarding import run_onboarding

    run_onboarding()
    return 0


def _cmd_auth(_args) -> int:
    """Two-step headless OAuth: print URL → accept pasted redirect → save token.
    Only relevant when a GOOGLE provider is configured (Gmail/Google Calendar)."""
    from executive_assistant.config import CalendarProvider, EmailProvider
    from executive_assistant.google_auth import (
        AuthError,
        exchange_code,
        get_auth_url,
        is_authorized,
        scopes_for,
    )

    try:
        cfg = load_config()
    except ConfigError as exc:
        print(exc)
        return 1

    google_email = cfg.email_provider == EmailProvider.GMAIL
    google_cal = cfg.calendar_provider == CalendarProvider.GOOGLE
    if not (google_email or google_cal):
        print("No Google provider is configured — nothing to authorize.")
        print(f"(email.provider={cfg.email_provider}, calendar.provider={cfg.calendar_provider})")
        return 1
    scopes = scopes_for(google_email, google_cal)

    if is_authorized(cfg.token_path, scopes):
        print("Already authorized ✓  (delete the token file to force re-authorization)")
        return 0

    secret = cfg.client_secret_path
    if not secret.exists():
        print(f"Google client secret not found at {secret}\n")
        print("One-time setup (~5 min):")
        print("  1. https://console.cloud.google.com/projectselector2/home/dashboard")
        print("     → create or select a project")
        print("  2. https://console.cloud.google.com/apis/library")
        print("     → enable 'Gmail API' and 'Google Calendar API'")
        print("  3. https://console.cloud.google.com/apis/credentials")
        print("     → Create Credentials → OAuth 2.0 Client ID → type 'Desktop app'")
        print("  4. https://console.cloud.google.com/auth/audience")
        print("     → add your Google account as a test user (if app is in Testing)")
        print(f"  5. Download the JSON and save it as:\n       {secret}")
        return 1

    try:
        url = get_auth_url(secret, scopes)
    except AuthError as exc:
        print(exc)
        return 1

    print("\nOpen this URL in ANY browser (phone/laptop is fine):\n")
    print(f"    {url}\n")
    print("After you approve, the browser will try to load http://localhost:1/…")
    print("and FAIL — that's expected. Copy the ENTIRE URL from the address bar.")
    pasted = input("Paste it here: ").strip()
    try:
        token = exchange_code(secret, scopes, pasted, cfg.token_path)
    except AuthError as exc:
        print(exc)
        return 1
    print(f"\n✓ Authorized — tokens saved to {token}")
    print("  They refresh automatically from now on.")
    return 0


def _cmd_doctor(_args) -> int:
    """Health report: config ✓/✗, then one check per configured provider."""
    from executive_assistant.config import CalendarProvider, EmailProvider

    ok = True
    print(f"Config file:  {config_path()}")
    try:
        cfg = load_config()
        print(f"  ✓ loaded — user={cfg.user_name!r}, tz={cfg.timezone}")
    except ConfigError as exc:
        print(f"  ✗ {exc}")
        return 1

    # --- email provider -------------------------------------------------------
    if cfg.email_provider == EmailProvider.GMAIL:
        ok &= _check_google(cfg, email=True, calendar=False)
    elif cfg.email_provider == EmailProvider.IMAP:
        ok &= _check_imap(cfg)
    else:
        print("  ◌ email provider: none")

    # --- calendar provider ------------------------------------------------------
    if cfg.calendar_provider == CalendarProvider.GOOGLE:
        ok &= _check_google(cfg, email=False, calendar=True)
    elif cfg.calendar_provider == CalendarProvider.CALDAV:
        ok &= _check_caldav(cfg)
    elif cfg.calendar_provider == CalendarProvider.LOCAL_ICS:
        exists = cfg.ics_file.exists()
        print(f"  {'✓' if exists else '✗ missing (re-run onboarding)'} local calendar ({cfg.ics_file})")
        ok &= exists
    else:
        print("  ◌ calendar provider: none")

    if cfg.weather_enabled:
        try:
            from executive_assistant.weather_client import WeatherClient

            lines = WeatherClient(cfg.weather_lat, cfg.weather_lon, cfg.weather_label).briefing_lines()
            print(f"  ✓ weather reachable — {lines[0]}")
        except Exception as exc:
            print(f"  ✗ weather failed — {exc}")
            ok = False

    if cfg.tasks_enabled:
        print(f"  {'✓' if cfg.tasks_file.exists() else '✗ missing'} task file ({cfg.tasks_file})")
        ok = ok and cfg.tasks_file.exists()

    print(f"  {'✓' if not cfg.github_enabled else '◌'} github "
          f"({'disabled' if not cfg.github_enabled else 'enabled (stub)'})")

    # LLM policy — local_only mode promises ZERO paid API calls; verify the
    # local path is actually healthy (Ollama up + model pulled).
    if cfg.llm_local_only:
        from executive_assistant.thinker import Thinker

        status = Thinker(cfg).status()
        if status["reachable"] and status["model_pulled"]:
            print(f"  ✓ local-only LLM — ollama:{status['model']} ready (zero token fees)")
        else:
            why = "Ollama unreachable" if not status["reachable"] else \
                  f"model not pulled — run: ollama pull {status['model']}"
            print(f"  ⚠ local-only LLM — {why}")
            print("    (deterministic fallbacks will cover thinking jobs; no fees either way)")
    else:
        print(f"  ◌ thinking model: {cfg.thinking_model} (cloud — per-token fees apply)")

    print("\nOverall:", "✓ ready" if ok else "✗ fix the ✗ items above")
    return 0 if ok else 1


def _check_google(cfg, email: bool, calendar: bool) -> bool:
    """Shared check for the two Google providers (same token, different scopes)."""
    from executive_assistant.google_auth import is_authorized, scopes_for

    label = "gmail" if email else "google calendar"
    if not cfg.client_secret_path.exists():
        print(f"  ✗ client secret MISSING — run: python -m executive_assistant auth")
        return False
    scopes = scopes_for(email, calendar)
    good = is_authorized(cfg.token_path, scopes)
    print(f"  {'✓' if good else '✗ not authorized — run auth'}  {label} OAuth")
    return good


def _check_imap(cfg) -> bool:
    """Try a real IMAP login — the only honest check."""
    from executive_assistant.imap_client import ImapEmailClient, ImapError
    from executive_assistant.secrets import get_secret

    if not get_secret("email_imap_password"):
        print("  ✗ IMAP password missing — set email_imap_password in config/secrets.yaml")
        return False
    client = ImapEmailClient(cfg.imap_host, cfg.imap_username,
                             get_secret("email_imap_password"), port=cfg.imap_port)
    try:
        conn = client._connect()
        conn.logout()
        print(f"  ✓ IMAP login ok — {cfg.imap_host} as {cfg.imap_username}")
        return True
    except ImapError as exc:
        print(f"  ✗ IMAP failed — {exc}")
        return False


def _check_caldav(cfg) -> bool:
    """Probe the CalDAV collection with a tiny REPORT."""
    from executive_assistant.caldav_client import CalDavCalendar, CalDavError
    from executive_assistant.secrets import get_secret

    if not get_secret("calendar_caldav_password"):
        print("  ✗ CalDAV password missing — set calendar_caldav_password in config/secrets.yaml")
        return False
    client = CalDavCalendar(cfg.caldav_url, cfg.caldav_username,
                            get_secret("calendar_caldav_password"), timezone=cfg.timezone)
    try:
        client.events_today()
        print(f"  ✓ CalDAV reachable — {cfg.caldav_url}")
        return True
    except CalDavError as exc:
        print(f"  ✗ CalDAV failed — {exc}")
        return False


def _cmd_briefing(_args) -> int:
    from executive_assistant.briefing import MorningBriefing

    try:
        print(MorningBriefing(load_config()).render_text())
        return 0
    except ConfigError as exc:
        print(exc)
        return 1


def _cmd_wrapup(_args) -> int:
    from executive_assistant.briefing import EveningWrapUp

    try:
        print(EveningWrapUp(load_config()).render_text())
        return 0
    except ConfigError as exc:
        print(exc)
        return 1


def _cmd_tasks(args) -> int:
    from executive_assistant.tasks_client import TaskFile

    try:
        cfg = load_config()
    except ConfigError as exc:
        print(exc)
        return 1
    tf = TaskFile.load(cfg.tasks_file)

    if args.tasks_command == "list":
        for i, t in enumerate(tf.prioritized(), 1):
            due = f"  (due {t.due})" if t.due else ""
            pri = f"  [{t.priority}]" if t.priority != "normal" else ""
            print(f"{i:2}. {t.title}{due}{pri}")
        return 0
    if args.tasks_command == "add":
        due = datetime.strptime(args.due, "%Y-%m-%d").date() if args.due else None
        t = tf.add(args.title, due=due, priority=args.priority)
        tf.save(cfg.tasks_file)
        print(f"added: {t.render()}")
        return 0
    if args.tasks_command == "done":
        from datetime import date

        t = tf.complete(args.fragment, date.today())
        if t:
            tf.save(cfg.tasks_file)
            print(f"completed: {t.title}")
            return 0
        print(f"no open task matching {args.fragment!r}")
        return 1
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="executive_assistant",
                                     description="Personal executive assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("onboard", help="run the setup wizard")
    sub.add_parser("auth", help="Google OAuth walkthrough")
    sub.add_parser("doctor", help="health check")
    sub.add_parser("briefing", help="print the morning briefing")
    sub.add_parser("wrapup", help="print the evening wrap-up")

    tasks_p = sub.add_parser("tasks", help="manage the local task file")
    tasks_sub = tasks_p.add_subparsers(dest="tasks_command", required=True)
    tasks_sub.add_parser("list")
    add_p = tasks_sub.add_parser("add")
    add_p.add_argument("title")
    add_p.add_argument("--due", help="YYYY-MM-DD")
    add_p.add_argument("--priority", choices=["low", "normal", "high"], default="normal")
    done_p = tasks_sub.add_parser("done")
    done_p.add_argument("fragment", help="text from the task title")

    args = parser.parse_args(argv)
    handlers = {
        "onboard": _cmd_onboard,
        "auth": _cmd_auth,
        "doctor": _cmd_doctor,
        "briefing": _cmd_briefing,
        "wrapup": _cmd_wrapup,
        "tasks": _cmd_tasks,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
