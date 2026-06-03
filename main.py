import anyio
import logging

from src.config import load_config
from src.fetchers.rss import fetch_all_feeds
from src.intelligence.analyst import analyze, AnalystError
from src.renderers.html import render_html
from src.renderers.markdown import render_markdown
from src.outputs.file import write_report
from src.outputs.zulip import post_to_zulip


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


async def main():
    log.info("Starting cybersec standup pipeline")

    try:
        config = load_config()
    except Exception as e:
        log.error(f"Failed to load config: {e}")
        raise

    try:
        items = await fetch_all_feeds(config)
        log.info(f"Fetched {len(items)} items from {len(config.feeds)} feeds")
    except Exception as e:
        log.error(f"Feed fetch failed: {e}")
        raise

    try:
        report = await analyze(items, config)
        log.info(f"Analysis complete. Items sent to LLM: {report.items_analyzed}")
    except AnalystError as e:
        log.error(f"Analysis failed: {e}")
        raise
    except Exception as e:
        log.error(f"Unexpected error during analysis: {e}")
        raise

    try:
        if config.output_format in ("html", "both"):
            html_content = render_html(report, config)
            if config.file_enabled:
                path = write_report(html_content, config.file_html_path)
                log.info(f"HTML report written to {path}")

        if config.output_format in ("markdown", "both"):
            md_content = render_markdown(report, config)
            if config.file_enabled:
                path = write_report(md_content, config.file_markdown_path)
                log.info(f"Markdown report written to {path}")
            if config.zulip_enabled:
                await post_to_zulip(md_content, config)
                log.info("Posted to Zulip")

    except Exception as e:
        log.error(f"Output phase failed: {e}")
        raise

    log.info("Pipeline complete")


if __name__ == "__main__":
    anyio.run(main)
