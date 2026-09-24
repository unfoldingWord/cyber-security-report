import logging
from src.models import FeedItem, AppConfig


log = logging.getLogger(__name__)


def apply_filters(items: list[FeedItem], config: AppConfig) -> tuple[list[FeedItem], dict]:
    """
    Apply the deterministic ignore backstop.

    Relevance ("is this about a system we run?") is judged by the LLM against the
    environment profile, not here — keyword whitelisting was too brittle (surface
    matches on unrelated stories, and misses relevant items phrased differently).
    This layer only hard-drops known noise so it never reaches the LLM.

    Returns:
      - kept_items: Items that matched no ignore pattern, order preserved
      - stats: {"ignored_count": int}
    """
    if not config.filters_ignore:
        return items, {"ignored_count": 0}

    kept = []
    ignored_count = 0

    for item in items:
        combined_text = item.title + " " + item.summary
        if any(pattern.search(combined_text) for pattern in config.filters_ignore):
            ignored_count += 1
            log.debug(f"Ignored article: {item.title}")
            continue
        kept.append(item)

    return kept, {"ignored_count": ignored_count}
