import asyncio
import logging
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import httpx
import feedparser
from src.models import FeedItem, AppConfig


log = logging.getLogger(__name__)


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return "".join(self.text).strip()


def strip_html(html_text):
    if not html_text:
        return ""
    stripper = HTMLStripper()
    try:
        stripper.feed(html_text)
        return stripper.get_text()
    except Exception:
        return html_text


async def fetch_all_feeds(config: AppConfig) -> list[FeedItem]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        tasks = [_fetch_one(client, feed) for feed in config.feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    items = []
    for result in results:
        if isinstance(result, Exception):
            log.warning(f"Feed fetch failed: {result}")
        elif result:
            items.extend(result)

    return items


async def _fetch_one(client: httpx.AsyncClient, feed_config: dict) -> list[FeedItem]:
    url = feed_config["url"]
    name = feed_config["name"]

    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception as e:
        log.warning(f"Failed to fetch {name} from {url}: {e}")
        return []

    try:
        parsed = feedparser.parse(response.text)
    except Exception as e:
        log.warning(f"Failed to parse {name}: {e}")
        return []

    items = []
    for entry in parsed.entries[: 20]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "").strip()
        summary = strip_html(summary)

        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        if title and link:
            items.append(
                FeedItem(
                    title=title,
                    url=link,
                    summary=summary,
                    source=name,
                    published=published,
                )
            )

    log.info(f"Fetched {len(items)} items from {name}")
    return items
