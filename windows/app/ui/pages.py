from __future__ import annotations

import os
import asyncio
from datetime import datetime
from pathlib import Path
import socket
import threading
import time

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
import plotly
import httpx
from PIL import UnidentifiedImageError, Image

from app.config import load_settings, settings
from app.config_writer import save_lan_settings, save_launcher_settings
from app.cover import safe_cover_url, local_cover_url, cover_key
from app.version import APP_VERSION, INSTALLER_REVISION
from app.services.update_service import RELEASES_URL, UpdateError
from app.logger import clear_log_file
from app.models import AppError
from app.security import session_token, verify_password
from app.services.analysis_service import (
    METRICS,
    build_chart_blocks,
    build_dual_axis_chart,
    build_ratio_chart,
    build_summary,
    count_imported_snapshots,
)
from app.services.history_import_service import parse_history_csv
from app.services.history_exchange_service import MAX_ZIP_BYTES
from app.ui.dashboard import templates
from app.services.text_inspection import build_text_panel


router = APIRouter()


def _flash_redirect(url: str, message: str, level: str = "info") -> RedirectResponse:
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    parts=urlsplit(url);query=dict(parse_qsl(parts.query));query.update(message=message,level=level)
    return RedirectResponse(urlunsplit((parts.scheme,parts.netloc,parts.path,urlencode(query),parts.fragment)),status_code=303)


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


def _latest_payload(row, task) -> dict[str, object | None]:
    fields = [
        "view_count",
        "like_count",
        "coin_count",
        "favorite_count",
        "reply_count",
        "danmaku_count",
        "share_count",
        "online_count",
        "online_text",
        "captured_at",
        "source_type",
    ]
    latest = {field: row[field] if row and field in row.keys() else None for field in fields}
    return {
        "latest": latest,
        "task": {"status": task["status"] if task else None},
    }


def _recent_reports(bvid: str, limit: int = 5) -> list[dict[str, str]]:
    if not settings.report_output_dir.exists():
        return []
    files = sorted(settings.report_output_dir.glob(f"{bvid}_*.html"), key=lambda path: path.stat().st_mtime, reverse=True)
    return [
        {
            "name": path.name,
            "url": f"/reports/{path.name}",
            "folder": settings.report_output_dir.as_posix(),
        }
        for path in files[:limit]
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


def _request_shutdown(app) -> None:
    callback = getattr(app.state, "shutdown_callback", None)
    if callback:
        callback()
        return

    def stop_process() -> None:
        time.sleep(1)
        tray = getattr(app.state, "desktop_tray", None)
        if tray:
            tray.stop()
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
    current_settings = load_settings()
    local_ip = _local_ip()
    tasks, up_groups = request.app.state.up_monitor.layout(repo.list_tasks())
    up_detect_interval, up_video_interval = request.app.state.up_monitor.store.defaults(settings.crawl.default_interval)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "tasks": tasks,
            "up_groups": up_groups, "up_detect_interval": up_detect_interval, "up_video_interval": up_video_interval,
            "up_revision": request.app.state.up_monitor.state_snapshot()["revision"],
            "message": message,
            "level": level,
            "default_interval": settings.crawl.default_interval,
            "min_interval": settings.crawl.min_interval,
            "runtime_lan_enabled": settings.lan.enabled,
            "lan_config_enabled": current_settings.lan.enabled,
            "lan_password_set": bool(current_settings.lan.password_hash),
            "local_url": f"http://127.0.0.1:{current_settings.app.port}",
            "lan_url": f"http://{local_ip}:{current_settings.app.port}",
        },
    )


@router.get("/api/logs")
async def api_logs(request: Request, bvid: str | None = None, limit: int = 30):
    limit = max(1, min(limit, 100))
    rows = request.app.state.repository.list_logs(bvid=bvid, limit=limit)
    return {"logs": _log_payload(rows)}


@router.get("/api/videos/{bvid}/latest")
async def api_video_latest(request: Request, bvid: str):
    repo = request.app.state.repository
    payload = _latest_payload(repo.latest_snapshot(bvid), repo.get_task_by_bvid(bvid))
    video = repo.get_video(bvid)
    payload["cover_url"] = local_cover_url(bvid, video["cover_url"]) if video else None
    return payload


@router.get("/assets/{name}")
async def branding_asset(name: str):
    allowed = {"app-icon.png", "app-icon.ico", "appearance.js", "appearance.css", "charts.js", "settings.js"}
    if name == "plotly.min.js":
        # Stream the installed asset instead of materializing several MB per request.
        return FileResponse(Path(plotly.__file__).parent / "package_data" / "plotly.min.js",
                            media_type="application/javascript", headers={"Cache-Control": "public, max-age=86400"})
    if name not in allowed:
        return Response(status_code=404)
    from app.config import BASE_DIR
    return FileResponse(BASE_DIR / "app" / "assets" / name)


@router.get("/covers/{bvid}/{key}.webp")
async def cached_cover(request: Request, bvid: str, key: str):
    video = request.app.state.repository.get_video(bvid)
    url = safe_cover_url(video["cover_url"]) if video else None
    if not url or key != cover_key(url):
        return Response(status_code=404)
    headers = {"Cache-Control": "private, max-age=31536000, immutable", "ETag": f'"{key}"'}
    if request.headers.get("if-none-match") == headers["ETag"]:
        return Response(status_code=304, headers=headers)
    try:
        path = await request.app.state.cover_cache.get(url)
        return FileResponse(path, media_type="image/webp", headers=headers)
    except (httpx.HTTPError, ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return Response(status_code=502, headers={"Cache-Control": "no-store"})


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


@router.post("/tasks/{task_id}/interval")
async def change_task_interval(request: Request, task_id: int, interval_seconds: int = Form(...)):
    try:
        request.app.state.repository.set_task_interval(task_id, interval_seconds, settings.crawl.min_interval)
        return _flash_redirect('/', f'采集间隔已改为 {interval_seconds} 秒')
    except AppError as exc:
        return _flash_redirect('/', str(exc), 'error')


@router.post("/tasks/{task_id}/resume")
async def resume_task(request: Request, task_id: int):
    try:
        request.app.state.video_service.resume_task(task_id)
        return _flash_redirect("/", "任务已恢复")
    except AppError as exc:
        return _flash_redirect("/", str(exc), "error")


@router.post("/tasks/{task_id}/stop")
async def stop_task(request: Request, task_id: int):
    task = request.app.state.repository.get_task(task_id)
    request.app.state.video_service.stop_task(task_id)
    if task:
        await request.app.state.full_text.cancel_video(task['bvid'])
    return _flash_redirect("/", "已放入回收站，停止检测，历史数据保留")


@router.get("/recycle-bin", response_class=HTMLResponse)
async def recycle_bin(request: Request, message: str | None = None, level: str = "info"):
    tasks = [task for task in request.app.state.repository.list_tasks(include_stopped=True) if task["status"] == "stopped"]
    return templates.TemplateResponse(request, "recycle_bin.html", {"tasks": tasks, "message": message, "level": level})


@router.post("/recycle-bin/{task_id}/restore")
async def restore_recycled_task(request: Request, task_id: int):
    try:
        request.app.state.video_service.restore_task(task_id)
        return _flash_redirect("/recycle-bin", "已取回链接，恢复正常检测")
    except AppError as exc:
        return _flash_redirect("/recycle-bin", str(exc), "error")


@router.get("/api/desktop/visibility")
async def desktop_visibility(request: Request):
    panel = getattr(request.app.state, "desktop_panel", None)
    native = "BilibiliMonitorDesktopPanel" in request.headers.get("user-agent", "")
    return {"hidden": bool(native and panel and panel.hidden)}


@router.post("/desktop/activate")
async def activate_desktop(request: Request):
    from urllib.parse import urlsplit
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        return Response(status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        return Response(status_code=403)
    if urlsplit(str(request.url)).hostname not in {"127.0.0.1", "::1"}:
        return Response(status_code=403)
    panel = getattr(request.app.state, "desktop_panel", None)
    if panel:
        await asyncio.to_thread(panel.open, "/")
        return {"activated": True}
    return {"activated": False}


@router.post("/desktop/theme")
async def desktop_theme(request: Request):
    from urllib.parse import urlsplit
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        return Response(status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        return Response(status_code=403)
    if urlsplit(str(request.url)).hostname not in {"127.0.0.1", "::1"}:
        return Response(status_code=403)
    try:
        data = await request.json()
    except ValueError:
        return Response(status_code=400)
    if not isinstance(data, dict) or not isinstance(data.get("dark"), bool):
        return Response(status_code=400)
    panel = getattr(request.app.state, "desktop_panel", None)
    if panel:
        await asyncio.to_thread(panel.set_theme, data["dark"])
    return {"applied": bool(panel)}


@router.post("/tasks/{task_id}/collect")
async def collect_now(request: Request, task_id: int):
    task = request.app.state.repository.get_task(task_id)
    if not task:
        return _flash_redirect("/", "任务不存在", "error")
    try:
        collected = await request.app.state.crawl_service.collect_once(task["bvid"])
        if not collected:
            return _flash_redirect("/", "本次未采集：任务已停止或正在检测")
        return _flash_redirect("/", "立即采集完成")
    except AppError as exc:
        return _flash_redirect("/", str(exc), "error")


@router.get("/videos/{bvid}", response_class=HTMLResponse)
async def video_detail(
    request: Request,
    bvid: str,
    message: str | None = None,
    level: str = "info",
    left_metric: str = "view_count",
    right_metric: str = "like_count",
    ratio_numerator: str = "like_count",
    ratio_denominator: str = "view_count",
):
    repo = request.app.state.repository
    video = repo.get_video(bvid)
    task = repo.get_task_by_bvid(bvid)
    snapshots = repo.list_snapshots(bvid)
    text_panel = build_text_panel(repo.text_dashboard_data(bvid), video, snapshots[-1] if snapshots else None)
    metric_fields = {field for field, _title in METRICS}
    if left_metric not in metric_fields:
        left_metric = "view_count"
    if right_metric not in metric_fields:
        right_metric = "like_count"
    if ratio_numerator not in metric_fields:
        ratio_numerator = "like_count"
    if ratio_denominator not in metric_fields:
        ratio_denominator = "view_count"
    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "video": video,
            "cover_url": local_cover_url(bvid, video["cover_url"]) if video else None,
            "task": task,
            "snapshots": snapshots,
            "latest": snapshots[-1] if snapshots else None,
            "charts": build_chart_blocks(snapshots, include_plotlyjs=False, lazy=True),
            "dual_axis_chart": build_dual_axis_chart(snapshots, left_metric, right_metric, lazy=True),
            "ratio_chart": build_ratio_chart(snapshots, ratio_numerator, ratio_denominator, lazy=True),
            "metric_options": METRICS,
            "left_metric": left_metric,
            "right_metric": right_metric,
            "ratio_numerator": ratio_numerator,
            "ratio_denominator": ratio_denominator,
            "imported_snapshot_count": count_imported_snapshots(snapshots),
            "summary": build_summary(snapshots),
            "latest_refresh_seconds": settings.crawl.min_interval,
            "report_output_dir": settings.report_output_dir,
            "reports": request.app.state.report_service.recent(bvid),
            "text_panel": text_panel,
            "message": message,
            "level": level,
            "needs_plotly": True,
        },
    )


@router.post("/videos/{bvid}/comments/collect")
async def collect_comments(request: Request, bvid: str):
    try:
        count = await request.app.state.phase2_service.collect_comments_once(bvid)
        return _flash_redirect(f"/videos/{bvid}", f"评论单页采样完成：本次保存或更新 {count} 条，并非全量。更多评论请展开“登录后遍历评论与分段弹幕”，选择“评论及楼中楼”。")
    except AppError as exc:
        request.app.state.repository.add_log("WARNING", "评论采集未完成", bvid=bvid, detail=str(exc))
        return _flash_redirect(f"/videos/{bvid}", str(exc), "error")


@router.post("/videos/{bvid}/danmaku/collect")
async def collect_danmaku(request: Request, bvid: str, cid: int | None = Form(None), scope: str = Form("selected")):
    try:
        if scope not in {"selected", "all"}:
            raise AppError("无效的采样范围")
        count = await request.app.state.phase2_service.collect_danmaku_once(bvid, cid, all_parts=scope == "all")
        return _flash_redirect(f"/videos/{bvid}", f"弹幕采样完成：{count} 条（{'全部分 P' if scope == 'all' else '仅所选分 P'}），非完整历史")
    except AppError as exc:
        request.app.state.repository.add_log("WARNING", "弹幕采集未完成", bvid=bvid, detail=str(exc))
        return _flash_redirect(f"/videos/{bvid}", str(exc), "error")


@router.post("/videos/{bvid}/danmaku/parts")
async def discover_danmaku_parts(request: Request, bvid: str):
    try:
        parts = await request.app.state.phase2_service.discover_danmaku_parts(bvid)
        return _flash_redirect(f"/videos/{bvid}", f"已读取 {len(parts)} 个分 P，未采样弹幕")
    except AppError as exc:
        return _flash_redirect(f"/videos/{bvid}", str(exc), "error")


@router.post("/videos/{bvid}/phase2/demo")
async def seed_phase2_demo_data(request: Request, bvid: str):
    comment_count, danmaku_count = request.app.state.phase2_service.seed_demo_data(bvid)
    return _flash_redirect(f"/videos/{bvid}", f"已生成演示数据：评论 {comment_count} 条，弹幕 {danmaku_count} 条")


@router.post("/videos/{bvid}/comments/import")
async def import_comments(request: Request, bvid: str, comments_text: str = Form(...)):
    count = request.app.state.phase2_service.import_comments_text(bvid, comments_text)
    return _flash_redirect(f"/videos/{bvid}", f"已导入评论：{count} 条")


@router.post("/videos/{bvid}/danmaku/import")
async def import_danmaku(request: Request, bvid: str, danmaku_text: str = Form(...)):
    count = request.app.state.phase2_service.import_danmaku_text(bvid, danmaku_text)
    return _flash_redirect(f"/videos/{bvid}", f"已导入弹幕：{count} 条")


@router.post("/videos/{bvid}/history/import")
async def import_history(
    request: Request,
    bvid: str,
    history_csv: str = Form(...),
    source_note: str = Form(""),
):
    try:
        rows = parse_history_csv(history_csv)
        count = request.app.state.repository.insert_history_snapshots(
            bvid,
            rows,
            source_note=source_note.strip() or "手动导入历史记录",
        )
        request.app.state.repository.add_log("INFO", f"导入历史快照：{count} 条", bvid=bvid)
        return _flash_redirect(f"/videos/{bvid}", f"已导入历史记录：{count} 条")
    except AppError as exc:
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
async def generate_report(request: Request, bvid: str, open_report: bool = Form(False)):
    if open_report:
        from app.ui.full_text_api import local
        local(request)
    try:
        path = request.app.state.report_service.generate(bvid)
        if open_report:
            request.app.state.report_service.open(path.name)
            return _flash_redirect(f"/videos/{bvid}", "报告已在系统浏览器打开")
        return _flash_redirect(f"/videos/{bvid}", f"报告已生成：{path.name}；保存位置：{path.parent}")
    except Exception as exc:
        request.app.state.repository.add_log("ERROR", "报告生成失败", bvid=bvid, detail=str(exc))
        return _flash_redirect(f"/videos/{bvid}", "报告生成失败，请查看日志", "error")


@router.get("/reports/{filename}")
async def download_report(request: Request, filename: str):
    try:
        record=request.app.state.report_service.known(filename)
        path=Path(record["path"])
        if not path.is_file():raise AppError("报告路径已改变或文件已不存在")
        return FileResponse(path)
    except AppError:
        return HTMLResponse("报告路径已改变或文件已删除。请返回应用重新生成报告。",status_code=404)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, message: str | None = None, level: str = "info"):
    repo = request.app.state.repository
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
            "update_service": request.app.state.update_service,
            "app_version": APP_VERSION,
            "installer_revision": INSTALLER_REVISION,
            "releases_url": RELEASES_URL,
            "lan_active": lan_active,
            "local_ip": local_ip,
            "local_url": f"http://127.0.0.1:{current_settings.app.port}",
            "lan_url": f"http://{local_ip}:{current_settings.app.port}",
            "lan_password_set": bool(current_settings.lan.password_hash),
            "launcher_show_console": current_settings.launcher.show_console,
            "logs": repo.list_logs(limit=100),
            "export_output_dir": settings.database_path.parent / "exports",
            "restart_required": current_settings.lan.enabled != settings.lan.enabled
            or current_settings.lan.password_hash != settings.lan.password_hash,
        },
    )


@router.post("/settings/updates/check")
async def check_desktop_updates(request: Request):
    await request.app.state.update_service.check()
    return RedirectResponse("/settings#version-updates", status_code=303)


@router.get("/settings/updates/download")
async def download_desktop_update(request: Request):
    try:
        path, name = await request.app.state.update_service.download()
        return FileResponse(path, filename=name, media_type="application/octet-stream")
    except UpdateError as exc:
        return _flash_redirect("/settings", str(exc), "error")


@router.post("/settings/lan")
async def update_lan_settings(
    request: Request,
    enabled: str | None = Form(None),
    password: str = Form(""),
):
    try:
        save_lan_settings(enabled=enabled == "on", password=password.strip() or None)
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"message": "已自动保存，重启程序后生效"})
        return _flash_redirect("/settings", "局域网访问设置已保存，重启程序后生效")
    except ValueError as exc:
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"error": str(exc)}, status_code=400)
        return _flash_redirect("/settings", str(exc), "error")


@router.post("/settings/launcher")
async def update_launcher_settings(request: Request, show_console: str | None = Form(None)):
    save_launcher_settings(show_console=show_console == "on")
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"message": "已自动保存，下次启动生效"})
    return _flash_redirect("/settings", "启动设置已保存，下次启动程序时生效")


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


@router.post("/maintenance/export-data")
async def export_data(request: Request):
    path = request.app.state.export_service.export_all()
    return _flash_redirect("/settings", f"全部数据已导出：{path}")


@router.get("/history-exchange/export")
async def export_history_exchange(request: Request):
    payload = request.app.state.history_exchange_service.export_zip()
    filename = datetime.now().astimezone().strftime("bilibili-history-v1-%Y%m%d_%H%M%S.zip")
    return Response(
        payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/history-exchange/preview", response_class=HTMLResponse)
async def preview_history_exchange(request: Request, exchange_zip: UploadFile = File(...)):
    payload = await exchange_zip.read(MAX_ZIP_BYTES + 1)
    if len(payload) > MAX_ZIP_BYTES:
        return _flash_redirect("/settings", "ZIP 超过 100MB 限制", "error")
    try:
        preview = request.app.state.history_exchange_service.preview(payload)
    except ValueError as exc:
        return _flash_redirect("/settings", f"导入校验失败：{exc}", "error")
    token = os.urandom(16).hex()
    previews = request.app.state.history_exchange_previews
    previews.clear()
    previews[token] = preview
    return templates.TemplateResponse(
        request,
        "exchange_preview.html",
        {"token": token, "preview": preview},
    )


@router.post("/history-exchange/confirm")
async def confirm_history_exchange(request: Request, token: str = Form(...)):
    preview = request.app.state.history_exchange_previews.pop(token, None)
    if preview is None:
        return _flash_redirect("/settings", "导入预览已失效，请重新选择 ZIP", "error")
    try:
        report = request.app.state.history_exchange_service.merge(preview)
    except Exception as exc:
        return _flash_redirect("/settings", f"导入失败，事务已回滚：{exc}", "error")
    message = f"导入完成：视频 +{report.videos_added}，快照 +{report.snapshots_added}，重复 {report.duplicates}，冲突 {report.conflicts}"
    return _flash_redirect("/settings", message)


@router.post("/shutdown")
async def shutdown_app(request: Request):
    _request_shutdown(request.app)
    return templates.TemplateResponse(
        request,
        "shutdown.html",
        {"message": "程序正在退出，可以关闭这个浏览器页面。"},
    )


@router.post('/up-monitors')
async def add_up_monitor(request: Request, up_input: str = Form(...), detect_interval: int = Form(300), video_interval: int = Form(300)):
    from app.ui.full_text_api import local
    local(request)
    try:
        await request.app.state.up_monitor.add(up_input,detect_interval,video_interval)
        return _flash_redirect('/#up-monitors','UP 检测已添加，首次投稿作为基线，不补录旧视频')
    except AppError as exc:return _flash_redirect('/#up-monitors',str(exc),'error')

@router.post('/up-monitors/{identity}/{action}')
async def update_up_monitor(request: Request, identity: int, action: str, detect_interval: int = Form(300), video_interval: int = Form(300), bvid: str = Form('')):
    from app.ui.full_text_api import local
    local(request);service=request.app.state.up_monitor
    try:
        if not service.store.get(identity):raise AppError('UP 检测不存在')
        if action=='pause':service.store.state(identity,'paused')
        elif action=='resume':
            await service.provider.page(service.store.get(identity)['mid'])
            service.store.state(identity,'running')
        elif action=='remove':service.store.remove(identity)
        elif action=='check':
            result=await service.poll(identity)
            if result and (result.get('skipped') or result.get('error')):
                return _flash_redirect('/#up-monitors',result.get('skipped') or result['error'],'error')
        elif action=='promote':service.store.promote(identity,bvid)
        elif action=='interval':
            service.validate_intervals(detect_interval,video_interval);service.store.intervals(identity,detect_interval,video_interval)
        else:raise AppError('UP 操作不正确')
        return _flash_redirect('/#up-monitors','UP 检测设置已更新')
    except AppError as exc:return _flash_redirect('/#up-monitors',str(exc),'error')

@router.post('/reports/{filename}/open')
async def open_report_external(request: Request, filename: str):
    from app.ui.full_text_api import local
    local(request)
    try:
        bvid=request.app.state.report_service.open(filename)
        return _flash_redirect(f'/videos/{bvid}','报告已在系统浏览器打开')
    except AppError as exc:return _flash_redirect(f'/videos/{filename.split("_")[0]}',str(exc),'error')

@router.post('/reports/{filename}/delete')
async def delete_report(request: Request, filename: str):
    from app.ui.full_text_api import local
    local(request)
    try:
        bvid=request.app.state.report_service.delete(filename)
        return _flash_redirect(f'/videos/{bvid}','报告已删除')
    except (AppError,OSError):return _flash_redirect('/', '报告无法删除，请检查文件位置或占用情况','error')


@router.get('/api/up-monitors/status')
async def up_monitor_status(request: Request):
    from app.ui.dashboard import local_time
    state=request.app.state.up_monitor.state_snapshot()
    state['checked']={k:local_time(v) for k,v in state['checked'].items()}
    return JSONResponse(state,headers={'Cache-Control':'no-store'})


@router.post('/recovery/restart-detection')
async def restart_detection(request: Request):
    from app.ui.full_text_api import local
    local(request)
    result=await request.app.state.recovery.run()
    if 'skipped' in result and isinstance(result['skipped'],str):return _flash_redirect('/',result['skipped'])
    return _flash_redirect('/',f"已安排视频 {result['videos']}、UP {result['ups']} 重新检测，跳过 {result['skipped']}；调度器将执行。手动暂停、回收站、登录待验证及风控/未知类型冷却保持不变。")
