"""Manual public text probe using disposable storage; never edits the user's database."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.collectors.bilibili_client import BilibiliClient
from app.collectors.provider import BilibiliWebProvider
from app.database import Database, Repository
from app.services.phase2_service import Phase2Service


async def probe(bvid):
    with tempfile.TemporaryDirectory(prefix="bilibili-public-text-") as folder:
        db = Database(Path(folder) / "probe.db")
        db.initialize()
        repo = Repository(db)
        provider = BilibiliWebProvider(BilibiliClient(min_interval_seconds=3, max_retries=0))
        video = await provider.fetch_video_info(bvid)
        repo.upsert_video(video)
        service = Phase2Service(repo, provider, 20, 5)
        result = {"bvid": bvid, "storage": "disposable", "cookies": False}
        async def all_danmaku(bvid):
            return await service.collect_danmaku_once(bvid, all_parts=True)
        for kind, operation in [("comments", service.collect_comments_once), ("danmaku", all_danmaku)]:
            try:
                result[kind] = {"saved": await operation(bvid)}
                rows = repo.list_comments(bvid, 10000) if kind == "comments" else repo.list_danmaku(bvid, 10000)
                field = "message" if kind == "comments" else "text"
                result[kind]["nonempty"] = sum(bool(row[field]) for row in rows)
            except Exception as exc:
                result[kind] = {"error": str(exc), "type": type(exc).__name__}
        result["scope"] = repo.text_dashboard_data(bvid)["runs"]
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bvid")
    asyncio.run(probe(parser.parse_args().bvid))
