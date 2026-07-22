---
name: "ai-news-feed"
title: "AI News Feed"
category: "productivity"
version: "1.0.0"
description: "Aggregates AI and agentic-AI news from 14 RSS feeds + 10 X/Twitter accounts, pushes batches to pushes/*.json, and maintains a rolling latest-50 feed.json that Zo renders as the AI news page."
tags:
  - news
  - aggregation
  - ai-research
  - rss
  - twitter
changelog:
  "1.0.0": "Jul 22, 2026 — Initial SKILL.md. Extracted news_engine.py to own the mechanical rules (link-quality checks, feed-window merge, push-batch rebuild, filename derivation) that were previously re-derived by hand each push. Written after auditing feed.json and finding most articles linked to account profile pages or generic landing pages instead of the specific post — see Pitfalls."
platforms: [macos, linux, windows]
required_environment_variables: []
---

# AI News Feed

Aggregation skill that watches 14 RSS feeds and 10 X/Twitter accounts for AI/agentic-AI news, writes a batch summary each push, and keeps `feed.json` as a rolling window of the latest 50 articles for Zo to render.

---

## Role & Ownership

Each push cycle:
1. Pull new items from the RSS feeds + X/Twitter accounts (`~/.hermes/scripts/ai-feed-fetcher.py`).
2. For each new item: write `title`, pick the correct `url`, judge the `category`, write a 1-2 line `summary`. **This step is judgment — the agent owns it.**
3. Validate the batch, merge it into `feed.json`, and archive it to `pushes/YYYY-MM-DD-HHMM.json`. **This step is mechanical — `news_engine.py` owns it.**

The dividing line: anything that requires reading and understanding a story (what it's about, which bucket it belongs in, how to summarize it) is the agent's job. Anything that's "given this data, compute this value" — is this URL a real post or a profile page, does this batch fit in the 50-article window, what filename does this timestamp map to — is `news_engine.py`'s job. Don't re-derive the latter by hand; call the script and trust its output.

---

## Schema

```json
{
  "updated_at": "2026-07-22T12:00:00+08:00",
  "source": "hermes-ai-reporter",
  "article_count": 28,
  "tldr": "One-paragraph summary of this batch — judgment, written by the agent",
  "articles": [
    {
      "title": "Article headline",
      "url": "https://x.com/AnthropicAI/status/1234567890123456789",
      "category": "ai_models | agents_tooling | hermes_nous | anthropic | deepseek | chinese_ai | platforms_integration | ai_research | industry | moonshot_ai | policy | zo_computer",
      "published": "2026-07-22",
      "summary": "1-2 line summary of what this is about"
    }
  ]
}
```

`pushes/YYYY-MM-DD-HHMM.json` uses the same article schema under a `pushed_at` + `tldr` + `articles` batch, one file per push.

---

## Link Quality (do NOT eyeball this — run the script)

**Rule: `url` must point at the specific post, never at a profile or generic landing page.** This has been the single biggest source of a bad reader experience in this feed — as of the Jul 22 batch, several articles still link to `https://x.com/AccountName` (no `/status/<id>`) or a placeholder status ID like `.../status/launch`, and five separate OpenAI stories all pointed at the same `openai.com/news/` landing page instead of each story's own URL.

Before writing an article's `url` into a batch, if the source is a social post, capture the post's own permalink (`https://x.com/<handle>/status/<numeric id>`), not the account URL. If the source is a blog/newsroom with a shared index page, find that specific post's page, not the section index.

Before pushing a batch, run:

```bash
python3 ~/.hermes/skills/productivity/ai-news-feed/scripts/news_engine.py validate --file <path-to-batch-or-feed.json>
```

Returns `{"valid": bool, "issue_count": int, "issues": [{"index", "title", "type", "detail"}, ...]}`. `type` is one of `missing_fields`, `profile_link`, `malformed_status_id`, `undocumented_category`, `duplicate_url`. **If `valid` is false, fix every issue before pushing** — do not ship a batch with unresolved `profile_link` or `malformed_status_id` issues; go back to the source and find the real permalink rather than falling back to the account page.

<details><summary>Reference rule (context only — the script owns this logic)</summary>

- `https://x.com/<handle>` or `https://twitter.com/<handle>` with no `/status/` suffix → `profile_link`
- `/status/<id>` where `<id>` is not purely numeric → `malformed_status_id`
- Same `url` appearing twice in one file → `duplicate_url`

</details>

---

## Feed Window Maintenance (do NOT merge by hand)

`feed.json` is a rolling window of the latest 50 articles. After validating a new batch, merge it in with:

```bash
python3 ~/.hermes/skills/productivity/ai-news-feed/scripts/news_engine.py merge \
    --existing-file feed.json --new-file <new-batch.json> --max-articles 50 --out feed.json
```

Returns `{"articles": [...], "article_count": int, "duplicate_urls": [...], "dropped_overflow": [...]}`. This dedupes by URL (the new copy wins — useful when a link gets corrected in a later batch), sorts by `published` descending, and caps at 50. `article_count` in the output already matches `len(articles)` — copy it verbatim into `feed.json`, don't recount.

**If `feed.json`'s history looks inconsistent** (e.g. `article_count` doesn't match the article list, or you suspect a bad merge happened), rebuild it from scratch across the full `pushes/` archive instead of patching by hand:

```bash
python3 ~/.hermes/skills/productivity/ai-news-feed/scripts/news_engine.py rebuild --pushes-dir pushes --max-articles 50 --out feed.json
```

This recomputes the same 50-article window from every push batch in date order — later batches win on duplicate URLs, same rule as `merge`. You still need to hand-write `updated_at`, `source`, and `tldr` into the output — the script doesn't fabricate those (see Role & Ownership).

Sanity-check the final file before pushing:

```bash
python3 ~/.hermes/skills/productivity/ai-news-feed/scripts/news_engine.py count-check --file feed.json
```

## Push Archive Filename

`pushes/*.json` filenames are `YYYY-MM-DD-HHMM.json` derived from the push timestamp — don't hand-type it:

```bash
python3 ~/.hermes/skills/productivity/ai-news-feed/scripts/news_engine.py filename --pushed-at "2026-07-22T12:00:00+08:00"
```

Returns `{"filename": "2026-07-22-1200.json"}`.

---

## Pitfalls

- **Profile-link / landing-page bug (audited Jul 22, 2026):** An audit of the live feed found the majority of X/Twitter-sourced articles linked to the account's profile page instead of the specific post, plus non-numeric placeholder status IDs (`.../status/launch`, `.../status/announcement`) and five distinct OpenAI stories all pointing at the shared `openai.com/news/` index instead of their own pages. This is the exact failure `news_engine.py validate` exists to catch — run it on every batch before pushing, not just when something looks wrong.
- **`article_count` drift:** Don't hand-type `article_count` in `feed.json` or a push batch — it must equal `len(articles)`. Use the `merge`/`rebuild` output directly, or run `count-check` before pushing.
- **Category drift:** `KNOWN_CATEGORIES` in `news_engine.py` and the schema table above must stay in sync. If a new category is genuinely needed, add it to both in the same change — don't let the data silently drift ahead of the docs (this happened once already: `ai_research`, `industry`, `moonshot_ai`, `policy`, `zo_computer` were in use for several pushes before the schema doc caught up).
