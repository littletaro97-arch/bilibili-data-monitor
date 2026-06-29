from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import socket
import threading
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from plotly.offline import get_plotlyjs

from app.config import load_settings, settings
from app.config_writer import save_lan_settings
from app.logger import clear_log_file
from app.models import AppError
from app.security import session_token, verify_password
from app.services.analysis_service import build_chart_blocks, build_summary
from app.ui.dashboard import templates


router = APIRouter()


def _flash_redirect(url: str, message: str, level: str = "info") -> RedirectResponse:
    return RedirectResponse(f"{url}?message={message}&level={level}", status_code=303)


def _log_payload(rows) -> list[dict[str, str | None]]:
    return [
        {
            "created_at": row["created_at"],
            "level": row["level"],
            "bvid": row["bvid"],
            "message": row["message"],
            "detail": row["detail"],
        }
        for row in rows
    ]


def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "无法检测"


def _request_shutdown() -> None:
    def stop_process() -> None:
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=stop_process, daemon=True).start()


def _datetime_local_to_iso(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.isoformat()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, message: str | None = None, level: str = "info"):
    repo = request.app.state.repository
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "tasks": repo.list_tasks(),
            "logs": repo.list_logs(limit=20),
            "message": message,
            "level": level,
            "default_interval": settings.crawl.default_interval,
            "min_interval": settings.crawl.min_interval,
        },
    )


@router.get("/api/logs")
async def api_logs(request: Request, bvid: str | None = None, limit: int = 30):
    limit = max(1, min(limit, 100))
    rows = request.app.state.repository.list_logs(bvid=bvid, limit=limit)
    return {"logs": _log_payload(rows)}


@router.get("/assets/plotly.min.js")
async def plotly_asset():
    return Response(get_plotlyjs(), media_type="application/javascript")


@router.get("/lan/login", response_class=HTMLResponse)
async def lan_login_page(request: Request, message: str | None = None, level: str = "info"):
    return templates.TemplateResponse(
        request,
        "lan_login.html",
        {"message": message, "level": level},
    )


@router.post("/lan/login")
async def lan_login(password: str = Form(...)):
    if not settings.lan.enabled:
        return _flash_redirect("/", "局域网访问未启用")
    if verify_password(password, settings.lan.password_hash):
        response = _flash_redirect("/", "登录成功")
        response.set_cookie(
            settings.lan.session_cookie,
            session_token(settings.lan.password_hash),
            httponly=True,
            samesite="lax",
        )
        return response
    return _flash_redirect("/lan/login", "访问密码错误", "error")


@router.post("/tasks")
async def add_task(
    request: Request,
    video_input: str = Form(...),
    interval_seconds: int = Form(settings.crawl.default_interval),
):
    try:
        bvid = await request.app.state.video_service.add_video_task(video_input, interval_seconds)
        return _flash_redirect("/", f"视频任务已添加：{bvid}")
    except AppError as exc:
        return _flash_redirect("/", str(exc), "error")
    except Exception as exc:
        request.app.state.repository.add_log("ERROR", "添加任务失败", detail=str(exc))
        return _flash_redirect("/", "添加任务失败，请查看日志", "error")


@router.post("/tasks/{task_id}/pause")
async def pause_task(request: Request, task_id: int):
    request.app.state.video_service.pause_task(task_id)
    return _flash_redirect("/", "任务已暂停")


@router.post("/tasks/{task_id}/resume")
async def resume_task(request: Request, task_id: int):
    try:
        request.app.state.video_service.resume_task(task_id)
        return _flash_redirect("/", "任务已恢复")
    except AppError as exc:
        return _flash_redirect("/", str(exc), "error")


@router.post("/tasks/{task_id}/stop")
async def stop_task(request: Request, task_id: int):
    request.app.state.video_service.stop_task(task_id)
    return _flash_redirect("/", "任务已删除，历史数据保留")


@router.post("/tasks/{task_id}/collect")
async def collect_now(request: Request, task_id: int):
    task = request.app.state.repository.get_task(task_id)
    if not task:
        return _flash_redirect("/", "任务不存在", "error")
    try:
        await request.app.state.crawl_service.collect_once(task["bvid"])
        return _flash_redirect("/", "立即采集完成")
    except AppError as exc:
        return _flash_redirect("/", str(exc), "error")


@router.get("/videos/{bvid}", response_class=HTMLResponse)
async def video_detail(request: Request, bvid: str, message: str | None = None, level: str = "info"):
    repo = request.app.state.repository
    video = repo.get_video(bvid)
    task = repo.get_task_by_bvid(bvid)
    snapshots = repo.list_snapshots(bvid)
    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "video": video,
            "task": task,
            "snapshots": snapshots,
            "latest": snapshots[-1] if snapshots else None,
            "charts": build_chart_blocks(snapshots, include_plotlyjs=False),
            "summary": build_summary(snapshots),
            "logs": repo.list_logs(bvid=bvid, limit=30),
            "comments": repo.list_comments(bvid, limit=30),
            "danmaku": repo.list_danmaku(bvid, limit=50),
            "message": message,
            "level": level,
            "needs_plotly": True,
        },
    )


@router.post("/videos/{bvid}/comments/collect")
async def collect_comments(request: Request, bvid: str):
    try:
        count = await request.app.state.phase2_service.collect_comments_once(bvid)
        return _flash_redirect(f"/videos/{bvid}", f"评论采集完成：{count} 条")
    except AppError as exc:
        request.app.state.repository.add_log("WARNING", "评论采集未完成", bvid=bvid, detail=str(exc))
        return _flash_redirect(f"/videos/{bvid}", str(exc), "error")


@router.post("/videos/{bvid}/danmaku/collect")
async def collect_danmaku(request: Request, bvid: str):
    try:
        count = await request.app.state.phase2_service.collect_danmaku_once(bvid)
        return _flash_redirect(f"/videos/{bvid}", f"弹幕采集完成：{count} 条")
    except AppError as exc:
        request.app.state.repository.add_log("WARNING", "弹幕采集未完成", bvid=bvid, detail=str(exc))
        return _flash_redirect(f"/videos/{bvid}", str(exc), "error")


@router.post("/videos/{bvid}/logs/clear")
async def clear_video_logs(request: Request, bvid: str):
    count = request.app.state.repository.clear_logs(bvid=bvid)
    return _flash_redirect(f"/videos/{bvid}", f"已清理该视频日志：{count} 条")


@router.post("/videos/{bvid}/snapshots/delete-before")
async def delete_snapshots_before(
    request: Request,
    bvid: str,
    before_time: str = Form(...),
):
    if not before_time.strip():
        return _flash_redirect(f"/videos/{bvid}", "必须填写删除截止时间", "error")
    try:
        cutoff = _datetime_local_to_iso(before_time.strip())
    except ValueError:
        return _flash_redirect(f"/videos/{bvid}", "删除截止时间格式不正确", "error")
    count = request.app.state.repository.delete_snapshots_before(bvid, cutoff)
    request.app.state.repository.add_log("WARNING", f"删除历史快照：{count} 条，早于 {cutoff}", bvid=bvid)
    return _flash_redirect(f"/videos/{bvid}", f"已删除早于 {cutoff} 的图表数据：{count} 条")


@router.post("/videos/{bvid}/report")
async def generate_report(request: Request, bvid: str):
    try:
        path = request.app.state.report_service.generate(bvid)
        return _flash_redirect(f"/videos/{bvid}", f"报告已生成：{path.name}")
    except Exception as exc:
        request.app.state.repository.add_log("ERROR", "报告生成失败", bvid=bvid, detail=str(exc))
        return _flash_redirect(f"/videos/{bvid}", "报告生成失败，请查看日志", "error")


@router.get("/reports/{filename}")
async def download_report(filename: str):
    path = settings.report_output_dir / Path(filename).name
    if not path.exists():
        return RedirectResponse("/", status_code=303)
    return FileResponse(path)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, message: str | None = None, level: str = "info"):
    current_settings = load_settings()
    local_ip = _local_ip()
    lan_active = current_settings.lan.enabled and current_settings.lan.password_hash == settings.lan.password_hash
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "settings": current_settings,
            "message": message,
            "level": level,
            "runtime_lan_enabled": settings.lan.enabled,
            "lan_active": lan_active,
            "local_ip": local_ip,
            "local_url": f"http://127.0.0.1:{current_settings.app.port}",
            "lan_url": f"http://{local_ip}:{current_settings.app.port}",
            "lan_password_set": bool(current_settings.lan.password_hash),
            "restart_required": current_settings.lan.enabled != settings.lan.enabled
            or current_settings.lan.password_hash != settings.lan.password_hash,
        },
    )


@router.post("/settings/lan")
async def update_lan_settings(
    enabled: str | None = Form(None),
    password: str = Form(""),
):
    try:
        save_lan_settings(enabled=enabled == "on", password=password.strip() or None)
        return _flash_redirect("/settings", "局域网访问设置已保存，重启程序后生效")
    except ValueError as exc:
        return _flash_redirect("/settings", str(exc), "error")


@router.post("/maintenance/clear-raw-json")
async def clear_raw_json(request: Request):
    count = request.app.state.repository.clear_raw_json()
    return _flash_redirect("/settings", f"已清理 raw_json 字段：{count} 处")


@router.post("/maintenance/clear-logs")
async def clear_logs(request: Request):
    count = request.app.state.repository.clear_logs()
    file_ok = clear_log_file()
    suffix = "，日志文件已清空" if file_ok else "，日志文件可能被占用"
    return _flash_redirect("/settings", f"已清理页面日志：{count} 条{suffix}")


@router.post("/shutdown")
async def shutdown_app(request: Request):
    _request_shutdown()
    return templates.TemplateResponse(
        request,
        "shutdown.html",
        {"message": "程序正在退出，可以关闭这个浏览器页面。"},
    )
