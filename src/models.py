from datetime import datetime
from pydantic import BaseModel, HttpUrl


class FeedItem(BaseModel):
    title: str
    url: str
    summary: str
    source: str
    published: datetime | None = None


class BriefingItem(BaseModel):
    severity: str
    title: str
    why_relevant: str
    action: str
    links: list[str] = []
    cve: str | None = None


class IntelReport(BaseModel):
    generated_at: datetime
    core_situation: list[str]
    key_items: list[BriefingItem]
    extra_attention: list[str]
    items_analyzed: int
    sources: list[str]
    filtered_ignored_count: int = 0
    filtered_included_count: int = 0


class AppConfig(BaseModel):
    feeds: list[dict]
    report_title: str
    lookback_hours: int
    max_items_to_llm: int
    output_format: str
    file_enabled: bool
    file_html_path: str
    file_markdown_path: str
    zulip_enabled: bool
    zulip_stream: str
    zulip_topic: str
    zulip_server_url: str | None = None
    zulip_email: str | None = None
    zulip_api_key: str | None = None
    filters_ignore: list[str] = []
    filters_include: list[str] = []
