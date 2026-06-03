from pathlib import Path
from datetime import datetime


def write_report(content: str, path_template: str) -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = Path(path_template.replace("{date}", date_str))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
