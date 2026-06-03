import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from claude_agent_sdk import query, AssistantMessage, TextBlock, ClaudeAgentOptions
from src.models import FeedItem, IntelReport, BriefingItem, AppConfig
from src.filters import apply_filters


log = logging.getLogger(__name__)


class AnalystError(Exception):
    pass


async def analyze(items: list[FeedItem], config: AppConfig) -> IntelReport:
    now = datetime.now(timezone.utc)
    lookback = timedelta(hours=config.lookback_hours)

    filtered = [
        item for item in items
        if item.published is None or (now - item.published) <= lookback
    ]

    deduped = {}
    for item in filtered:
        if item.url not in deduped:
            deduped[item.url] = item

    sorted_items = sorted(
        deduped.values(),
        key=lambda x: x.published or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    filtered_items, filter_stats = apply_filters(sorted_items, config)

    limited = filtered_items[: config.max_items_to_llm]

    log.info(
        f"Pre-LLM: {len(items)} total → {len(filtered)} in lookback → "
        f"{len(deduped)} after dedup → ignored {filter_stats['ignored_count']} → "
        f"{len(filtered_items)} after filters → {len(limited)} for LLM"
    )

    text_block = "\n\n".join(
        f"{item.source} | {item.title} | {item.url}\n{item.summary}"
        for item in limited
    )

    inclusion_note = ""
    if config.filters_include and filter_stats["included_count"] > 0:
        inclusion_note = "\n\nIMPORTANT: The following articles have been flagged as priority topics and should be emphasized in your analysis:\n"
        for item in limited[: filter_stats["included_count"]]:
            inclusion_note += f"  - {item.title}\n"

    prompt = f"""You are a cybersecurity analyst preparing a daily standup briefing.

Analyze these {len(limited)} security news headlines from the last {config.lookback_hours} hours.

<HEADLINES>
{text_block}
</HEADLINES>
{inclusion_note}

Return ONLY valid JSON matching this exact schema:
{{
  "core_situation": ["3-5 short bullet strings summarising the overall threat picture"],
  "key_items": [
    {{
      "severity": "critical|high|medium|threat",
      "title": "Short descriptive title",
      "why_relevant": "One sentence on relevance",
      "action": "Concrete action to take",
      "links": ["https://..."],
      "cve": "CVE-YYYY-NNNNN or null"
    }}
  ],
  "extra_attention": ["1-4 specific things that need attention today"]
}}

No prose before or after the JSON."""

    options = ClaudeAgentOptions(
        tools=[],
        permission_mode="dontAsk",
        max_turns=1,
    )

    text_chunks = []
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
    except Exception as e:
        raise AnalystError(f"LLM query failed: {e}")

    raw_json = "".join(text_chunks)
    raw_json = re.sub(r"^```json\s*", "", raw_json)
    raw_json = re.sub(r"\s*```$", "", raw_json)

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        raise AnalystError(f"Failed to parse LLM JSON response: {e}\nRaw: {raw_json}")

    sources = sorted(set(item.source for item in limited))

    key_items = [
        BriefingItem(
            severity=item_data["severity"],
            title=item_data["title"],
            why_relevant=item_data["why_relevant"],
            action=item_data["action"],
            links=item_data.get("links", []),
            cve=item_data.get("cve"),
        )
        for item_data in data["key_items"]
    ]

    return IntelReport(
        generated_at=now,
        core_situation=data["core_situation"],
        key_items=key_items,
        extra_attention=data["extra_attention"],
        items_analyzed=len(limited),
        sources=sources,
        filtered_ignored_count=filter_stats["ignored_count"],
        filtered_included_count=filter_stats["included_count"],
    )
