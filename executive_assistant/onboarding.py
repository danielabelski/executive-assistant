"""Onboarding — the interactive chooser that writes config/config.yaml.

THIS IS THE FEATURE THE PROJECT WAS BUILT AROUND:
    The user — not the developer — decides which providers the assistant
    uses and how much autonomy it gets. Every choice is explained in plain
    language at the moment it's made, and the result is a config file the
    user can re-visit or regenerate anytime.

CHOOSER MENUS
    email.provider:    Gmail (OAuth) · any IMAP+SMTP account · none
    calendar.provider: Google Calendar · CalDAV server · local .ics · none
    email.permission:  draft_only · approve_send · auto_send_routine

Passwords are collected here but written ONLY to gitignored
config/secrets.yaml (chmod 600) — never into config.yaml.

Design notes:
    * input()/print() are injected so tests drive the wizard with scripted
      answers — no pexpect, no tty.
    * Every prompt has a sane default; Enter keeps it.
    * Only network touch: optional ZIP→lat/lon (weather), degrades gracefully.

Run it:   python -m executive_assistant onboard
"""

from __future__ import annotations

from typing import Callable

from executive_assistant.config import (
    AssistantConfig,
    CalendarProvider,
    EmailPermission,
    EmailProvider,
    save_config,
)
from executive_assistant.secrets import set_secret
from executive_assistant.weather_client import WeatherError, resolve_zip

InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]

# --- prompt helpers (loop until valid, so a typo never aborts setup) -------------


def _ask(prompt: str, default: str, input_func: InputFunc, out: OutputFunc) -> str:
    suffix = f" [{default}]" if default else ""
    answer = input_func(f"{prompt}{suffix}: ").strip()
    return answer or default


def _ask_yes_no(prompt: str, default: bool, input_func: InputFunc, out: OutputFunc) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        answer = input_func(f"{prompt} [{hint}]: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        out("Please answer y or n.")


def _ask_choice(prompt: str, options: dict[str, str], default: str,
                input_func: InputFunc, out: OutputFunc) -> str:
    """options maps key → human description. Prints a numbered menu."""
    out(prompt)
    keys = list(options.keys())
    for i, key in enumerate(keys, 1):
        marker = " (default)" if key == default else ""
        out(f"  {i}. {options[key]}{marker}")
    while True:
        answer = input_func(f"Choose 1-{len(keys)} [{keys.index(default) + 1}]: ").strip()
        if not answer:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(keys):
            return keys[int(answer) - 1]
        out("Invalid choice — enter a number from the list.")


def _ask_int(prompt: str, default: int, input_func: InputFunc, out: OutputFunc) -> int:
    while True:
        answer = input_func(f"{prompt} [{default}]: ").strip()
        if not answer:
            return default
        if answer.isdigit():
            return int(answer)
        out("Enter a number.")


# --- provider-specific detail collectors -------------------------------------------


def _collect_imap_details(cfg: AssistantConfig, input_func: InputFunc, out: OutputFunc) -> None:
    out("")
    out("IMAP + SMTP settings — any provider with an app password works here")
    out("(Fastmail, Outlook, Yahoo, ProtonMail Bridge, self-hosted…).")
    out("Common presets: Fastmail imap.fastmail.com / Outlook outlook.office365.com")
    cfg.imap_host = _ask("IMAP host", "imap.fastmail.com", input_func, out)
    cfg.imap_port = _ask_int("IMAP port (SSL)", 993, input_func, out)
    cfg.smtp_host = _ask("SMTP host", cfg.imap_host.replace("imap.", "smtp."),
                         input_func, out)
    cfg.smtp_port = _ask_int("SMTP port (SSL)", 465, input_func, out)
    cfg.imap_username = _ask("Email address / username", "", input_func, out)
    cfg.imap_drafts_folder = _ask("Drafts folder name", "Drafts", input_func, out)
    password = _ask("App password (stored ONLY in gitignored secrets.yaml)",
                    "", input_func, out)
    if password:
        set_secret("email_imap_password", password)
        out("  → saved to config/secrets.yaml (chmod 600)")
    else:
        out("  ⚠ no password given — set it later in config/secrets.yaml as")
        out("    email_imap_password, or via env var EXEC_ASSISTANT_EMAIL_IMAP_PASSWORD")


def _collect_caldav_details(cfg: AssistantConfig, input_func: InputFunc, out: OutputFunc) -> None:
    out("")
    out("CalDAV settings — you need the CALENDAR COLLECTION URL, e.g.")
    out("  Nextcloud: https://HOST/remote.php/dav/calendars/USER/personal/")
    out("  Fastmail:  https://caldav.fastmail.com/dav/calendars/user/USER/ID/")
    cfg.caldav_url = _ask("Calendar collection URL", "", input_func, out)
    cfg.caldav_username = _ask("Username", "", input_func, out)
    password = _ask("App password (stored ONLY in gitignored secrets.yaml)",
                    "", input_func, out)
    if password:
        set_secret("calendar_caldav_password", password)
        out("  → saved to config/secrets.yaml (chmod 600)")
    else:
        out("  ⚠ no password given — set it later in config/secrets.yaml as")
        out("    calendar_caldav_password, or via env var EXEC_ASSISTANT_CALENDAR_CALDAV_PASSWORD")


def _collect_permission(cfg: AssistantConfig, input_func: InputFunc, out: OutputFunc) -> None:
    """The email permission chooser — identical for every email provider."""
    out("")
    out("EMAIL PERMISSIONS — how much may the assistant do with email?")
    cfg.email_permission = _ask_choice(
        "Pick the level you're comfortable with:",
        {
            EmailPermission.DRAFT_ONLY:
                "Drafts only — I read mail and prepare drafts; nothing is "
                "ever sent. You review and send in your mail client.",
            EmailPermission.APPROVE_SEND:
                "Draft + ask — I prepare replies and ask you in chat "
                "before EVERY send. Nothing leaves without your yes.",
            EmailPermission.AUTO_SEND_ROUTINE:
                "Auto-send routine — pre-approved senders (you list them) "
                "may be answered automatically; everyone else still asks.",
        },
        EmailPermission.DRAFT_ONLY,
        input_func, out,
    )
    if cfg.email_permission == EmailPermission.AUTO_SEND_ROUTINE:
        raw = _ask(
            "Routine senders, comma-separated (e.g. newsletter@x.com, assistant@y.com)",
            "", input_func, out)
        cfg.routine_senders = [a.strip() for a in raw.split(",") if a.strip()]
    raw = _ask(
        "Important senders to FLAG in briefings (comma-separated, optional)",
        "", input_func, out)
    cfg.important_senders = [a.strip() for a in raw.split(",") if a.strip()]


# --- the wizard ------------------------------------------------------------------


def run_onboarding(input_func: InputFunc = input,
                   out: OutputFunc = print,
                   save: bool = True) -> AssistantConfig:
    """Walk the user through every choice; return (and save) the config."""
    out("=" * 68)
    out("  Executive Assistant — setup")
    out("  Every choice is yours, and every choice can be changed later by")
    out("  editing config/config.yaml or re-running this wizard.")
    out("=" * 68)

    cfg = AssistantConfig()

    # 1) Who + where ------------------------------------------------------------
    cfg.user_name = _ask("Your name", cfg.user_name, input_func, out)
    cfg.timezone = _ask("Your timezone (IANA name)", cfg.timezone, input_func, out)

    # 2) EMAIL provider chooser ----------------------------------------------------
    out("")
    out("EMAIL — pick a provider. 'None' means no email code ever runs.")
    cfg.email_provider = _ask_choice(
        "Which email account should the assistant use?",
        {
            EmailProvider.GMAIL:
                "Gmail — Google OAuth (most integrated; one-time browser setup)",
            EmailProvider.IMAP:
                "Any IMAP+SMTP account — Fastmail, Outlook, ProtonMail Bridge…",
            EmailProvider.NONE:
                "None — no email integration",
        },
        EmailProvider.GMAIL,
        input_func, out,
    )
    if cfg.email_provider == EmailProvider.IMAP:
        _collect_imap_details(cfg, input_func, out)
    if cfg.email_enabled:
        _collect_permission(cfg, input_func, out)

    # 3) CALENDAR provider chooser ---------------------------------------------------
    out("")
    out("CALENDAR — pick a provider. 'None' means no calendar code ever runs.")
    cfg.calendar_provider = _ask_choice(
        "Which calendar should the assistant read?",
        {
            CalendarProvider.GOOGLE:
                "Google Calendar — shares the Gmail OAuth setup",
            CalendarProvider.CALDAV:
                "CalDAV server — Nextcloud, Fastmail, iCloud, Radicale…",
            CalendarProvider.LOCAL_ICS:
                "Local .ics file — a calendar that's just a file (zero accounts)",
            CalendarProvider.NONE:
                "None — no calendar integration",
        },
        CalendarProvider.GOOGLE,
        input_func, out,
    )
    if cfg.calendar_provider == CalendarProvider.CALDAV:
        _collect_caldav_details(cfg, input_func, out)
    elif cfg.calendar_provider == CalendarProvider.LOCAL_ICS:
        cfg.local_ics_path = _ask("Path for the calendar file", cfg.local_ics_path,
                                  input_func, out)

    # 4) Remaining integrations --------------------------------------------------------
    out("")
    out("OTHER INTEGRATIONS")
    cfg.tasks_enabled = _ask_yes_no(
        "Local task file — a tasks.md to-do list in this project?", True, input_func, out)
    cfg.weather_enabled = _ask_yes_no(
        "Weather — US National Weather Service forecast?", True, input_func, out)
    cfg.github_enabled = _ask_yes_no(
        "GitHub — monitor repos for new issues? (stub; off is fine)", False, input_func, out)

    # 5) Weather location ----------------------------------------------------------------
    if cfg.weather_enabled:
        out("")
        out("WEATHER — the National Weather Service needs coordinates.")
        zip_code = _ask("Your ZIP code (US)", "97201", input_func, out)
        try:
            lat, lon, label = resolve_zip(zip_code)
            cfg.weather_zip, cfg.weather_lat, cfg.weather_lon, cfg.weather_label = (
                zip_code, lat, lon, label)
            out(f"  → Resolved to {label} ({lat}, {lon})")
        except WeatherError as exc:
            out(f"  ⚠ {exc}")
            out("  Weather is left enabled but unconfigured; re-run onboarding later.")
            cfg.weather_enabled = False

    # 6) GitHub (stub) ---------------------------------------------------------------------
    if cfg.github_enabled:
        cfg.github_username = _ask("GitHub username", "", input_func, out)
        raw = _ask("Repos to watch, comma-separated (owner/repo)", "", input_func, out)
        cfg.github_repos = [r.strip() for r in raw.split(",") if r.strip()]

    # 7) Thinking model ------------------------------------------------------------
    out("")
    out("THINKING MODEL — routine language comes from the local phrasebank")
    out("(zero tokens). A few jobs need real judgment: ranking priorities,")
    out("triaging email, drafting replies. Those go to a strong model.")
    cfg.thinking_model = _ask("Model for the thinking parts (Hermes/OpenRouter id)",
                              cfg.thinking_model, input_func, out)

    # 8) Briefing preferences -----------------------------------------------------------------
    out("")
    out("BRIEFINGS — when should the assistant check in?")
    cfg.morning_time = _ask("Morning briefing time (24h)", cfg.morning_time, input_func, out)
    cfg.evening_time = _ask("Evening wrap-up time (24h)", cfg.evening_time, input_func, out)

    # Save + side effects ------------------------------------------------------------------------
    if save:
        path = save_config(cfg)
        out("")
        out(f"✓ Config written to {path}")
        if cfg.tasks_enabled:
            _ensure_tasks_file(cfg, out)
        if cfg.calendar_provider == CalendarProvider.LOCAL_ICS:
            _ensure_ics_file(cfg, out)
        _print_next_steps(cfg, out)
    return cfg


def _ensure_tasks_file(cfg: AssistantConfig, out: OutputFunc) -> None:
    path = cfg.tasks_file
    if not path.exists():
        path.write_text(
            "# Tasks\n\n"
            "## Open\n"
            "- [ ] Try your first morning briefing @priority(high)\n"
            "- [ ] Add a real task: python -m executive_assistant tasks add \"Title\"\n\n"
            "## Done\n"
        )
        out(f"✓ Created starter task file at {path}")


def _ensure_ics_file(cfg: AssistantConfig, out: OutputFunc) -> None:
    path = cfg.ics_file
    if not path.exists():
        path.write_text(
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
            "PRODID:-//executive-assistant//EN\r\nEND:VCALENDAR\r\n"
        )
        out(f"✓ Created empty calendar file at {path}")


def _print_next_steps(cfg: AssistantConfig, out: OutputFunc) -> None:
    out("")
    out("NEXT STEPS")
    n = 1
    if cfg.gmail_enabled or cfg.calendar_provider == CalendarProvider.GOOGLE:
        out(f"  {n}. Set up Google access (one time, ~10 min):")
        out("       python -m executive_assistant auth")
        out("     (It walks you through creating OAuth credentials + authorizing.)")
        n += 1
    out(f"  {n}. Check everything is wired:   python -m executive_assistant doctor")
    out(f"  {n + 1}. Preview your briefing:       python -m executive_assistant briefing")
    out(f"  {n + 2}. Ask Hermes to schedule the {cfg.morning_time} AM / "
        f"{cfg.evening_time} PM cron jobs.")
