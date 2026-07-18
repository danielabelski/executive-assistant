"""Tests for the GitHub stub — it must fail loudly and helpfully until implemented."""

import pytest

from executive_assistant.github_client import GitHubClient, GitHubNotConfigured


class TestStub:
    def test_unconfigured_by_default(self):
        assert GitHubClient().is_configured() is False

    def test_configured_when_username_and_repos_present(self):
        assert GitHubClient("me", ["me/repo"]).is_configured() is True

    def test_new_issues_raises_with_guidance(self):
        with pytest.raises(GitHubNotConfigured, match="gh auth login"):
            GitHubClient("me", ["me/repo"]).new_issues()

    def test_summary_raises(self):
        with pytest.raises(GitHubNotConfigured):
            GitHubClient().notifications_summary()
