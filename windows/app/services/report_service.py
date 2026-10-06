from __future__ import annotations

from datetime import datetime
import re
import webbrowser
from app.models import AppError
from app.database import iso_now
from pathlib import Path

from markupsafe import Markup
from app.config import BASE_DIR

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.database import Repository
from app.services.analysis_service import build_chart_blocks, build_summary


class ReportService:
    def __init__(self, repository: Repository, output_dir: str | Path, template_dir: str | Path):
        self.repository = repository
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
        )

    def generate(self, bvid: str) -> Path:
        if not re.fullmatch(r"BV[0-9A-Za-z]{10}",bvid):raise AppError("视频编号不正确")
        video = self.repository.get_video(bvid)
        if not video:raise AppError("视频不存在")
        task = self.repository.get_task_by_bvid(bvid)
        snapshots = self.repository.list_snapshots(bvid)
        latest = snapshots[-1] if snapshots else None
        charts = build_chart_blocks(snapshots, include_plotlyjs=True)
        template = self.env.get_template("report.html.j2")
        generated_at = datetime.now().astimezone().isoformat()
        html = template.render(
            appearance_css=Markup((BASE_DIR / "app/assets/appearance.css").read_text(encoding="utf-8")),
            appearance_js=Markup((BASE_DIR / "app/assets/appearance.js").read_text(encoding="utf-8")),
            video=video,
            task=task,
            snapshots=snapshots,
            latest=latest,
            charts=charts,
            summary=build_summary(snapshots),
            generated_at=generated_at,
            collection_start=snapshots[0]["captured_at"] if snapshots else "暂无",
            collection_end=snapshots[-1]["captured_at"] if snapshots else "暂无",
        )
        path = self.output_dir / f"{bvid}_{datetime.now().astimezone().strftime('%Y%m%d_%H%M%S_%f')}.html"
        path.write_text(html, encoding="utf-8")
        self.register(path, bvid)
        self.repository.add_log("INFO", "生成 HTML 报告", bvid=bvid, detail=str(path))
        return path

    def register(self, path, bvid):
        path=Path(path).absolute()
        if not re.fullmatch(r'BV[0-9A-Za-z]{10}_[0-9_]+\.html',path.name):return
        with self.repository.database.connect() as c:
            c.execute('INSERT OR IGNORE INTO html_reports(filename,bvid,path,created_at) VALUES (?,?,?,?)',(path.name,bvid,str(path),iso_now()))

    def recent(self,bvid,limit=20):
        for p in self.output_dir.glob(f'{bvid}_*.html'):self.register(p,bvid)
        # Old releases logged each report path, including reports moved before migration.
        with self.repository.database.connect() as c:
            logs=c.execute("SELECT detail FROM crawl_logs WHERE bvid=? AND message='生成 HTML 报告' AND detail IS NOT NULL",(bvid,)).fetchall()
        for r in logs:self.register(Path(r['detail']),bvid)
        with self.repository.database.connect() as c:
            rows=c.execute('SELECT * FROM html_reports WHERE bvid=? AND deleted=0 ORDER BY filename DESC LIMIT ?',(bvid,limit)).fetchall()
        return [{'name':r['filename'],'url':f'/reports/{r["filename"]}/open','available':Path(r['path']).is_file()} for r in rows]

    def known(self,filename):
        if not re.fullmatch(r'BV[0-9A-Za-z]{10}_[0-9_]+\.html',filename):raise AppError('报告文件名不正确')
        with self.repository.database.connect() as c:r=c.execute('SELECT * FROM html_reports WHERE filename=?',(filename,)).fetchone()
        if r and r['deleted']:raise AppError('报告已删除')
        if not r:
            path=self.output_dir/filename
            if path.is_file():self.register(path,filename.split('_')[0]);return self.known(filename)
            raise AppError('报告路径已改变或文件已不存在')
        return r

    def open(self,filename):
        r=self.known(filename);path=Path(r['path'])
        if not path.is_file():raise AppError('报告路径已改变或文件已不存在')
        from app.config import settings
        if not webbrowser.open(f"http://127.0.0.1:{settings.app.port}/reports/{filename}"):raise AppError('无法打开系统浏览器')
        return r['bvid']

    def delete(self,filename):
        r=self.known(filename);path=Path(r['path'])
        # Delete only this registered HTML file; no directory or path supplied by clients.
        if path.exists():path.unlink()
        with self.repository.database.connect() as c:c.execute('UPDATE html_reports SET deleted=1 WHERE filename=?',(filename,))
        self.repository.add_log('INFO','删除 HTML 报告',bvid=r['bvid'])
        return r['bvid']
