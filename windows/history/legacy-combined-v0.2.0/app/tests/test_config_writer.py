import tomllib

from app import config_writer
from app.config import Settings


def test_save_launcher_settings_writes_launcher_block(tmp_path, monkeypatch):
    monkeypatch.setattr(config_writer, "BASE_DIR", tmp_path)
    monkeypatch.setattr(config_writer, "load_settings", lambda: Settings())

    config_writer.save_launcher_settings(show_console=False)

    raw = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert raw["launcher"]["show_console"] is False
    assert raw["lan"]["enabled"] is False


def test_save_lan_settings_preserves_launcher_setting(tmp_path, monkeypatch):
    current = Settings()
    current = Settings(launcher=type(current.launcher)(show_console=False))
    monkeypatch.setattr(config_writer, "BASE_DIR", tmp_path)
    monkeypatch.setattr(config_writer, "load_settings", lambda: current)

    config_writer.save_lan_settings(enabled=False)

    raw = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))
    assert raw["launcher"]["show_console"] is False
