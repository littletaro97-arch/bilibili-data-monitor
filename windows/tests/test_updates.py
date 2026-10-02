import hashlib
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.services.update_service import REPOSITORY, UpdateService, UpdateError, safe_download_url


def release(version="0.12.0", revision=1, content=b"synthetic installer bytes"):
    name = f"BilibiliMonitor-v{version}-installer.{revision}-windows-x64-setup.exe"
    tag = f"windows-v{version}-installer.{revision}"
    return {"tag_name": tag, "draft": False, "prerelease": False, "body": "<script>notes</script>", "assets": [{
        "name": name, "state": "uploaded", "size": len(content),
        "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
        "browser_download_url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{name}",
    }]}


@pytest.mark.asyncio
async def test_select_windows_numeric_version_and_installer_revision(tmp_path):
    android = {"tag_name": "v99.0.0", "assets": [{"name": "bilibili-android.apk"}]}
    prerelease = release("2.0.0")
    prerelease["prerelease"] = True
    draft = release("3.0.0")
    draft["draft"] = True
    data = [android, prerelease, draft, release("0.9.9"), release("0.12.0"), release("0.12.0", 2)]
    service = UpdateService(tmp_path, httpx.MockTransport(lambda request: httpx.Response(200, json=data)))
    await service.check()
    assert service.available and service.package.version == (0, 12, 0, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("version,revision,available", [("0.11.1", 1, False), ("0.11.1", 2, True), ("0.10.9", 99, False)])
async def test_compare_current_version(tmp_path, version, revision, available):
    service = UpdateService(tmp_path, httpx.MockTransport(lambda request: httpx.Response(200, json=[release(version, revision)])))
    await service.check()
    assert service.available is available


@pytest.mark.asyncio
async def test_scan_past_android_only_page(tmp_path):
    def respond(request):
        if request.url.params["page"] == "1":
            return httpx.Response(200, json=[{"tag_name": "android", "assets": []}] * 100)
        return httpx.Response(200, json=[release()])
    service = UpdateService(tmp_path, httpx.MockTransport(respond))
    await service.check()
    assert service.available


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 404, 429, 500])
async def test_api_failure_clears_stale_download(tmp_path, status):
    service = UpdateService(tmp_path, httpx.MockTransport(lambda request: httpx.Response(200, json=[release()])))
    await service.check()
    assert service.available
    service.transport = httpx.MockTransport(lambda request: httpx.Response(status))
    await service.check()
    assert service.package is None and not service.available
    assert "当前版本不低于" not in service.status


@pytest.mark.asyncio
async def test_missing_digest_does_not_offer_download(tmp_path):
    item = release()
    del item["assets"][0]["digest"]
    service = UpdateService(tmp_path, httpx.MockTransport(lambda request: httpx.Response(200, json=[item])))
    await service.check()
    assert service.available and service.package.digest is None
    with pytest.raises(UpdateError):
        await service.download()


@pytest.mark.asyncio
async def test_wrong_repository_asset_is_rejected(tmp_path):
    item = release()
    item["assets"][0]["browser_download_url"] = "https://github.com/attacker/project/setup.exe"
    service = UpdateService(tmp_path, httpx.MockTransport(lambda request: httpx.Response(200, json=[item])))
    await service.check()
    assert service.package is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "digest", "size", "redirect", "network"])
async def test_verified_download_and_cleanup(tmp_path, failure):
    content = b"synthetic installer bytes"
    item = release(content=content)
    def respond(request):
        if request.url.host == "api.github.com":
            return httpx.Response(200, json=[item])
        if request.url.host == "github.com":
            location = "http://evil.example/setup.exe" if failure == "redirect" else "https://release-assets.githubusercontent.com/test-asset"
            return httpx.Response(302, headers={"Location": location})
        if failure == "network":
            raise httpx.ConnectError("offline", request=request)
        body = b"X" * len(content) if failure == "digest" else content + b"x" if failure == "size" else content
        return httpx.Response(200, content=body)
    service = UpdateService(tmp_path, httpx.MockTransport(respond))
    await service.check()
    if failure:
        with pytest.raises(UpdateError):
            await service.download()
        assert not list(tmp_path.iterdir())
    else:
        path, name = await service.download()
        assert path.read_bytes() == content and name == item["assets"][0]["name"]
        assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("url", ["http://github.com/a", "https://github.com.evil.example/a", "https://user:pass@github.com/a", "https://127.0.0.1/a", "https://github.com:8443/a", "https://[bad/a"])
def test_download_url_boundaries(url):
    assert not safe_download_url(url)


def test_settings_check_and_download_routes(tmp_path):
    from app.main import create_app
    app = create_app()
    item = release()
    def respond(request):
        if request.url.host == "api.github.com":
            return httpx.Response(200, json=[item])
        return httpx.Response(200, content=b"synthetic installer bytes")
    app.state.update_service = UpdateService(tmp_path, httpx.MockTransport(respond))
    client = TestClient(app)
    assert "尚未检查更新" in client.get("/settings").text
    response = client.post("/settings/updates/check")
    assert response.status_code == 200 and "下载更新安装包" in response.text
    assert "&lt;script&gt;notes&lt;/script&gt;" in response.text
    response = client.get("/settings/updates/download")
    assert response.status_code == 200 and response.content == b"synthetic installer bytes"
    assert "attachment" in response.headers["content-disposition"]


def test_installer_retains_application_identity_and_previous_directory():
    script = (Path(__file__).parents[1] / "packaging" / "installer.iss").read_text(encoding="utf-8")
    assert "AppId={{C3C19C03-7F8E-48E4-95F3-B497EB0C6AE6}" in script
    assert "UsePreviousAppDir=yes" in script
