# AI News Feed

Aggregated AI and agentic news from the Hermes Agent AI Reporter.

## Structure

```
├── feed.json       ← Latest 50 articles (Zo's endpoint)
├── pushes/         ← Individual batch files (YYYY-MM-DD-HHMM.json)
├── skill/          ← SKILL.md + news_engine.py (the mechanical rules behind this data)
└── README.md       ← You're here
```

## `feed.json` Schema

```json
{
  "updated_at": "2026-07-18T21:00:00+08:00",
  "source": "hermes-ai-reporter",
  "tldr": "One-paragraph summary of this batch",
  "articles": [
    {
      "title": "Article headline",
      "url": "https://...",
      "category": "ai_models | agents_tooling | hermes_nous | anthropic | deepseek | chinese_ai | platforms_integration | ai_research | industry | moonshot_ai | policy | zo_computer",
      "published": "2026-07-18",
      "summary": "1-2 line summary of what this is about"
    }
  ]
}
```

### Link quality

`url` must point at the specific post/article, never at an account's profile
page (e.g. `https://x.com/AnthropicAI/status/1234567890`, not
`https://x.com/AnthropicAI`) or a generic landing page. A profile-only link
forces the reader to go hunt for the actual source, which defeats the point
of the feed. This is enforced by `skill/scripts/news_engine.py` — see
`skill/SKILL.md` for the full rule set (link validation, the rolling
50-article window, push-batch merging) that governs how this data gets
produced.

## Raw Data Source

Pulled by the Hermes AI Reporter Feed Fetcher (`~/.hermes/scripts/ai-feed-fetcher.py`) from 14 RSS feeds + 10 X/Twitter accounts.

## Usage

Zo reads `https://raw.githubusercontent.com/chintheman/ai-news-feed/main/feed.json` to render the AI news page.
