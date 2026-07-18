"""Google OAuth2 for a HEADLESS machine (Jetson) — the "paste the URL" flow.

WHY THIS ISN'T THE USUAL flow.run_local_server()
-------------------------------------------------
The normal google-auth-oauthlib flow opens a browser on the same machine
and catches the redirect on a local port. On a headless Jetson there is no
browser — you'll approve on your laptop/phone instead. So:

    1. We build an authorization URL whose redirect is http://localhost:1/
       (Google allows any localhost port for "Desktop app" OAuth clients).
    2. You open the URL anywhere, approve, and the browser tries to load
       http://localhost:1/?code=... — which FAILS to load. That's expected.
    3. You copy the full failed URL out of the address bar and paste it back.
    4. We extract ?code= and exchange it for tokens, saved to token.json.

Tokens auto-refresh on every later run — the dance happens exactly once.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes are requested according to which integrations are enabled. We ask
# for compose+send up front even in draft_only mode so that upgrading your
# permission level later doesn't force re-authorization. (What the assistant
# actually DOES is still governed by approval.py, not by the token.)
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
]
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]


class AuthError(Exception):
    """Raised for missing client secrets, bad codes, or failed refreshes."""


def scopes_for(gmail: bool, calendar: bool) -> list[str]:
    scopes: list[str] = []
    if gmail:
        scopes += GMAIL_SCOPES
    if calendar:
        scopes += CALENDAR_SCOPES
    return scopes


def _new_flow(client_secret_file: Path, scopes: list[str]) -> InstalledAppFlow:
    if not client_secret_file.exists():
        raise AuthError(
            f"Google client secret not found at {client_secret_file}.\n"
            "Download it from Google Cloud Console → APIs & Services → Credentials\n"
            "(OAuth 2.0 Client ID, type 'Desktop app') and save it there.\n"
            "See README § 'Google setup' for the full walkthrough."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes=scopes)
    # The redirect URI must match what we tell the user to expect.
    flow.redirect_uri = "http://localhost:1/"
    return flow


def get_auth_url(client_secret_file: Path, scopes: list[str]) -> str:
    """Step 1: produce the URL the user opens in any browser."""
    flow = _new_flow(client_secret_file, scopes)
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    # Stash the flow so exchange_code() can reuse the same PKCE verifier.
    _PENDING_FLOWS[str(client_secret_file)] = flow
    return auth_url


# Flows are stateful (PKCE code_verifier). In the CLI both steps happen in
# one process, so a module-level dict keyed by client-secret path is enough.
_PENDING_FLOWS: dict[str, InstalledAppFlow] = {}


def exchange_code(
    client_secret_file: Path, scopes: list[str], pasted: str, token_file: Path
) -> Path:
    """Step 2: turn the pasted redirect URL (or bare code) into saved tokens."""
    code = _extract_code(pasted)
    flow = _PENDING_FLOWS.get(str(client_secret_file)) or _new_flow(client_secret_file, scopes)
    try:
        flow.fetch_token(code=code)
    except Exception as exc:  # google-auth raises several types; keep message clear
        raise AuthError(
            f"Code exchange failed: {exc}\n"
            "Codes expire quickly and are single-use — if you reused an old "
            "browser tab, ask for a fresh auth URL and paste the NEWEST redirect."
        ) from exc
    creds = flow.credentials
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json())
    _PENDING_FLOWS.pop(str(client_secret_file), None)
    return token_file


def _extract_code(pasted: str) -> str:
    """Accept either the full redirect URL or just the code itself."""
    pasted = pasted.strip()
    if pasted.startswith("http"):
        query = parse_qs(urlparse(pasted).query)
        if "code" not in query:
            raise AuthError("That URL has no ?code=... in it — copy the ENTIRE address bar.")
        return query["code"][0]
    return pasted


def load_credentials(token_file: Path, scopes: list[str]) -> Credentials:
    """Load saved tokens, refreshing if expired. Raises AuthError if absent."""
    if not token_file.exists():
        raise AuthError(
            f"Not authorized yet (no {token_file}).\n"
            "Run:  python -m executive_assistant auth"
        )
    creds = Credentials.from_authorized_user_file(str(token_file), scopes)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())  # persist the refresh
        except Exception as exc:
            raise AuthError(f"Token refresh failed ({exc}) — re-run the auth command.") from exc
    if not creds.valid:
        raise AuthError("Saved credentials are invalid — re-run the auth command.")
    return creds


def is_authorized(token_file: Path, scopes: list[str]) -> bool:
    """Quiet True/False check used by `doctor` and tests."""
    try:
        load_credentials(token_file, scopes)
        return True
    except AuthError:
        return False
