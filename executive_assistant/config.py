"""Configuration loading, validation, and saving for Executive Assistant.

DESIGN IDEA — "policy as data":
    Everything the assistant is *allowed* to do lives in one YAML file.
    Modules never hardcode a permission decision; they read this config
    (usually via approval.py). Changing your mind later is a one-line edit
    — or a re-run of the onboarding wizard.

PROVIDER MODEL
--------------
Email and calendar are chosen from provider menus during onboarding:
    email.provider:    none | gmail | imap
    calendar.provider: none | google | caldav | local_ics
Passwords are NOT here — they live in gitignored config/secrets.yaml.

LEGACY COMPAT: config files written before providers existed (with
integrations.gmail / integrations.calendar booleans) still load — the
booleans are mapped onto the provider model at read time.

SCHEMA VERSIONING
-----------------
SCHEMA_VERSION is the current config-file schema. load() stamps the
resulting AssistantConfig with it; if the on-disk file declares an older
version (or none), the ORIGINAL file is copied to <file>.bak before any
later rewrite can touch it, so a schema upgrade is never destructive.

ENVIRONMENT OVERRIDES (applied at load, win over the YAML file)
---------------------------------------------------------------
    EXEC_ASSISTANT_TZ                 → user.timezone
    EXEC_ASSISTANT_THINKING_MODEL     → llm.thinking_model
    EXEC_ASSISTANT_EMAIL_PROVIDER     → email.provider (none|gmail|imap)
    EXEC_ASSISTANT_CALENDAR_PROVIDER  → calendar.provider (none|google|caldav|local_ics)
    EXEC_ASSISTANT_QUIET_HOURS        → briefing.quiet_hours (e.g. "22:00-07:00")

Search order:  1. $EXEC_ASSISTANT_CONFIG   2. <project>/config/config.yaml
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
ENV_VAR = "EXEC_ASSISTANT_CONFIG"

#: Current config-file schema version. Bump when the YAML layout changes in a
#: way load() must migrate; old files are backed up to <file>.bak on load.
SCHEMA_VERSION = 3


class ConfigError(Exception):
    """Raised when the config file is missing, unreadable, or invalid."""


class EmailPermission:
    """The three email permission levels a user can pick during onboarding."""

    DRAFT_ONLY = "draft_only"                  # read + draft, never send
    APPROVE_SEND = "approve_send"              # draft, ask before every send
    AUTO_SEND_ROUTINE = "auto_send_routine"    # routine senders auto; rest ask

    ALL = (DRAFT_ONLY, APPROVE_SEND, AUTO_SEND_ROUTINE)


class EmailProvider:
    NONE = "none"
    GMAIL = "gmail"          # Google OAuth (google-auth + gmail API)
    IMAP = "imap"            # any IMAP+SMTP account (stdlib)

    ALL = (NONE, GMAIL, IMAP)


class CalendarProvider:
    NONE = "none"
    GOOGLE = "google"        # Google Calendar via OAuth
    CALDAV = "caldav"        # Nextcloud/Fastmail/iCloud/Radicale…
    LOCAL_ICS = "local_ics"  # a calendar.ics file in the project

    ALL = (NONE, GOOGLE, CALDAV, LOCAL_ICS)


@dataclass
class AssistantConfig:
    """Typed, validated view of config.yaml."""

    schema_version: int = SCHEMA_VERSION

    # user
    user_name: str = "there"
    timezone: str = "America/Los_Angeles"

    # provider selection — the onboarding chooser writes these
    email_provider: str = EmailProvider.NONE
    calendar_provider: str = CalendarProvider.NONE
    tasks_enabled: bool = True
    weather_enabled: bool = True
    github_enabled: bool = False

    # email policy (provider-independent)
    email_permission: str = EmailPermission.DRAFT_ONLY
    important_senders: list[str] = field(default_factory=list)
    routine_senders: list[str] = field(default_factory=list)

    # IMAP provider settings (password → secrets.yaml, key email_imap_password)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    smtp_host: str = ""
    smtp_port: int = 465
    imap_drafts_folder: str = "Drafts"

    # CalDAV provider settings (password → secrets.yaml, key calendar_caldav_password)
    caldav_url: str = ""
    caldav_username: str = ""

    # local .ics provider settings
    local_ics_path: str = "calendar.ics"

    # tasks
    tasks_path: str = "tasks.md"

    # weather
    weather_zip: str = ""
    weather_lat: float = 0.0
    weather_lon: float = 0.0
    weather_label: str = ""

    # github (stub)
    github_username: str = ""
    github_repos: list[str] = field(default_factory=list)

    # briefing behaviour
    morning_time: str = "07:00"
    evening_time: str = "18:00"
    max_emails: int = 5
    max_tasks: int = 10
    quiet_hours: str | None = None                    # e.g. "22:00-07:00"
    briefing_section_order: list[str] = field(default_factory=list)
    briefing_weekend_sections: list[str] = field(default_factory=list)
    briefing_max_lines: int = 10
    daily_auto_send_limit: int = 20                   # auto-send rate cap / day
    vip_senders: list[str] = field(default_factory=list)
    email_unread_only: bool = False
    thinker_timeout_s: int = 90                       # LLM thinking-job timeout

    # LLM routing — templates (phrasebank) cover routine language; thinking
    # jobs go either to a strong cloud model or to LOCAL OLLAMA ONLY
    thinking_model: str = "kimi-k3"
    llm_local_only: bool = False        # true = never call a paid/cloud API
    ollama_model: str = "qwen2.5:3b"    # used when llm_local_only is true
    ollama_host: str = "http://localhost:11434"

    # google oauth file locations (relative to project root)
    google_client_secret_file: str = "credentials/google_client_secret.json"
    google_token_file: str = "credentials/google_token.json"

    # --- derived helpers -----------------------------------------------------
    @property
    def email_enabled(self) -> bool:
        return self.email_provider != EmailProvider.NONE

    @property
    def gmail_enabled(self) -> bool:
        """True only for the Gmail provider (kept for readable call sites)."""
        return self.email_provider == EmailProvider.GMAIL

    @property
    def calendar_enabled(self) -> bool:
        return self.calendar_provider != CalendarProvider.NONE

    def resolve(self, relative: str) -> Path:
        """Resolve a config-relative path against the project root."""
        p = Path(relative)
        return p if p.is_absolute() else PROJECT_ROOT / p

    @property
    def tasks_file(self) -> Path:
        return self.resolve(self.tasks_path)

    @property
    def ics_file(self) -> Path:
        return self.resolve(self.local_ics_path)

    @property
    def client_secret_path(self) -> Path:
        return self.resolve(self.google_client_secret_file)

    @property
    def token_path(self) -> Path:
        return self.resolve(self.google_token_file)


def config_path() -> Path:
    override = os.environ.get(ENV_VAR)
    return Path(override) if override else DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None) -> AssistantConfig:
    """Load and validate config.yaml into an AssistantConfig."""
    path = path or config_path()
    if not path.exists():
        raise ConfigError(
            f"No config file at {path}.\n"
            "Run:  python -m executive_assistant onboard"
        )
    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Config file {path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file {path} must contain a YAML mapping.")

    # Schema upgrade guard: an old file is preserved verbatim before any
    # later save() can rewrite it in the new layout.
    try:
        file_version = int(raw.get("version", 1) or 1)
    except (TypeError, ValueError):
        file_version = 1
    if file_version < SCHEMA_VERSION:
        shutil.copy2(path, path.with_name(path.name + ".bak"))

    email_raw = raw.get("email", {})
    calendar_raw = raw.get("calendar", {})
    integrations = raw.get("integrations", {})

    # Legacy compat: old files have integrations.gmail / integrations.calendar
    # booleans instead of provider names.
    email_provider = email_raw.get("provider")
    if email_provider is None:
        email_provider = EmailProvider.GMAIL if integrations.get("gmail") else EmailProvider.NONE
    calendar_provider = calendar_raw.get("provider")
    if calendar_provider is None:
        calendar_provider = (
            CalendarProvider.GOOGLE if integrations.get("calendar") else CalendarProvider.NONE
        )

    cfg = AssistantConfig(
        user_name=raw.get("user", {}).get("name", "there"),
        timezone=raw.get("user", {}).get("timezone", "America/Los_Angeles"),
        email_provider=email_provider,
        calendar_provider=calendar_provider,
        tasks_enabled=bool(integrations.get("tasks", True)),
        # Absent key = OFF (a config that never mentions weather shouldn't
        # fail coordinate validation); onboarding always writes it explicitly.
        weather_enabled=bool(integrations.get("weather", False)),
        github_enabled=bool(integrations.get("github", False)),
        email_permission=email_raw.get("permission", EmailPermission.DRAFT_ONLY),
        important_senders=list(email_raw.get("important_senders", []) or []),
        routine_senders=list(email_raw.get("routine_senders", []) or []),
        imap_host=email_raw.get("imap", {}).get("host", ""),
        imap_port=int(email_raw.get("imap", {}).get("port", 993)),
        imap_username=email_raw.get("imap", {}).get("username", ""),
        smtp_host=email_raw.get("imap", {}).get("smtp_host", ""),
        smtp_port=int(email_raw.get("imap", {}).get("smtp_port", 465)),
        imap_drafts_folder=email_raw.get("imap", {}).get("drafts_folder", "Drafts"),
        caldav_url=calendar_raw.get("caldav", {}).get("url", ""),
        caldav_username=calendar_raw.get("caldav", {}).get("username", ""),
        local_ics_path=calendar_raw.get("local_ics", {}).get("path", "calendar.ics"),
        tasks_path=raw.get("tasks", {}).get("path", "tasks.md"),
        weather_zip=str(raw.get("weather", {}).get("zip_code", "")),
        weather_lat=float(raw.get("weather", {}).get("latitude", 0.0)),
        weather_lon=float(raw.get("weather", {}).get("longitude", 0.0)),
        weather_label=raw.get("weather", {}).get("label", ""),
        github_username=raw.get("github", {}).get("username", ""),
        github_repos=list(raw.get("github", {}).get("repos", []) or []),
        morning_time=raw.get("briefing", {}).get("morning_time", "07:00"),
        evening_time=raw.get("briefing", {}).get("evening_time", "18:00"),
        max_emails=int(raw.get("briefing", {}).get("max_emails", 5)),
        max_tasks=int(raw.get("briefing", {}).get("max_tasks", 10)),
        quiet_hours=raw.get("briefing", {}).get("quiet_hours"),
        briefing_section_order=list(
            raw.get("briefing", {}).get("section_order", []) or []),
        briefing_weekend_sections=list(
            raw.get("briefing", {}).get("weekend_sections", []) or []),
        briefing_max_lines=int(raw.get("briefing", {}).get("max_lines", 10)),
        daily_auto_send_limit=int(email_raw.get("daily_auto_send_limit", 20)),
        vip_senders=list(email_raw.get("vip_senders", []) or []),
        email_unread_only=bool(email_raw.get("unread_only", False)),
        thinker_timeout_s=int(raw.get("llm", {}).get("thinker_timeout_s", 90)),
        thinking_model=raw.get("llm", {}).get("thinking_model", "kimi-k3"),
        llm_local_only=bool(raw.get("llm", {}).get("local_only", False)),
        ollama_model=raw.get("llm", {}).get("ollama_model", "qwen2.5:3b"),
        ollama_host=raw.get("llm", {}).get("ollama_host", "http://localhost:11434"),
        google_client_secret_file=raw.get("google", {}).get(
            "client_secret_file", "credentials/google_client_secret.json"
        ),
        google_token_file=raw.get("google", {}).get(
            "token_file", "credentials/google_token.json"
        ),
    )
    _apply_env_overrides(cfg)
    cfg.schema_version = SCHEMA_VERSION
    _validate(cfg)
    return cfg


def _apply_env_overrides(cfg: AssistantConfig) -> None:
    """Environment wins over the YAML file (see module docstring table)."""
    env = os.environ
    if env.get("EXEC_ASSISTANT_TZ"):
        cfg.timezone = env["EXEC_ASSISTANT_TZ"]
    if env.get("EXEC_ASSISTANT_THINKING_MODEL"):
        cfg.thinking_model = env["EXEC_ASSISTANT_THINKING_MODEL"]
    if env.get("EXEC_ASSISTANT_EMAIL_PROVIDER"):
        cfg.email_provider = env["EXEC_ASSISTANT_EMAIL_PROVIDER"]
    if env.get("EXEC_ASSISTANT_CALENDAR_PROVIDER"):
        cfg.calendar_provider = env["EXEC_ASSISTANT_CALENDAR_PROVIDER"]
    if env.get("EXEC_ASSISTANT_QUIET_HOURS"):
        cfg.quiet_hours = env["EXEC_ASSISTANT_QUIET_HOURS"]


def _validate(cfg: AssistantConfig) -> None:
    """Fail loudly on the mistakes that matter, with actionable messages."""
    if cfg.email_provider not in EmailProvider.ALL:
        raise ConfigError(
            f"email.provider must be one of {EmailProvider.ALL}, got {cfg.email_provider!r}")
    if cfg.calendar_provider not in CalendarProvider.ALL:
        raise ConfigError(
            f"calendar.provider must be one of {CalendarProvider.ALL}, "
            f"got {cfg.calendar_provider!r}")
    if cfg.email_permission not in EmailPermission.ALL:
        raise ConfigError(
            f"email.permission must be one of {EmailPermission.ALL}, "
            f"got {cfg.email_permission!r}")
    if cfg.email_provider == EmailProvider.IMAP and not (cfg.imap_host and cfg.imap_username):
        raise ConfigError("IMAP provider needs email.imap.host and email.imap.username.")
    if cfg.calendar_provider == CalendarProvider.CALDAV and not (
            cfg.caldav_url and cfg.caldav_username):
        raise ConfigError("CalDAV provider needs calendar.caldav.url and .username.")
    if cfg.weather_enabled and not (cfg.weather_lat and cfg.weather_lon):
        raise ConfigError(
            "Weather is enabled but latitude/longitude are not set. "
            "Re-run onboarding or edit the weather: section.")


def save_config(cfg: AssistantConfig, path: Path | None = None) -> Path:
    """Write an AssistantConfig back to YAML (used by onboarding)."""
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "version": SCHEMA_VERSION,
        "user": {"name": cfg.user_name, "timezone": cfg.timezone},
        "email": {
            "provider": cfg.email_provider,
            "permission": cfg.email_permission,
            "important_senders": cfg.important_senders,
            "routine_senders": cfg.routine_senders,
            "vip_senders": cfg.vip_senders,
            "unread_only": cfg.email_unread_only,
            "daily_auto_send_limit": cfg.daily_auto_send_limit,
        },
        "calendar": {"provider": cfg.calendar_provider},
        "integrations": {  # kept for quick human scanning of non-provider toggles
            "tasks": cfg.tasks_enabled,
            "weather": cfg.weather_enabled,
            "github": cfg.github_enabled,
        },
        "tasks": {"path": cfg.tasks_path},
        "weather": {
            "zip_code": cfg.weather_zip,
            "latitude": cfg.weather_lat,
            "longitude": cfg.weather_lon,
            "label": cfg.weather_label,
        },
        "github": {"username": cfg.github_username, "repos": cfg.github_repos},
        "briefing": {
            "morning_time": cfg.morning_time,
            "evening_time": cfg.evening_time,
            "max_emails": cfg.max_emails,
            "max_tasks": cfg.max_tasks,
            "quiet_hours": cfg.quiet_hours,
            "section_order": cfg.briefing_section_order,
            "weekend_sections": cfg.briefing_weekend_sections,
            "max_lines": cfg.briefing_max_lines,
        },
        "llm": {
            "thinking_model": cfg.thinking_model,
            "local_only": cfg.llm_local_only,
            "ollama_model": cfg.ollama_model,
            "ollama_host": cfg.ollama_host,
            "thinker_timeout_s": cfg.thinker_timeout_s,
        },
        "google": {
            "client_secret_file": cfg.google_client_secret_file,
            "token_file": cfg.google_token_file,
        },
    }
    if cfg.email_provider == EmailProvider.IMAP:
        data["email"]["imap"] = {
            "host": cfg.imap_host,
            "port": cfg.imap_port,
            "smtp_host": cfg.smtp_host,
            "smtp_port": cfg.smtp_port,
            "username": cfg.imap_username,
            "drafts_folder": cfg.imap_drafts_folder,
        }
    if cfg.calendar_provider == CalendarProvider.CALDAV:
        data["calendar"]["caldav"] = {"url": cfg.caldav_url, "username": cfg.caldav_username}
    if cfg.calendar_provider == CalendarProvider.LOCAL_ICS:
        data["calendar"]["local_ics"] = {"path": cfg.local_ics_path}

    header = ("# Written by onboarding. Edit by hand or re-run:\n"
              "#   python -m executive_assistant onboard\n"
              "# Passwords are NOT here — see config/secrets.yaml (gitignored).\n")
    path.write_text(header + yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return path
