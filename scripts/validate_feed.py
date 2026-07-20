#!/usr/bin/env python3
"""Validate feed.json and pushes/*.json against the schema documented in README.md.

Checks for:
  - missing required fields
  - X/Twitter (or other social) links that point at a profile instead of a
    specific post (the #1 source of "wrong link" user complaints)
  - malformed post/status IDs (non-numeric)
  - categories not documented in README.md's schema
  - duplicate URLs within a single file

Exit code is non-zero if any error-level issue is found, so this can be wired
into a pre-commit hook or CI step.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_ARTICLE_FIELDS = {"title", "url", "category", "published", "summary"}

# Documented in README.md's `feed.json` Schema section — keep in sync.
KNOWN_CATEGORIES = {
    "ai_models",
    "agents_tooling",
    "hermes_nous",
    "anthropic",
    "deepseek",
    "chinese_ai",
    "platforms_integration",
    "ai_research",
    "industry",
    "moonshot_ai",
    "policy",
    "zo_computer",
}

SOCIAL_PROFILE_RE = re.compile(
    r"^https?://(www\.)?(x|twitter)\.com/([^/?#]+)/?$"
)
SOCIAL_STATUS_RE = re.compile(
    r"^https?://(www\.)?(x|twitter)\.com/[^/]+/status/([^/?#]+)/?$"
)


def check_url(url: str) -> list[str]:
    errors = []
    if SOCIAL_PROFILE_RE.match(url):
        errors.append(f"links to a profile page, not a specific post: {url}")
    m = SOCIAL_STATUS_RE.match(url)
    if m and not m.group(3).isdigit():
        errors.append(f"status ID is not numeric (likely a placeholder/fake link): {url}")
    return errors


def validate_articles(articles: list[dict], file_label: str) -> list[str]:
    errors = []
    seen_urls = set()
    for i, article in enumerate(articles):
        loc = f"{file_label}#{i} ({article.get('title', '<no title>')[:50]!r})"

        missing = REQUIRED_ARTICLE_FIELDS - article.keys()
        if missing:
            errors.append(f"{loc}: missing fields {sorted(missing)}")
            continue

        for err in check_url(article["url"]):
            errors.append(f"{loc}: {err}")

        if article["category"] not in KNOWN_CATEGORIES:
            errors.append(
                f"{loc}: undocumented category {article['category']!r} "
                f"(add it to README.md and KNOWN_CATEGORIES)"
            )

        if article["url"] in seen_urls:
            errors.append(f"{loc}: duplicate URL within {file_label}: {article['url']}")
        seen_urls.add(article["url"])

    return errors


def main() -> int:
    files = [REPO_ROOT / "feed.json", *sorted((REPO_ROOT / "pushes").glob("*.json"))]
    all_errors = []

    for path in files:
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        all_errors.extend(validate_articles(data.get("articles", []), path.name))

    if all_errors:
        print(f"Found {len(all_errors)} issue(s):\n")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("All feed files look good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
