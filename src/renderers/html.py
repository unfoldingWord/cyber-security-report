from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from src.models import IntelReport, AppConfig


TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def render_html(report: IntelReport, config: AppConfig) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
    )
    template = env.get_template("report.html.j2")
    return template.render(report=report, config=config, now=report.generated_at)
