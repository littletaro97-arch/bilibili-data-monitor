from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import PurePosixPath
import uuid
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

from app.database import Repository


FORMAT_NAME = "bilibili-history-exchange"
FORMAT_VERSION = 1
REQUIRED_FILES = {"manifest.json", "videos.json", "snapshots.json", "checksums.json"}
MAX_ZIP_BYTES = 100 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 200 * 1024 * 1024
MAX_JSON_BYTES = 100 * 1024 * 1024
MAX_ENTRIES = 8
MAX_COMPRESSION_RATIO = 100
SOURCES = {"MANUAL", "AUTO", "UNKNOWN"}


@dataclass(frozen=True)
class ExchangePreview:
    manifest: dict
    videos: list[dict]
    snapshots: list[dict]


@dataclass(frozen=True)
class ImportReport:
    videos_added: int
    snapshots_added: int
    duplicates: int
    conflicts: int
    invalid: int = 0


class HistoryExchangeService:
    def __init__(self, repository: Repository, app_version: str = "0.11.1"):
        self.repository = repository
        self.app_version = app_version

    def export_zip(self) -> bytes:
        with self.repository.database.connect() as conn:
            videos = [self._video_row(dict(row)) for row in conn.execute("SELECT * FROM videos ORDER BY bvid")]
            snapshots = [self._snapshot_row(dict(row)) for row in conn.execute("SELECT * FROM video_stats_snapshot")]
            snapshots.sort(key=lambda item: (item["bvId"], item["collectedAt"], item["contentSha256"]))
        exported_at = _utc_now()
        manifest = {
            "formatName": FORMAT_NAME,
            "formatVersion": FORMAT_VERSION,
            "exportId": str(uuid.uuid4()),
            "exportedAt": exported_at,
            "sourcePlatform": "windows",
            "sourceAppVersion": self.app_version,
            "schemaVersion": 1,
            "recordCounts": {"videos": len(videos), "snapshots": len(snapshots)},
            "includedSections": ["videos", "snapshots"],
            "timeStandard": "UTC RFC3339",
            "checksumAlgorithm": "SHA-256",
        }
        files = {
            "manifest.json": _json_bytes(manifest),
            "videos.json": _json_bytes(videos),
            "snapshots.json": _json_bytes(snapshots),
        }
        files["checksums.json"] = _json_bytes({name: sha256(value).hexdigest() for name, value in files.items()})
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return output.getvalue()

    def preview(self, payload: bytes) -> ExchangePreview:
        if len(payload) > MAX_ZIP_BYTES:
            raise ValueError("ZIP 超过 100MB 限制")
        try:
            with ZipFile(BytesIO(payload), "r") as archive:
                infos = archive.infolist()
                self._validate_entries(infos)
                files = {info.filename: archive.read(info) for info in infos}
        except BadZipFile as exc:
            raise ValueError("文件不是有效 ZIP") from exc
        checksums = _load_json(files["checksums.json"], "checksums.json")
        for name in ("manifest.json", "videos.json", "snapshots.json"):
            if checksums.get(name) != sha256(files[name]).hexdigest():
                raise ValueError(f"{name} SHA-256 校验失败")
        manifest = _load_json(files["manifest.json"], "manifest.json")
        if manifest.get("formatName") != FORMAT_NAME:
            raise ValueError("未知交换格式")
        if manifest.get("formatVersion") != FORMAT_VERSION:
            raise ValueError("不支持的 formatVersion")
        videos = _load_json(files["videos.json"], "videos.json")
        snapshots = _load_json(files["snapshots.json"], "snapshots.json")
        if not isinstance(videos, list) or not isinstance(snapshots, list):
            raise ValueError("记录文件必须是 JSON 数组")
        validated_videos = [self._validate_video(item) for item in videos]
        validated_snapshots = [self._validate_snapshot(item) for item in snapshots]
        counts = manifest.get("recordCounts", {})
        if counts != {"videos": len(validated_videos), "snapshots": len(validated_snapshots)}:
            raise ValueError("记录数量与 manifest 不一致")
        return ExchangePreview(manifest, validated_videos, validated_snapshots)

    def merge(self, preview: ExchangePreview) -> ImportReport:
        videos_added = snapshots_added = duplicates = conflicts = 0
        with self.repository.database.connect() as conn:
            for video in preview.videos:
                exists = conn.execute("SELECT 1 FROM videos WHERE bvid=?", (video["bvId"],)).fetchone()
                if not exists:
                    now = _utc_now()
                    conn.execute(
                        """INSERT INTO videos (bvid, aid, title, owner_mid, owner_name, pubdate, duration, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (video["bvId"], video.get("aid"), video.get("title"), video.get("authorMid"), video.get("authorName"), video.get("pubdate"), video.get("duration"), now, now),
                    )
                    videos_added += 1
            for snapshot in preview.snapshots:
                candidates = conn.execute(
                    "SELECT * FROM video_stats_snapshot WHERE bvid=? AND collection_source=?",
                    (snapshot["bvId"], snapshot["collectionSource"]),
                ).fetchall()
                matches = [row for row in candidates if _utc_time(row["captured_at"]) == snapshot["collectedAt"]]
                digest = snapshot["contentSha256"]
                existing_digests = {_snapshot_digest(self._snapshot_row(dict(row))) for row in matches}
                if digest in existing_digests:
                    duplicates += 1
                elif matches:
                    conflicts += 1
                elif not conn.execute("SELECT 1 FROM videos WHERE bvid=?", (snapshot["bvId"],)).fetchone():
                    conflicts += 1
                else:
                    conn.execute(
                        """INSERT INTO video_stats_snapshot
                           (bvid,captured_at,view_count,danmaku_count,reply_count,favorite_count,coin_count,share_count,like_count,source_type,collection_source,exchange_digest)
                           VALUES (?,?,?,?,?,?,?,?,?,'imported',?,?)""",
                        (snapshot["bvId"], snapshot["collectedAt"], snapshot.get("viewCount"), snapshot.get("danmakuCount"), snapshot.get("replyCount"), snapshot.get("favoriteCount"), snapshot.get("coinCount"), snapshot.get("shareCount"), snapshot.get("likeCount"), snapshot["collectionSource"], digest),
                    )
                    snapshots_added += 1
        return ImportReport(videos_added, snapshots_added, duplicates, conflicts)

    def _validate_entries(self, infos: list[ZipInfo]) -> None:
        if len(infos) > MAX_ENTRIES or {item.filename for item in infos} != REQUIRED_FILES:
            raise ValueError("ZIP 文件结构不符合交换格式")
        if len({item.filename for item in infos}) != len(infos):
            raise ValueError("ZIP 包含重复条目")
        total = 0
        for info in infos:
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                raise ValueError("ZIP 包含非法路径")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("ZIP 不允许符号链接")
            total += info.file_size
            if info.file_size > MAX_JSON_BYTES or total > MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("ZIP 解压大小超过限制")
            if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                raise ValueError("ZIP 压缩比异常")

    @staticmethod
    def _video_row(row: dict) -> dict:
        return {"bvId": row["bvid"], "aid": row.get("aid"), "title": row.get("title"), "authorName": row.get("owner_name"), "authorMid": row.get("owner_mid"), "duration": row.get("duration"), "pubdate": row.get("pubdate"), "sourceUrl": f"https://www.bilibili.com/video/{row['bvid']}"}

    @staticmethod
    def _snapshot_row(row: dict) -> dict:
        item = {"bvId": row["bvid"], "collectedAt": _utc_time(row["captured_at"]), "collectionSource": row.get("collection_source") if row.get("collection_source") in SOURCES else "UNKNOWN", "viewCount": row.get("view_count"), "danmakuCount": row.get("danmaku_count"), "replyCount": row.get("reply_count"), "favoriteCount": row.get("favorite_count"), "coinCount": row.get("coin_count"), "shareCount": row.get("share_count"), "likeCount": row.get("like_count"), "fetchStatus": "success", "errorMessage": None}
        item["contentSha256"] = _snapshot_digest(item)
        return item

    @staticmethod
    def _validate_video(item: object) -> dict:
        if not isinstance(item, dict) or not _valid_bv(item.get("bvId")):
            raise ValueError("videos.json 包含无效 BV")
        return item

    @staticmethod
    def _validate_snapshot(item: object) -> dict:
        if not isinstance(item, dict) or not _valid_bv(item.get("bvId")):
            raise ValueError("snapshots.json 包含无效 BV")
        result = dict(item)
        result["collectedAt"] = _utc_time(result.get("collectedAt"))
        if result.get("collectionSource") not in SOURCES:
            raise ValueError("无效 collectionSource")
        for name in ("viewCount", "danmakuCount", "replyCount", "favoriteCount", "coinCount", "shareCount", "likeCount"):
            value = result.get(name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 2**63 - 1):
                raise ValueError(f"{name} 必须是非负64位整数或 null")
        if result.get("contentSha256") != _snapshot_digest(result):
            raise ValueError("快照内容摘要不匹配")
        return result


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_json(payload: bytes, name: str):
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} JSON 损坏") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_time(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("无效 UTC 时间")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("无效 UTC 时间") from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    utc = parsed.astimezone(timezone.utc)
    base = utc.strftime("%Y-%m-%dT%H:%M:%S")
    if not utc.microsecond:
        fraction = ""
    elif utc.microsecond % 1000 == 0:
        fraction = f".{utc.microsecond // 1000:03d}"
    else:
        fraction = f".{utc.microsecond:06d}"
    return f"{base}{fraction}Z"


def _snapshot_digest(item: dict) -> str:
    fields = ("bvId", "collectedAt", "collectionSource", "viewCount", "danmakuCount", "replyCount", "favoriteCount", "coinCount", "shareCount", "likeCount", "fetchStatus", "errorMessage")
    canonical = "\x1f".join("null" if item.get(name) is None else str(item.get(name)) for name in fields)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _valid_bv(value: object) -> bool:
    return isinstance(value, str) and len(value) == 12 and value.startswith("BV") and value.isalnum()
