#!/usr/bin/env python3
"""Stdlib-only unit tests for news_engine.py — no new dependency."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import news_engine as ne


def _article(**overrides):
    base = {
        "title": "Some AI headline",
        "url": "https://x.com/AnthropicAI/status/1234567890",
        "category": "anthropic",
        "published": "2026-07-20",
        "summary": "A summary.",
    }
    base.update(overrides)
    return base


class TestLinkQuality(unittest.TestCase):
    def test_profile_only_link_flagged(self):
        issues = ne.check_link_quality("https://x.com/AnthropicAI")
        self.assertIn("profile_link", issues)

    def test_twitter_domain_also_flagged(self):
        issues = ne.check_link_quality("https://twitter.com/OpenAI")
        self.assertIn("profile_link", issues)

    def test_status_link_is_fine(self):
        issues = ne.check_link_quality("https://x.com/AnthropicAI/status/1234567890")
        self.assertEqual(issues, [])

    def test_non_numeric_status_id_flagged(self):
        issues = ne.check_link_quality("https://x.com/Kimi_Moonshot/status/eFHEbdxn3P")
        self.assertIn("malformed_status_id", issues)

    def test_non_social_url_is_fine(self):
        issues = ne.check_link_quality("https://techcrunch.com/2026/07/19/some-article/")
        self.assertEqual(issues, [])


class TestValidateArticles(unittest.TestCase):
    def test_clean_list_is_valid(self):
        result = ne.validate_articles([_article()])
        self.assertTrue(result["valid"])
        self.assertEqual(result["issue_count"], 0)

    def test_missing_field_flagged(self):
        bad = _article()
        del bad["summary"]
        result = ne.validate_articles([bad])
        self.assertFalse(result["valid"])
        self.assertEqual(result["issues"][0]["type"], "missing_fields")

    def test_profile_link_flagged(self):
        result = ne.validate_articles([_article(url="https://x.com/OpenAI")])
        self.assertFalse(result["valid"])
        self.assertEqual(result["issues"][0]["type"], "profile_link")

    def test_undocumented_category_flagged(self):
        result = ne.validate_articles([_article(category="not_a_real_category")])
        types = [i["type"] for i in result["issues"]]
        self.assertIn("undocumented_category", types)

    def test_duplicate_url_flagged(self):
        a = _article(title="First")
        b = _article(title="Second")  # same default url as a
        result = ne.validate_articles([a, b])
        types = [i["type"] for i in result["issues"]]
        self.assertIn("duplicate_url", types)

    def test_multiple_articles_all_clean(self):
        articles = [
            _article(url="https://x.com/AnthropicAI/status/1"),
            _article(url="https://x.com/AnthropicAI/status/2"),
        ]
        result = ne.validate_articles(articles)
        self.assertTrue(result["valid"])


class TestMergeIntoFeed(unittest.TestCase):
    def test_new_article_appended(self):
        existing = [_article(url="https://a.com/1", published="2026-07-19")]
        new = [_article(url="https://a.com/2", published="2026-07-20")]
        result = ne.merge_into_feed(existing, new, max_articles=50)
        urls = [a["url"] for a in result["articles"]]
        self.assertEqual(urls, ["https://a.com/2", "https://a.com/1"])

    def test_sorted_by_published_descending(self):
        existing = [_article(url="https://a.com/1", published="2026-07-01")]
        new = [_article(url="https://a.com/2", published="2026-07-20")]
        result = ne.merge_into_feed(existing, new, max_articles=50)
        published = [a["published"] for a in result["articles"]]
        self.assertEqual(published, sorted(published, reverse=True))

    def test_duplicate_url_new_copy_wins(self):
        existing = [_article(url="https://a.com/1", summary="old summary")]
        new = [_article(url="https://a.com/1", summary="corrected summary")]
        result = ne.merge_into_feed(existing, new, max_articles=50)
        self.assertEqual(len(result["articles"]), 1)
        self.assertEqual(result["articles"][0]["summary"], "corrected summary")
        self.assertIn("https://a.com/1", result["duplicate_urls"])

    def test_overflow_dropped_and_reported(self):
        existing = [_article(url=f"https://a.com/{i}", published="2026-07-01") for i in range(3)]
        new = [_article(url="https://a.com/new", published="2026-07-20")]
        result = ne.merge_into_feed(existing, new, max_articles=2)
        self.assertEqual(result["article_count"], 2)
        self.assertEqual(len(result["dropped_overflow"]), 2)

    def test_article_count_matches_list_length(self):
        existing = [_article(url="https://a.com/1")]
        new = [_article(url="https://a.com/2")]
        result = ne.merge_into_feed(existing, new)
        self.assertEqual(result["article_count"], len(result["articles"]))


class TestRebuildFromPushes(unittest.TestCase):
    def test_later_batch_wins_on_duplicate(self):
        batch1 = {"articles": [_article(url="https://a.com/1", summary="v1")]}
        batch2 = {"articles": [_article(url="https://a.com/1", summary="v2")]}
        result = ne.rebuild_feed_from_pushes([batch1, batch2])
        self.assertEqual(len(result["articles"]), 1)
        self.assertEqual(result["articles"][0]["summary"], "v2")

    def test_accumulates_across_batches(self):
        batch1 = {"articles": [_article(url="https://a.com/1", published="2026-07-01")]}
        batch2 = {"articles": [_article(url="https://a.com/2", published="2026-07-02")]}
        result = ne.rebuild_feed_from_pushes([batch1, batch2])
        self.assertEqual(result["article_count"], 2)

    def test_respects_max_articles_across_batches(self):
        batches = [
            {"articles": [_article(url=f"https://a.com/{i}", published=f"2026-07-{i:02d}")]}
            for i in range(1, 6)
        ]
        result = ne.rebuild_feed_from_pushes(batches, max_articles=3)
        self.assertEqual(result["article_count"], 3)


class TestPushFilename(unittest.TestCase):
    def test_derives_canonical_name(self):
        self.assertEqual(
            ne.push_filename("2026-07-22T12:00:00+08:00"),
            "2026-07-22-1200.json",
        )

    def test_midnight_minute_padding(self):
        self.assertEqual(
            ne.push_filename("2026-07-05T08:05:00+08:00"),
            "2026-07-05-0805.json",
        )


class TestCountConsistency(unittest.TestCase):
    def test_consistent_when_matching(self):
        feed = {"article_count": 2, "articles": [_article(), _article()]}
        result = ne.check_count_consistency(feed)
        self.assertTrue(result["consistent"])

    def test_flags_mismatch(self):
        feed = {"article_count": 5, "articles": [_article()]}
        result = ne.check_count_consistency(feed)
        self.assertFalse(result["consistent"])
        self.assertEqual(result["declared"], 5)
        self.assertEqual(result["actual"], 1)


if __name__ == "__main__":
    unittest.main()
