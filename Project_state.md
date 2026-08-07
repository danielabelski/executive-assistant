# Project State: Executive Assistant

> **Last updated:** 2026-08-06
> **Current phase:** build
> **Overall health:** green

---

## 1. Goal (1–2 sentences)
A personal "executive assistant" agent that delivers morning briefings and
evening wrap-ups (calendar, email, tasks, weather) to Telegram, with
user-chosen providers and permission levels set during an onboarding wizard.

## 2. Current Status
### Done
- [x] Provider architecture: Gmail · IMAP+SMTP · Google Calendar · CalDAV ·
      local .ics · none — chosen per-user during onboarding
- [x] Onboarding chooser: provider menus, 3 email permission levels,
      thinking-model selection (cloud vs local-only); passwords → secrets.yaml
- [x] approval.py policy gate (draft_only / approve_send / auto_send_routine)
- [x] Phrasebank: 1,056 curated phrases, 66 categories, SQLite store,
      day-seeded rendering — routine language costs ~0 tokens
- [x] composer.py: compact "thinking jobs" (≤600 chars) per job
- [x] thinker.py: llm.local_only mode — local Ollama execution, answer
      validation contracts, deterministic fallbacks; live-verified on Jetson
      (qwen2.5:3b, 3.8s warm; hallucination regression test added)
- [x] 136 tests, all green; live smoke: local-ics + tasks + NWS weather
- [x] v0.1.0 + v0.2.0 pushed to github.com/drwjkirkpatrick-web/executive-assistant
- [x] v0.3.0 — 50 improvements: recurring/snooze/project tasks + tasks_cli,
      briefing headline/weekend/quiet-hours/line budgets, wrap-up streaks +
      tomorrow preview, phrasebank 1,216 phrases/76 cats + usage stats + tone
      filter + slot validation, thinker retry/preflight/timeout/fallback-flag,
      approval audit log + rate cap + explain CLI, config schema v3 + env
      overrides, onboarding review screen + --only sections, NWS hourly precip
      + alerts + trend, VIP senders/unread-count/draft-dedup/search on both
      email providers, next-event/all-day/conflicts across all calendar
      providers, paths.py + rotating logs, --json/--version/phrasebank/approve
      CLI commands, Makefile + scripts/dev.sh
- [x] 282 tests, all green

### In Progress
- [ ] —

### Not Started
- [ ] Google OAuth flow (needs Walker's browser, ~10 min)
- [ ] Walker runs `python -m executive_assistant onboard` for real
- [ ] Cron jobs: 7 AM briefing + 6 PM wrap-up to Telegram
- [ ] Optional: systemd --user unit for ollama serve (no sudo needed)

## 3. Architecture & Key Decisions
| Decision | Rationale | Date |
|---|---|---|
| Provider model over hardcoded Gmail | Users choose; onboarding is the product | 2026-07-18 |
| stdlib-only IMAP + CalDAV (no caldav/lxml pkgs) | ARM64/Jetson safe; defusedxml for server XML | 2026-07-18 |
| ics_util shared by local-ics + CalDAV | One tested parser, two providers | 2026-07-18 |
| secrets.yaml gitignored + env-var override | Passwords never in config.yaml | 2026-07-18 |
| Phrasebank SQLite + date-seeded rng | ~0-token boilerplate, consistent daily voice | 2026-07-18 |
| Thinking jobs ≤600 chars to thinking_model | LLM only for judgment; budget enforced by test | 2026-07-18 |
| Legacy integrations.* booleans → provider mapping | Old config files keep working | 2026-07-18 |

## 4. Blockers & Risks
- **Blocker:** Google OAuth needs Walker's Cloud Console + browser steps.
- **Risk:** none known; suite is fully mocked/offline.

## 5. Next Step (only ONE)
> **Next:** git init + commit + push to origin main.

## 6. Environment & Tooling Notes
- Python 3.11.15 venv at .venv; deps: requests, PyYAML, defusedxml,
  google-api-python-client, google-auth-oauthlib, pytest
- Host: Jetson (Linux tegra, ARM64)
- Delivery: Telegram home channel via Hermes cron

## 7. Recent Session Log
- 2026-07-18: v0.1.0 — full provider layer + phrasebank + composer; 121 tests green.
- 2026-07-18: v0.2.0 — llm.local_only Ollama mode: policy-enforcing thinker,
  answer-validation contracts, deterministic fallbacks; live-verified on Jetson
  (qwen2.5:3b, 3.8s warm, hallucination regression caught + fixed); 136 tests.
- 2026-07-18: Project kicked off; scope + permission-chooser requirement set.

## 8. References
- Plan: this file (initial build happened inline in-session)
