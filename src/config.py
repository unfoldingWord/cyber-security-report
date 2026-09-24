import os
import re
from datetime import datetime
from pathlib import Path
import yaml
from dotenv import load_dotenv
from src.models import AppConfig


def load_config() -> AppConfig:
    load_dotenv()

    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        config_data = yaml.safe_load(f)

    feeds = config_data["feeds"]["news"]
    report = config_data["report"]
    output = config_data["output"]
    output_file = output["file"]
    output_zulip = output["zulip"]

    output_format = output["format"]
    valid_formats = ("markdown", "html", "both")
    if output_format not in valid_formats:
        raise ValueError(
            f"output.format must be one of {valid_formats}, got {output_format!r}"
        )

    file_enabled = output_file["enabled"]
    file_html_path = output_file.get("html_path")
    file_markdown_path = output_file.get("markdown_path")

    # A path is only required when file output is on AND the format that writes
    # it is selected. This lets html_path stay unset in markdown mode.
    if file_enabled:
        if output_format in ("html", "both") and not file_html_path:
            raise ValueError(
                f"output.format is {output_format!r} but output.file.html_path is not set"
            )
        if output_format in ("markdown", "both") and not file_markdown_path:
            raise ValueError(
                f"output.format is {output_format!r} but output.file.markdown_path is not set"
            )

    zulip_enabled = output_zulip["enabled"]
    if zulip_enabled:
        missing_vars = []
        if not os.getenv("ZULIP_SERVER_URL"):
            missing_vars.append("ZULIP_SERVER_URL")
        if not os.getenv("ZULIP_EMAIL"):
            missing_vars.append("ZULIP_EMAIL")
        if not os.getenv("ZULIP_API_KEY"):
            missing_vars.append("ZULIP_API_KEY")
        if missing_vars:
            raise ValueError(f"Zulip enabled but missing env vars: {', '.join(missing_vars)}")

    filters = config_data.get("filters", {})

    def _compile_patterns(raw: list, label: str) -> list[re.Pattern]:
        compiled = []
        for s in raw:
            try:
                compiled.append(re.compile(s.strip(), re.IGNORECASE))
            except re.error as e:
                raise ValueError(f"Invalid regex in filters.{label}: {s.strip()!r} — {e}") from e
        return compiled

    filters_ignore = _compile_patterns(filters.get("ignore", []), "ignore")

    environment = config_data.get("environment", {}) or {}
    environment_description = environment.get("description")
    if environment_description:
        environment_description = environment_description.strip()
    environment_stack = environment.get("stack", []) or []

    environment_interests = []
    for entry in environment.get("interests", []) or []:
        environment_interests.append(
            {
                "topic": (entry.get("topic") or "").strip(),
                "include": " ".join((entry.get("include") or "").split()),
                "exclude": " ".join((entry.get("exclude") or "").split()),
            }
        )

    return AppConfig(
        feeds=feeds,
        report_title=report["title"],
        lookback_hours=report["lookback_hours"],
        max_items_to_llm=report["max_items_to_llm"],
        output_format=output_format,
        file_enabled=file_enabled,
        file_html_path=file_html_path,
        file_markdown_path=file_markdown_path,
        zulip_enabled=zulip_enabled,
        zulip_stream=output_zulip["stream"],
        zulip_topic=output_zulip["topic"],
        zulip_server_url=os.getenv("ZULIP_SERVER_URL"),
        zulip_email=os.getenv("ZULIP_EMAIL"),
        zulip_api_key=os.getenv("ZULIP_API_KEY"),
        filters_ignore=filters_ignore,
        environment_description=environment_description,
        environment_stack=environment_stack,
        environment_interests=environment_interests,
    )
