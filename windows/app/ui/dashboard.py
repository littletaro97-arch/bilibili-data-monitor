from pathlib import Path
from plotly import __version__ as PLOTLY_VERSION
from datetime import datetime
from app.services.analysis_service import METRICS

from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR


templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "reports" / "templates"))


def task_label(status):
    return {"running": "正常", "paused": "中断", "error": "异常", "stopped": "停止"}.get(status, "中断")


def task_style(task):
    status = task["status"]
    if status != "running":
        return status if status in {"paused", "error", "stopped"} else "interrupted"
    try:
        cooldown = task["cooldown_until"]
        if cooldown and datetime.fromisoformat(cooldown).astimezone() > datetime.now().astimezone():
            return "interrupted"
    except (KeyError, ValueError, IndexError, TypeError):
        pass
    return "running"


def local_time(value):
    if not value:
        return "暂无"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value)


templates.env.filters.update(task_label=task_label, task_style=task_style,
    task_display=lambda task: "中断" if task_style(task) == "interrupted" else task_label(task["status"]),
    count_display=lambda value: "暂无" if value is None else format(value, ","), local_time=local_time)

templates.env.globals["chart_metric_names"] = [field for field, _ in METRICS]
templates.env.globals["plotly_version"] = PLOTLY_VERSION
