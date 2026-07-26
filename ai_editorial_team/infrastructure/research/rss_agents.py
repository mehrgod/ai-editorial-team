from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import re
from typing import Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from ai_editorial_team.domain.models import Story
from ai_editorial_team.domain.ports import ResearchAgent


class RssFeedError(RuntimeError):
    """Raised when a feed cannot produce a candidate story."""


@dataclass(frozen=True)
class RssFeedConfig:
    source_name: str
    feed_url: str


@dataclass(frozen=True)
class RssResearchConfig:
    domain: str
    feeds: List[RssFeedConfig]


@dataclass(frozen=True)
class RssArticle:
    title: str
    summary: str
    published_at: Optional[datetime]
    source_name: str


@dataclass(frozen=True)
class RssResearchAgent:
    """Research agent backed by one or more RSS feeds."""

    config: RssResearchConfig
    timeout_seconds: float = 6.0

    def research(self) -> Story:
        articles, failures = self._fetch_all_articles()
        if not articles:
            raise RssFeedError(
                f"{self.config.domain} RSS feeds did not return any articles. "
                f"Failures: {'; '.join(failures)}"
            )

        article = self._select_recent_article(articles)
        return {
            "domain": self.config.domain,
            "headline": article.title,
            "summary": article.summary,
            "reason": (
                f"Selected as the most recent article from "
                f"{article.source_name}."
            ),
        }

    def _fetch_all_articles(self) -> Tuple[List[RssArticle], List[str]]:
        if not self.config.feeds:
            return [], [f"No RSS feeds configured for {self.config.domain}."]

        articles: List[RssArticle] = []
        failures: List[str] = []

        for feed in self.config.feeds:
            try:
                articles.extend(self._fetch_articles(feed))
            except RssFeedError as exc:
                failures.append(str(exc))

        return articles, failures

    def _fetch_articles(self, feed: RssFeedConfig) -> List[RssArticle]:
        request = Request(
            feed.feed_url,
            headers={"User-Agent": "ai-editorial-team/0.1"},
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            raise RssFeedError(
                f"{self.config.domain} RSS feed unavailable "
                f"from {feed.source_name} "
                f"({exc.code} {exc.reason}): {feed.feed_url}"
            ) from exc
        except URLError as exc:
            raise RssFeedError(
                f"{self.config.domain} RSS feed unavailable "
                f"from {feed.source_name} "
                f"({exc.reason}): {feed.feed_url}"
            ) from exc
        except TimeoutError as exc:
            raise RssFeedError(
                f"{self.config.domain} RSS feed timed out "
                f"from {feed.source_name}: {feed.feed_url}"
            ) from exc

        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise RssFeedError(
                f"{self.config.domain} RSS feed returned invalid XML "
                f"from {feed.source_name}: {feed.feed_url}"
            ) from exc

        articles = self._parse_rss_articles(root, feed.source_name)
        if articles:
            return articles

        articles = self._parse_atom_articles(root, feed.source_name)
        if articles:
            return articles

        raise RssFeedError(
            f"{self.config.domain} RSS feed returned no articles "
            f"from {feed.source_name}: {feed.feed_url}"
        )

    @staticmethod
    def _select_recent_article(articles: Iterable[RssArticle]) -> RssArticle:
        return max(
            articles,
            key=lambda article: article.published_at
            or datetime.min.replace(tzinfo=timezone.utc),
        )

    def _parse_rss_articles(
        self, root: ET.Element, source_name: str
    ) -> List[RssArticle]:
        articles: List[RssArticle] = []

        for item in root.findall(".//channel/item"):
            title = _element_text(item, "title")
            summary = _element_text(item, "description")
            published = _element_text(item, "pubDate") or _element_text(
                item, "{http://purl.org/dc/elements/1.1/}date"
            )
            article = _build_article(title, summary, published, source_name)
            if article:
                articles.append(article)

        return articles

    def _parse_atom_articles(
        self, root: ET.Element, source_name: str
    ) -> List[RssArticle]:
        articles: List[RssArticle] = []

        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title = _element_text(entry, "{http://www.w3.org/2005/Atom}title")
            summary = _element_text(
                entry, "{http://www.w3.org/2005/Atom}summary"
            ) or _element_text(entry, "{http://www.w3.org/2005/Atom}content")
            published = _element_text(
                entry, "{http://www.w3.org/2005/Atom}updated"
            ) or _element_text(entry, "{http://www.w3.org/2005/Atom}published")
            article = _build_article(title, summary, published, source_name)
            if article:
                articles.append(article)

        return articles


def create_finance_research_agent() -> ResearchAgent:
    return RssResearchAgent(
        RssResearchConfig(
            domain="Finance",
            feeds=[
                RssFeedConfig(
                    source_name="CBS News MoneyWatch",
                    feed_url="https://www.cbsnews.com/latest/rss/moneywatch",
                ),
                RssFeedConfig(
                    source_name="BBC News Business",
                    feed_url="https://feeds.bbci.co.uk/news/business/rss.xml",
                ),
                RssFeedConfig(
                    source_name="CNA Business",
                    feed_url=(
                        "https://www.channelnewsasia.com/api/v1/"
                        "rss-outbound-feed?_format=xml&category=6936"
                    ),
                ),
            ],
        )
    )


def create_ai_research_agent() -> ResearchAgent:
    return RssResearchAgent(
        RssResearchConfig(
            domain="Artificial Intelligence",
            feeds=[
                RssFeedConfig(
                    source_name="MIT News Artificial Intelligence",
                    feed_url=(
                        "https://news.mit.edu/topic/"
                        "mitartificial-intelligence2-rss.xml"
                    ),
                ),
                RssFeedConfig(
                    source_name="Google AI Blog",
                    feed_url="https://blog.google/technology/ai/rss/",
                ),
                RssFeedConfig(
                    source_name="Hugging Face Blog",
                    feed_url="https://huggingface.co/blog/feed.xml",
                ),
            ],
        )
    )


def create_sports_research_agent() -> ResearchAgent:
    return RssResearchAgent(
        RssResearchConfig(
            domain="Sports",
            feeds=[
                RssFeedConfig(
                    source_name="ESPN Top Headlines",
                    feed_url="https://www.espn.com/espn/rss/news",
                ),
                RssFeedConfig(
                    source_name="BBC Sport",
                    feed_url="https://feeds.bbci.co.uk/sport/rss.xml",
                ),
                RssFeedConfig(
                    source_name="CBS Sports General Headlines",
                    feed_url="https://www.cbssports.com/rss/headlines/",
                ),
            ],
        )
    )


def _element_text(parent: ET.Element, name: str) -> str:
    element = parent.find(name)
    if element is None or element.text is None:
        return ""
    return _clean_text(element.text)


def _build_article(
    title: str, summary: str, published: str, source_name: str
) -> Optional[RssArticle]:
    if not title:
        return None

    return RssArticle(
        title=title,
        summary=summary or "No summary provided by the RSS feed.",
        published_at=_parse_datetime(published),
        source_name=source_name,
    )


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    without_entities = html.unescape(without_tags)
    return " ".join(without_entities.split())
