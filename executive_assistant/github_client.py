"""GitHub monitoring — STUB.

The interface is settled so enabling this later is a config flip, not a
redesign. When you're ready, the plan is:

    * list open issues / new notifications across configured repos
    * via `gh` CLI (gh auth login) or a personal access token + REST

Until then every method raises GitHubNotConfigured with guidance, and the
briefing simply omits the GitHub section because integrations.github=false.
"""

from __future__ import annotations


class GitHubNotConfigured(Exception):
    """Raised whenever the stub is used before GitHub monitoring is set up."""


class GitHubClient:
    """Future home of repo monitoring. Documents the intended interface."""

    def __init__(self, username: str = "", repos: list[str] | None = None):
        self.username = username
        self.repos = repos or []

    def is_configured(self) -> bool:
        return bool(self.username and self.repos)

    def new_issues(self) -> list[dict]:
        """Would return [{repo, number, title, url, created_at}, ...]."""
        raise GitHubNotConfigured(
            "GitHub monitoring is stubbed off. To enable: set integrations.github: true\n"
            "in config/config.yaml, fill in github.username/repos, and authenticate\n"
            "with `gh auth login` (or a PAT). Then implement this method via the REST API."
        )

    def notifications_summary(self) -> str:
        """One-line summary for the briefing, e.g. '3 new issues across 2 repos'."""
        raise GitHubNotConfigured(
            "GitHub monitoring is stubbed off — see GitHubClient.new_issues."
        )
