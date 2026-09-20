# AI News Feed

Aggregated AI and agentic news from the Hermes Agent AI Reporter.

## Structure

```
├── feed.json       ← Rolling 7-day window of articles, capped at 60 (Zo's endpoint)
├── pushes/         ← Individual batch files (YYYY-MM-DD-HHMM.json)
└── README.md       ← You're here
```

`feed.json` is not a single run's batch. Every push merges that run's new
articles into the existing file via `~/.hermes/scripts/news-feed-merge.py`,
which keeps anything published in the last 7 days, dedupes by URL (the new
batch's copy wins) and caps the result at 60 articles, newest first.

## `feed.json` Schema

```json
{
  "updated_at": "2026-09-20T08:18:17+08:00",
  "source": "hermes-ai-reporter",
  "article_count": 36,
  "tldr": "Summary of this push, 3-5 short plain-English sentences",
  "articles": [
    {
      "title": "Article headline",
      "url": "https://...",
      "category": "ai_models",
      "published": "2026-09-20",
      "summary": "1-2 line summary of what this is about"
    }
  ]
}
```

Categories in use: `ai_models`, `agents_tooling`, `hermes_nous`, `anthropic`,
`deepseek`, `chinese_ai`, `platforms_integration`, `ai_research`, `policy`,
`industry`, `moonshot_ai`, `zo_computer`.

## Raw Data Source

Pulled by the Hermes AI Reporter Feed Fetcher (`~/.hermes/scripts/ai-feed-fetcher.py`)
from 14 RSS feeds, plus the X Multi-Scanner across 18 accounts. Pushed three
times a day (08:15, 13:15, 21:15 SGT) by the GitHub AI News Publisher cron.

## Usage

Zo reads `https://raw.githubusercontent.com/chintheman/ai-news-feed/main/feed.json`
to render the AI news page.
