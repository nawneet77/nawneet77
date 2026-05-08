"""Rewrite README.md NOW row with the latest external merged PR.

Runs in GitHub Actions on a daily cron. Searches for any merged PR I've
authored in repos owned by other users/orgs, picks the most recent, and
formats it into the marker block.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request

USERNAME = "nawneet77"
README = "README.md"
START = "<!-- LATEST_OSS:start -->"
END = "<!-- LATEST_OSS:end -->"


def fetch(url: str) -> dict:
    req = urllib.request.Request(url)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def latest_external_merged_pr() -> dict | None:
    q = f"is:pr is:merged author:{USERNAME} -user:{USERNAME}"
    url = (
        "https://api.github.com/search/issues?"
        f"q={urllib.parse.quote(q)}&sort=updated&order=desc&per_page=5"
    )
    data = fetch(url)
    items = data.get("items", [])
    return items[0] if items else None


def humanize_delta(iso: str) -> str:
    when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    delta = dt.datetime.now(dt.timezone.utc) - when
    if delta.days == 0:
        hours = delta.seconds // 3600
        if hours <= 1:
            return "just now"
        return f"{hours}h ago"
    if delta.days == 1:
        return "yesterday"
    if delta.days < 7:
        return f"{delta.days} days ago"
    if delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    months = delta.days // 30
    return f"{months} month{'s' if months > 1 else ''} ago"


def format_row(pr: dict) -> str:
    repo_url = pr["repository_url"]
    org_repo = "/".join(repo_url.split("/")[-2:])
    org = org_repo.split("/")[0]
    title = pr["title"]
    if len(title) > 70:
        title = title[:67] + "…"
    return (
        f'Last open source merge: <a href="https://github.com/{org}"><b>{org}</b></a> '
        f'<a href="{pr["html_url"]}">#{pr["number"]}</a> — <i>{title}</i> '
        f'&middot; {humanize_delta(pr["closed_at"])}.'
    )


def main() -> int:
    pr = latest_external_merged_pr()
    if not pr:
        print("No external merged PRs found — leaving README unchanged.")
        return 0

    new_content = format_row(pr)
    with open(README, encoding="utf-8") as f:
        text = f.read()

    pattern = re.compile(
        re.escape(START) + r".*?" + re.escape(END), re.DOTALL
    )
    if not pattern.search(text):
        print(f"Markers {START}…{END} not found in README — aborting.")
        return 1

    replacement = f"{START}{new_content}{END}"
    updated = pattern.sub(replacement, text)

    if updated == text:
        print("README already up to date.")
        return 0

    with open(README, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"README updated → {pr['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
