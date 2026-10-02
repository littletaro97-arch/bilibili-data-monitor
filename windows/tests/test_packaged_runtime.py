import sys

from app import config, launcher


def test_frozen_runtime_uses_user_data_and_writer_destination(tmp_path, monkeypatch):
    monkeypatch.delenv("BILIBILI_MONITOR_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert config.runtime_directory() == tmp_path / "BilibiliMonitor" / "runtime-data"


def test_runtime_override_is_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("BILIBILI_MONITOR_DATA_DIR", str(tmp_path))
    assert config.runtime_directory() == tmp_path.resolve()


def test_frozen_child_dispatch_does_not_invoke_python_module(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert launcher._command("app.main") == [sys.executable, "--server"]
    assert launcher._command("app.launcher", "--detached") == [sys.executable, "--detached"]


def test_frozen_does_not_import_adjacent_legacy_data(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(config, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / "config.toml").write_text('[app]\nport=9999', encoding="utf-8")
    assert config.migrate_legacy_runtime_data() == []
    assert not (tmp_path / "runtime" / "config.toml").exists()
