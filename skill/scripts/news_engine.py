#!/usr/bin/env python3
"""
News engine — deterministic rules for the AI News Feed skill.

Anything that's "given this data, compute this value" lives here instead of
in SKILL.md prose: link-quality checks, category validation, the rolling
50-article feed window, push-batch merging, and push-filename derivation.
SKILL.md should call these via the CLI below and trust the output rather
than re-deriving any of it — categorising a story or writing its summary
is judgment and stays with the agent; everything below is not.

Importable for direct use:
    from news_engine import validate_articles, merge_into_feed, ...

Also callable from Hermes sessions via terminal (prints compact single-line
JSON to stdout, since output feeds the agent's next reasoning step):
    python3 news_engine.py validate --file feed.json
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# skill/scripts/news_engine.py -> repo root is two levels up.
REPO_ROOT = Path(os.environ.get("NEWS_FEED_REPO_ROOT", Path(__file__).resolve().parents[2]))
FEED_PATH = REPO_ROOT / "feed.json"
PUSHES_DIR = REPO_ROOT / "pushes"

REQUIRED_ARTICLE_FIELDS = ["title", "url", "category", "published", "summary"]

# Every category actually in use across feed.json/pushes/*.json as of this
# writing. Keep in sync with SKILL.md's schema table — an article with a
# category outside this set is a documentation gap, not necessarily a bug.
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

_SOCIAL_PROFILE_RE = re.compile(r"^https?://(www\.)?(x|twitter)\.com/([^/?#]+)/?$")
_SOCIAL_STATUS_RE = re.compile(r"^https?://(www\.)?(x|twitter)\.com/[^/]+/status/([^/?#]+)/?$")


def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _save_json(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def check_link_quality(url: str) -> list[str]:
    """
    Flag the #1 recurring feed bug: a social link that points at an
    account's profile instead of the specific post. Also flags status IDs
    that are non-numeric, which is the signature of a fabricated/placeholder
    link rather than a real captured post.

    Returns a list of issue strings (empty if the URL is fine).
    """
    issues = []
    if _SOCIAL_PROFILE_RE.match(url):
        issues.append("profile_link")
    m = _SOCIAL_STATUS_RE.match(url)
    if m and not m.group(3).isdigit():
        issues.append("malformed_status_id")
    return issues


def validate_articles(articles: list) -> dict:
    """
    Validate a list of articles against the feed schema. Encodes as code
    what used to be prose review: required fields present, category in the
    documented enum, URL points at a specific post (not a profile page),
    status IDs are numeric, and no duplicate URLs within the list.

    Returns:
        {
          "valid": bool,
          "issue_count": int,
          "issues": [
            {"index": int, "title": str, "type": str, "detail": str}, ...
          ],
        }
    """
    issues = []
    seen_urls = {}

    for i, article in enumerate(articles):
        title = article.get("title", "<no title>")

        missing = [f for f in REQUIRED_ARTICLE_FIELDS if f not in article]
        if missing:
            issues.append({
                "index": i, "title": title, "type": "missing_fields",
                "detail": f"missing {missing}",
            })
            continue

        for link_issue in check_link_quality(article["url"]):
            if link_issue == "profile_link":
                detail = f"links to a profile page, not a specific post: {article['url']}"
            else:
                detail = f"status ID is not numeric (likely a placeholder/fake link): {article['url']}"
            issues.append({"index": i, "title": title, "type": link_issue, "detail": detail})

        if article["category"] not in KNOWN_CATEGORIES:
            issues.append({
                "index": i, "title": title, "type": "undocumented_category",
                "detail": f"category {article['category']!r} is not in KNOWN_CATEGORIES",
            })

        if article["url"] in seen_urls:
            issues.append({
                "index": i, "title": title, "type": "duplicate_url",
                "detail": f"same URL as index {seen_urls[article['url']]}: {article['url']}",
            })
        else:
            seen_urls[article["url"]] = i

    return {"valid": len(issues) == 0, "issue_count": len(issues), "issues": issues}


def merge_into_feed(existing_articles: list, new_articles: list, max_articles: int = 50) -> dict:
    """
    Fold a new push batch into the rolling feed window. This is the "latest
    N articles" rule that used to be re-derived by hand each push: dedup by
    URL (the new copy of an article wins — it may carry a corrected
    link/summary), sort by `published` descending, then cap at
    `max_articles`.

    Args:
        existing_articles: current feed.json["articles"]
        new_articles: articles from the batch being pushed
        max_articles: rolling window size (feed.json uses 50)

    Returns:
        {
          "articles": [...],       # merged, deduped, sorted, capped
          "article_count": int,
          "duplicate_urls": [...], # URLs present in both existing and new
          "dropped_overflow": [...],  # titles dropped for exceeding max_articles
        }
    """
    by_url = {}
    order = []
    for a in existing_articles:
        by_url[a["url"]] = a
        order.append(a["url"])

    duplicate_urls = []
    for a in new_articles:
        if a["url"] in by_url:
            duplicate_urls.append(a["url"])
        else:
            order.append(a["url"])
        by_url[a["url"]] = a  # new copy wins on conflict

    merged = [by_url[u] for u in order]
    merged.sort(key=lambda a: a.get("published", ""), reverse=True)

    kept = merged[:max_articles]
    dropped = merged[max_articles:]

    return {
        "articles": kept,
        "article_count": len(kept),
        "duplicate_urls": duplicate_urls,
        "dropped_overflow": [a["title"] for a in dropped],
    }


def rebuild_feed_from_pushes(push_batches: list, max_articles: int = 50) -> dict:
    """
    Recompute the rolling feed window from scratch across a set of push
    batches, for recovery/audit when feed.json's incremental history is in
    doubt. Batches must be given oldest-first — later batches win on
    duplicate URLs, same as a normal sequence of merge_into_feed() calls.

    Args:
        push_batches: list of parsed pushes/*.json contents, oldest first
        max_articles: rolling window size

    Returns: same shape as merge_into_feed()
    """
    result = {"articles": [], "article_count": 0, "duplicate_urls": [], "dropped_overflow": []}
    for batch in push_batches:
        merged = merge_into_feed(result["articles"], batch.get("articles", []), max_articles)
        result["articles"] = merged["articles"]
        result["article_count"] = merged["article_count"]
        result["duplicate_urls"].extend(merged["duplicate_urls"])
        result["dropped_overflow"].extend(merged["dropped_overflow"])
    return result


def push_filename(pushed_at_iso: str) -> str:
    """
    Derive the canonical pushes/*.json filename from a pushed_at timestamp.
    The convention (YYYY-MM-DD-HHMM.json, local time as given) is exactly
    the kind of thing that drifts if typed by hand under a fast-moving
    push — compute it instead.
    """
    dt = datetime.fromisoformat(pushed_at_iso)
    return dt.strftime("%Y-%m-%d-%H%M") + ".json"


def check_count_consistency(feed_obj: dict) -> dict:
    """
    Verify article_count matches len(articles). A silent mismatch here is
    exactly the class of bug that bit block-week state in the health &
    wellness skill (stored value drifting from the derived one) — cheaper
    to catch with a script than to eyeball a 50-item list.
    """
    declared = feed_obj.get("article_count")
    actual = len(feed_obj.get("articles", []))
    return {"consistent": declared == actual, "declared": declared, "actual": actual}


# ── CLI entry point (for Hermes terminal() calls) ──────────────────────

def _print_result(result) -> None:
    print(json.dumps(result, separators=(",", ":")))


def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="News engine — deterministic AI-news-feed rules")
    sub = parser.add_subparsers(dest="cmd")

    v = sub.add_parser("validate")
    v.add_argument("--file", help="path to a feed.json-shaped file (defaults to feed.json)")
    v.add_argument("--articles-json", help="inline JSON array of articles, instead of --file")

    m = sub.add_parser("merge")
    m.add_argument("--existing-file", required=True)
    m.add_argument("--new-file", required=True)
    m.add_argument("--max-articles", type=int, default=50)
    m.add_argument("--out", help="if set, write the merged feed.json here")

    r = sub.add_parser("rebuild")
    r.add_argument("--pushes-dir", default=str(PUSHES_DIR))
    r.add_argument("--max-articles", type=int, default=50)
    r.add_argument("--out", help="if set, write the rebuilt feed.json here")

    f = sub.add_parser("filename")
    f.add_argument("--pushed-at", required=True)

    c = sub.add_parser("count-check")
    c.add_argument("--file", help="path to a feed.json-shaped file (defaults to feed.json)")

    args = parser.parse_args()

    try:
        if args.cmd == "validate":
            if args.articles_json:
                articles = json.loads(args.articles_json)
            else:
                articles = _load_json(Path(args.file) if args.file else FEED_PATH)["articles"]
            _print_result(validate_articles(articles))

        elif args.cmd == "merge":
            existing = _load_json(Path(args.existing_file))["articles"]
            new = _load_json(Path(args.new_file))["articles"]
            result = merge_into_feed(existing, new, args.max_articles)
            if args.out:
                _save_json(Path(args.out), result)
            _print_result(result)

        elif args.cmd == "rebuild":
            pushes_dir = Path(args.pushes_dir)
            batches = [
                _load_json(p) for p in sorted(pushes_dir.glob("*.json"))
            ]
            result = rebuild_feed_from_pushes(batches, args.max_articles)
            if args.out:
                _save_json(Path(args.out), result)
            _print_result(result)

        elif args.cmd == "filename":
            _print_result({"filename": push_filename(args.pushed_at)})

        elif args.cmd == "count-check":
            feed = _load_json(Path(args.file) if args.file else FEED_PATH)
            _print_result(check_count_consistency(feed))

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    _cli()
