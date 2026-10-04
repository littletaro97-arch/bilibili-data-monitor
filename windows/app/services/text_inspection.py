"""Honest, bounded payload for text inspection; no inference from pool size to totals."""
import math


def build_text_panel(raw, video, latest):
    comments = [{"id": r["rpid"], "text": r.get("message") or "", "author": r.get("user_name") or "匿名",
        "likes": r.get("like_count") or 0, "replies": r.get("reply_count") or 0,
        "parent": r.get("parent_rpid"), "sent": r.get("ctime"), "captured": r["captured_at"],
        "visibility":r.get("visibility","unknown"),"checked":r.get("visibility_checked_at"),
        "origin": "local" if r["rpid"].startswith("local-comment-") else "public"} for r in raw["comments"]]
    dm = []
    for row in raw["danmaku"]:
        position = row.get("progress_sec")
        if position is not None and (not math.isfinite(position) or position < 0):
            position = None
        dm.append({"cid": row["cid"], "text": row.get("text") or "", "position": position,
            "sent": row.get("send_time"), "captured": row["captured_at"], "origin": row["origin"],"visibility":row.get("visibility","unknown"),"checked":row.get("visibility_checked_at")})
    parts = {}
    # Most recent metadata wins, including previously sampled parts on interrupted runs.
    for run in raw["runs"]:
        for part in run["metadata"].get("parts", []):
            parts.setdefault(str(part["cid"]), part)
    for row in dm:
        key = str(row["cid"])
        parts.setdefault(key, {"cid": row["cid"], "name": "未记录分 P 名称", "page": None})
    if video:
        cid = dict(video).get("cid")
        if cid is not None:
            parts.setdefault(str(cid), {"cid": cid, "name": "当前默认分 P", "page": 1})
    latest = dict(latest) if latest else {}
    return {"comments": comments, "danmaku": dm, "parts": list(parts.values()),
        "stored_comments": raw["stored_comments"], "stored_danmaku": raw["stored_danmaku"],
        "duplicates": raw["raw_danmaku"] - raw["stored_danmaku"], "truncated": raw["truncated"], "limit": raw["limit"],
        "platform_comments": latest.get("reply_count"), "platform_danmaku": latest.get("danmaku_count"),
        "platform_time": latest.get("captured_at"), "runs": raw["runs"], "complete": False}
