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


def _build_environment_note(config: AppConfig) -> str:
    """Render the environment profile the LLM uses to judge relevance.

    ``environment_stack`` may be a flat list of assets or a mapping of category
    (e.g. "Internal Systems") to a list of assets.
    """
    lines = ["OUR ENVIRONMENT:"]
    if config.environment_description:
        lines.append(config.environment_description)

    stack = config.environment_stack
    if isinstance(stack, dict):
        for category, assets in stack.items():
            lines.append(f"{category}:")
            lines.extend(f"  - {tech}" for tech in assets)
    elif stack:
        lines.append("Stack / assets we run:")
        lines.extend(f"  - {tech}" for tech in stack)

    if config.environment_interests:
        lines.append("")
        lines.append("WATCH TOPICS (judged separately from the stack — see INTERESTS rules):")
        for interest in config.environment_interests:
            lines.append(f"- {interest['topic']}")
            if interest.get("include"):
                lines.append(f"    INCLUDE: {interest['include']}")
            if interest.get("exclude"):
                lines.append(f"    EXCLUDE: {interest['exclude']}")

    return "\n".join(lines)


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

    kept_items, filter_stats = apply_filters(sorted_items, config)

    limited = kept_items[: config.max_items_to_llm]

    log.info(
        f"Pre-LLM: {len(items)} total → {len(filtered)} in lookback → "
        f"{len(deduped)} after dedup → ignored {filter_stats['ignored_count']} → "
        f"{len(kept_items)} after ignore backstop → {len(limited)} for LLM relevance pass"
    )

    text_block = "\n\n".join(
        f"{item.source} | {item.title} | {item.url}\n{item.summary}"
        for item in limited
    )

    environment_note = _build_environment_note(config)

    interests_rules = ""
    if config.environment_interests:
        interests_rules = """
INTERESTS RULES (a SEPARATE axis from the stack — "worth knowing", not "affects us"):
- Also surface an item if it is a genuinely notable development matching a WATCH
  TOPIC's INCLUDE and not its EXCLUDE — even if it touches nothing in our stack.
- Apply a HIGH bar. Surface at most 1-2 interest items total per briefing, unless
  one is truly critical. These are nuggets, not a firehose — err toward dropping.
- An interest item must clear the same EXCLUDE hype filters; ignore product
  launches, funding, benchmarks, and generic commentary.
- Prefix the title of an interest-only item with "[Watch] " so it is clearly a
  heads-up rather than something affecting our systems, and never let interest
  items crowd out stack-relevant ones.
"""

    prompt = f"""You are a cybersecurity analyst preparing a daily standup briefing.

You review a raw feed of security news and surface ONLY what is relevant to our
environment. Below are {len(limited)} headlines from the last {config.lookback_hours} hours.

{environment_note}

RELEVANCE RULES:
- Include an item only if it could plausibly affect the systems, software, or
  supply chain listed in OUR ENVIRONMENT above.
- Drop news about products, vendors, or platforms we do not run, even if it is
  high severity — it is not our concern today.
- When in doubt about whether something touches our stack, lean toward dropping
  it; false positives about systems we do not run are the main problem to avoid.
- Judge by meaning, not keywords: a Linux kernel, glibc, sudo, or OpenSSL issue
  is relevant to our Linux hosts even if it never says "Linux"; a story that
  merely name-drops "Google" in an unrelated context is not relevant.
- Let core_situation and extra_attention reflect only the relevant items too.
  If nothing in the feed is relevant, return empty key_items and say so in
  core_situation.
{interests_rules}
<HEADLINES>
{text_block}
</HEADLINES>

Return ONLY valid JSON matching this exact schema:
{{
  "core_situation": ["3-5 short bullet strings summarising the overall threat picture"],
  "key_items": [
    {{
      "severity": "critical|high|medium|threat",
      "title": "Short descriptive title",
      "affects": "Which of our assets/systems this touches, e.g. 'WordPress' (comma-separated if several; for a [Watch] item, the watch topic)",
      "why_relevant": "One sentence on WHY it matters. Do NOT restate our stack here (no 'We run WordPress; ...') — the affected asset already goes in affects.",
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
            affects=item_data.get("affects"),
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
        filtered_included_count=len(key_items),
    )
