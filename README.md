# AI News Feed

Aggregated AI and agentic news from the Hermes Agent AI Reporter.

## Structure

```
├── feed.json       ← Latest 50 articles (Zo's endpoint)
├── pushes/         ← Individual batch files (YYYY-MM-DD-HHMM.json)
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
      "category": "ai_models | agents_tooling | hermes_nous | anthropic | deepseek | chinese_ai | platforms_integration",
      "published": "2026-07-18",
      "summary": "1-2 line summary of what this is about"
    }
  ]
}
```

## Raw Data Source

Pulled by the Hermes AI Reporter Feed Fetcher (`~/.hermes/scripts/ai-feed-fetcher.py`) from 14 RSS feeds + 10 X/Twitter accounts.

## Usage

Zo reads `https://raw.githubusercontent.com/chintheman/ai-news-feed/main/feed.json` to render the AI news page.
