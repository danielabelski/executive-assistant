# Executive Assistant 🌅

[![Version 0.3.0](https://img.shields.io/badge/version-0.3.0-blueviolet)](#-whats-new-in-v030)
[![Tests: 282 passing](https://img.shields.io/badge/tests-282%20passing-brightgreen)](#-tests)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](#-quick-start)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](#-license)
[![Providers: Gmail · IMAP · CalDAV · ICS](https://img.shields.io/badge/providers-Gmail%20%C2%B7%20IMAP%20%C2%B7%20CalDAV%20%C2%B7%20ICS-orange)](#-you-choose-everything--really)
[![LLM: local-only capable](https://img.shields.io/badge/LLM-local--only%20capable-purple)](#-local-only-mode--zero-token-fees-forever)
[![Platform: Jetson · ARM64 · x86](https://img.shields.io/badge/platform-Jetson%20%C2%B7%20ARM64%20%C2%B7%20x86-lightgrey)](#-architecture)

**Wake up to an assistant that has already read your day.** Morning briefings
and evening wrap-ups — calendar, email, tasks, and weather — woven into one
warm, glanceable message, delivered where you actually live: your chat app.

Built for [Hermes Agent](https://github.com/NousResearch/hermes-agent), but
every module is plain, testable Python. No framework lock-in, no magic.

```
☀️ Morning, Walker! Coffee's on the day. Saturday, July 18

📅 Today's schedule
• 10:00–12:00  Clinic hours

✅ Tasks
• OVERDUE: Renew clinic license
• due soon: Order supplements

🌦 Weather
• This Afternoon: Sunny, 80°F, 0% precip
• Tonight: Clear, 56°F, 0% precip

Reply here and I can prepare drafts for you to review.
```

## ✨ The idea

Most "AI assistants" answer questions. This one *prepares you for your day*:

- **7:00 AM** — a briefing lands in Telegram: today's calendar, overnight
  email (important senders flagged ⭐), your open and overdue tasks, and the
  forecast.
- **6:00 PM** — a wrap-up: what you finished, what's still open, and the
  top three suggested priorities for tomorrow.
- **Anytime** — ask "reply to that first email politely" and it drafts a
  response… then does exactly what *your* permission level says it may do.

## 🎛 You choose everything — really

The heart of this project is an **onboarding chooser**
(`python -m executive_assistant onboard`). During setup, *you* decide what
the assistant may touch and how much autonomy it gets:

**Email providers** — pick one (or none):

| Provider | How it connects | Notes |
|---|---|---|
| **Gmail** | Google OAuth (one-time browser flow) | most integrated |
| **Any IMAP+SMTP** | host + app password | Fastmail, Outlook, ProtonMail Bridge, self-hosted — pure stdlib |
| none | — | no email code ever runs |

**Calendar providers** — pick one (or none):

| Provider | How it connects | Notes |
|---|---|---|
| **Google Calendar** | shares the Gmail OAuth | — |
| **CalDAV** | collection URL + app password | Nextcloud, Fastmail, iCloud, Radicale — stdlib XML, no heavy deps |
| **Local .ics file** | nothing! | a calendar that's just a file — zero accounts, works offline |
| none | — | no calendar code ever runs |

**Email permission levels** — the policy the assistant lives by:

| Level | What the assistant may do |
|---|---|
| `draft_only` | Read email, create **drafts**. Never sends. Ever. |
| `approve_send` | Draft, then ask you in chat before **every** send. |
| `auto_send_routine` | Pre-approved senders get auto-replies; everyone else still requires your yes. |

This isn't a promise in a README — it's enforced in code. Every sensitive
action routes through `approval.py`, and the test suite proves each level
behaves as documented. Passwords live in gitignored `config/secrets.yaml`
(chmod 600), never in config. Change your mind anytime: edit
`config/config.yaml` or re-run the wizard.

## 🆕 What's new in v0.3.0

Fifty improvements across the whole stack — the assistant got observant,
auditable, and easier to drive:

- **Smarter tasks** — recurring tasks (`@repeat(weekly)`), snooze
  (`@snooze(...)`), defer/reopen, `@project(...)` tags with rollups, staleness
  surfacing, duplicate guards, and a `suggested_next()` heuristic picker.
- **Richer briefings** — a one-line headline up top, weekend editions,
  configurable section order, quiet-hours flagging, per-section line budgets,
  and wrap-ups with streak tracking + tomorrow preview.
- **Auditable autonomy** — every approval-gate ruling lands in
  `data/approval_log.jsonl`; `auto_send_routine` gains a daily rate cap; and
  `python -m executive_assistant approve --explain send_email` tells you
  *why* the gate would rule before it ever does.
- **Weather with teeth** — hourly precip ("Umbrella? 40% at 5 PM"), active
  NWS severe-weather alerts, and a temperature trend arrow vs yesterday.
- **Calendar awareness** — next-event countdown ("Clinic in 45 min"),
  all-day events rendered properly, and overlap detection (⚔) shared by all
  three providers.
- **Email upgrades** — VIP sender flagging (⭐) on both providers, cheap
  unread-count polls, draft dedup, and search for thinking jobs.
- **Zero-token thinker, hardened** — retry-with-backoff on Ollama hiccups,
  model-pulled preflight in `doctor`, a hard timeout ceiling, and honest
  `[fallback]` labeling.
- **Ops that respect you** — schema v3 configs with auto-migration + backup,
  env-var overrides for every key, `onboard --only <section>` to re-run just
  one wizard section, a review-and-confirm screen before any config is
  written, `--json` output modes, `--version`, rotating logs in
  `data/assistant.log`, and a `Makefile`/`scripts/dev.sh` for the everyday
  commands.

## 🪶 The phrasebank — 1,216 phrases, ~0 tokens

An executive assistant's output is ~80% boilerplate ("Good morning", "3
unread", "rain expected — bring an umbrella"). Generating that with an LLM
every time burns tokens, latency, and money for zero added intelligence.

So the boilerplate lives in a **local SQLite phrasebank**
(`data/phrasebank.db`, built automatically from
`executive_assistant/phrasebank_data.py`): 1,216 curated phrases across 76
categories — greetings, status lines, weather advice, draft openers/closers
in four registers (formal / neutral / warm / brief), fallbacks, nudges, and
vocabulary sets. Rendered with slots, seeded by date so the assistant's
voice is consistent within a day and varies day to day.

**The LLM is reserved for genuine judgment.** `composer.py` builds compact
"thinking jobs" — e.g. *"Order these tasks by urgency… Reply with ONLY the
task numbers."* — that stay under a ~600-character budget (a full briefing
context runs 2,000+).

## 🏠 Local-only mode — zero token fees, forever

Set `llm.local_only: true` (or pick **"Local Ollama ONLY"** in onboarding)
and the assistant *structurally cannot* spend a token:

- Thinking jobs execute on your **local Ollama** (default `qwen2.5:3b` —
  a good Jetson-class thinker) via plain HTTP. No cloud endpoint exists in
  this code path.
- Every model answer passes a **validation contract** (`thinker.py`): a
  ranking must contain real task numbers, a triage must name a listed
  email. Small models sometimes hallucinate — we watched a 3B answer
  `4,5,6` for a five-task list — and garbage never reaches you.
- If Ollama is down, or the answer fails validation, **deterministic
  fallbacks** (due-date/priority sort, important-sender match) produce a
  dependable answer instead. The engine that produced each outcome is
  always labeled (`ollama:qwen2.5:3b`, `fallback(ollama-down)`,
  `fallback(ollama-invalid)`), so behavior is auditable.

Verified live on a Jetson: 3.8s warm latency for a priority-ranking job,
zero bytes leaving the machine. `doctor` checks Ollama reachability and
whether the model is pulled.

When `local_only` is false, jobs return to Hermes / your configured strong
model (`llm.thinking_model`, default `kimi-k3`) — use a good one; it's the
only model you pay for.

## 🚀 Quick start

```bash
git clone https://github.com/drwjkirkpatrick-web/executive-assistant.git
cd executive-assistant
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m executive_assistant onboard    # the chooser wizard (~3 min)
python -m executive_assistant auth       # only if you picked a Google provider
python -m executive_assistant doctor     # verify everything's wired
python -m executive_assistant briefing   # preview your morning briefing
```

### Google setup (one time, only for Gmail/Google Calendar)

The `auth` command walks you through it: create a Cloud project, enable the
**Gmail API** and **Google Calendar API**, create a *Desktop app* OAuth
client, add yourself as a test user, and save the JSON as
`credentials/google_client_secret.json`. Built for headless machines: you
approve in any browser, the redirect to `localhost:1` intentionally
"fails," and you paste the URL back. Tokens refresh automatically forever
after.

## 📅 Schedule it with Hermes cron

Two jobs deliver the full experience to Telegram (or your platform of choice):

- `0 7 * * *` → `python -m executive_assistant briefing`
- `0 18 * * *` → `python -m executive_assistant wrapup`

Ask your Hermes agent to set these up, or create them with
`hermes cron create`.

## 🧩 Architecture

```
executive_assistant/
├── onboarding.py        # the chooser wizard — review & confirm, --only section reruns
├── config.py            # policy-as-data: one YAML file, schema v3, env overrides
├── approval.py          # the gate every sensitive action must pass (+ audit log, rate cap)
├── briefing.py          # morning briefing + evening wrap-up (resilient by design)
├── composer.py          # template assembly + compact "thinking jobs" for the LLM
├── thinker.py           # policy-enforcing job executor: local Ollama + validation + fallbacks
├── phrasebank.py        # SQLite phrase store (1,216 phrases, usage stats, tone filter)
├── phrasebank_data.py   # the curated phrase data (76 categories, 4+ registers)
├── types.py             # Event / EmailSummary + shared conflict detection
├── gmail_client.py      # Gmail: unread, drafts, VIP flags, search (through the gate)
├── imap_client.py       # any IMAP+SMTP account (stdlib imaplib/smtplib)
├── calendar_client.py   # Google Calendar (next-event countdown, all-day aware)
├── caldav_client.py     # CalDAV (stdlib requests + defusedxml)
├── local_ics_calendar.py# a calendar that's just a .ics file
├── ics_util.py          # minimal RFC 5545 VEVENT parse/serialize
├── tasks_client.py      # tasks.md: recurring, snooze, projects, defer/reopen
├── tasks_cli.py         # task management straight from the shell
├── weather_client.py    # NWS — hourly precip, severe alerts, trend arrows
├── paths.py             # one owner for data/ paths (auto-created)
├── logging_setup.py     # rotating log at data/assistant.log
├── github_client.py     # stub: interface settled, enable when ready
├── google_auth.py       # headless OAuth (paste-the-URL flow)
├── secrets.py           # gitignored password store (chmod 600)
└── __main__.py          # onboard / auth / doctor / briefing / wrapup / tasks
                         #   --json · --version · phrasebank --stats · approve --explain
```

**Design principles**

- *Policy as data* — providers and permissions live in one YAML file, enforced everywhere.
- *Resilience* — a briefing never fails because one source is down; the section degrades to a warning.
- *Tokens for thought only* — templates for boilerplate, LLM for judgment.
- *Lossless personal files* — your hand-written notes in `tasks.md` and `.ics` survive machine edits.
- *Everything tested offline* — Google, IMAP, CalDAV, and NWS are all mocked; the suite runs with zero network and zero credentials.

## ✅ Tests

```bash
python -m pytest tests/ -q
# 282 passed
```

Or via the dev helpers: `make test` / `scripts/dev.sh test` (also `doctor`,
`briefing`, `wrapup`, `lint`).

## 🛣 Roadmap

- [ ] GitHub monitoring (the stub's interface is ready — flip the config)
- [ ] Draft-reply conversational loop in chat (phrasebank scaffolding + thinking model)
- [ ] Todoist / Google Tasks adapters behind the same collector interface
- [ ] Weekly review (Sunday evening)

## 📄 License

MIT — make yourself the assistant you deserve.
