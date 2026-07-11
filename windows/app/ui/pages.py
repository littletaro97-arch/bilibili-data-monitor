from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import socket
import threading
import time

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from plotly.offline import get_plotlyjs

from app.config import load_settings, settings
from app.config_writer import save_lan_settings, save_launcher_settings
from app.logger import clear_log_file
from app.models import AppError
from app.security import session_token, verify_password
from app.services.analysis_service import (
    METRICS,
    build_chart_blocks,
    build_danmaku_density_chart,
    build_dual_axis_chart,
    build_ratio_chart,
    build_summary,
    count_imported_snapshots,
    top_words,
)
from app.services.history_import_service import parse_history_csv
from app.services.history_exchange_service import MAX_ZIP_BYTES
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
    current_settings = load_settings()
    local_ip = _local_ip()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "tasks": repo.list_tasks(),
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
    return _latest_payload(repo.latest_snapshot(bvid), repo.get_task_by_bvid(bvid))


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
    comments = repo.list_comments(bvid, limit=200)
    danmaku = repo.list_danmaku(bvid, limit=500)
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
            "task": task,
            "snapshots": snapshots,
            "latest": snapshots[-1] if snapshots else None,
            "charts": build_chart_blocks(snapshots, include_plotlyjs=False),
            "dual_axis_chart": build_dual_axis_chart(snapshots, left_metric, right_metric),
            "ratio_chart": build_ratio_chart(snapshots, ratio_numerator, ratio_denominator),
            "metric_options": METRICS,
            "left_metric": left_metric,
            "right_metric": right_metric,
            "ratio_numerator": ratio_numerator,
            "ratio_denominator": ratio_denominator,
            "imported_snapshot_count": count_imported_snapshots(snapshots),
            "summary": build_summary(snapshots),
            "latest_refresh_seconds": settings.crawl.min_interval,
            "report_output_dir": settings.report_output_dir,
            "reports": _recent_reports(bvid),
            "comments": comments[:30],
            "danmaku": danmaku[:50],
            "comment_top_words": top_words(comments, field="message", limit=20),
            "danmaku_top_words": top_words(danmaku, field="text", limit=20),
            "danmaku_density_chart": build_danmaku_density_chart(danmaku),
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
async def generate_report(request: Request, bvid: str):
    try:
        path = request.app.state.report_service.generate(bvid)
        return _flash_redirect(f"/videos/{bvid}", f"报告已生成：{path.name}；保存位置：{path.parent}")
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


@router.post("/settings/launcher")
async def update_launcher_settings(show_console: str | None = Form(None)):
    save_launcher_settings(show_console=show_console == "on")
    return _flash_redirect("/settings", "启动设置已保存，下次运行 run.bat 时生效")


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
    _request_shutdown()
    return templates.TemplateResponse(
        request,
        "shutdown.html",
        {"message": "程序正在退出，可以关闭这个浏览器页面。"},
    )
