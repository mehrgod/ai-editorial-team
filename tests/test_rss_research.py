import unittest
from datetime import datetime, timezone
from typing import List

from ai_editorial_team.infrastructure.research.rss_agents import (
    RssArticle,
    RssResearchAgent,
    RssResearchConfig,
)


class FakeNewsworthinessAgent:
    def __init__(self, accepted_headlines: set[str]) -> None:
        self.accepted_headlines = accepted_headlines
        self.received_stories = []

    def assess_story(self, story):
        self.received_stories.append(story)
        return {
            "is_newsworthy": story["headline"] in self.accepted_headlines,
            "reason": f"Assessed {story['headline']}.",
        }


class FakeRssResearchAgent(RssResearchAgent):
    def __init__(self, articles: List[RssArticle], **kwargs) -> None:
        super().__init__(
            config=RssResearchConfig(domain="Sports", feeds=[]),
            **kwargs,
        )
        self._articles = articles

    def _fetch_all_articles(self):
        return self._articles, []


class RssResearchNewsworthinessTests(unittest.TestCase):
    def test_selects_first_newsworthy_article_from_recent_candidates(self):
        articles = [
            _article("Old real news", "Old summary", "2026-09-08T12:00:00Z"),
            _article("Draft Guide", "Rankings and mock drafts", "2026-09-09T12:00:00Z"),
            _article("Team signs star", "Contract announced", "2026-09-09T10:00:00Z"),
        ]
        newsworthiness_agent = FakeNewsworthinessAgent({"Team signs star"})
        research_agent = FakeRssResearchAgent(
            articles,
            newsworthiness_agent=newsworthiness_agent,
            max_newsworthiness_candidates=10,
        )

        story = research_agent.research()

        self.assertEqual(story["headline"], "Team signs star")
        self.assertEqual(
            [story["headline"] for story in newsworthiness_agent.received_stories],
            ["Draft Guide", "Team signs star"],
        )
        self.assertIn("Selected as a newsworthy article", story["reason"])

    def test_returns_pending_story_when_no_recent_candidate_is_newsworthy(self):
        articles = [
            _article("Draft Guide", "Rankings and mock drafts", "2026-09-09T12:00:00Z"),
            _article(
                "Betting odds", "Lines for upcoming games", "2026-09-09T10:00:00Z"
            ),
        ]
        newsworthiness_agent = FakeNewsworthinessAgent(set())
        research_agent = FakeRssResearchAgent(
            articles,
            newsworthiness_agent=newsworthiness_agent,
            max_newsworthiness_candidates=10,
        )

        story = research_agent.research()

        self.assertEqual(story["headline"], "Sports news pending")
        self.assertIn("Sports news is still coming in", story["summary"])
        self.assertIn("assessing 2 recent article(s)", story["reason"])

    def test_newsworthiness_assessment_is_bounded(self):
        articles = [
            _article(f"Candidate {index}", "Summary", f"2026-09-09T1{index}:00:00Z")
            for index in range(4)
        ]
        newsworthiness_agent = FakeNewsworthinessAgent({"Candidate 0"})
        research_agent = FakeRssResearchAgent(
            articles,
            newsworthiness_agent=newsworthiness_agent,
            max_newsworthiness_candidates=2,
        )

        story = research_agent.research()

        self.assertEqual(story["headline"], "Sports news pending")
        self.assertEqual(len(newsworthiness_agent.received_stories), 2)


def _article(title: str, summary: str, published: str) -> RssArticle:
    return RssArticle(
        title=title,
        summary=summary,
        published_at=datetime.fromisoformat(
            published.replace("Z", "+00:00")
        ).astimezone(timezone.utc),
        source_name="Test Feed",
    )


if __name__ == "__main__":
    unittest.main()
