import logging
from src.models import FeedItem, AppConfig


log = logging.getLogger(__name__)


def apply_filters(items: list[FeedItem], config: AppConfig) -> tuple[list[FeedItem], dict]:
    """
    Apply ignore/include filters to articles.

    Returns:
      - filtered_items: Items after applying ignore + reordering includes to front
      - stats: {"ignored_count": int, "included_count": int}
    """
    if not config.filters_ignore and not config.filters_include:
        return items, {"ignored_count": 0, "included_count": 0}

    not_ignored = []
    ignored_count = 0

    for item in items:
        combined_text = (item.title + " " + item.summary).lower()
        if any(keyword.lower() in combined_text for keyword in config.filters_ignore):
            ignored_count += 1
            log.debug(f"Ignored article: {item.title}")
            continue
        not_ignored.append(item)

    included = []
    normal = []

    for item in not_ignored:
        combined_text = (item.title + " " + item.summary).lower()
        if any(keyword.lower() in combined_text for keyword in config.filters_include):
            included.append(item)
            log.debug(f"Included article: {item.title}")
        else:
            normal.append(item)

    filtered = included + normal
    return filtered, {"ignored_count": ignored_count, "included_count": len(included)}
