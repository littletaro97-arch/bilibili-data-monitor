import pytest

from app.config import AppConfig, LanConfig, Settings
from app.main import resolve_bind_host


def test_default_settings_are_local_only():
    settings = Settings()

    assert settings.app.host == "127.0.0.1"
    assert settings.lan.enabled is False
    assert resolve_bind_host(settings) == "127.0.0.1"


def test_lan_mode_requires_password_hash():
    settings = Settings(lan=LanConfig(enabled=True, password_hash=""))

    with pytest.raises(RuntimeError, match="LAN access requires a password"):
        resolve_bind_host(settings)


def test_lan_mode_binds_all_interfaces_when_password_is_set():
    settings = Settings(lan=LanConfig(enabled=True, password_hash="pbkdf2_sha256$placeholder"))

    assert resolve_bind_host(settings) == "0.0.0.0"


def test_non_local_host_is_rejected_when_lan_is_disabled():
    settings = Settings(app=AppConfig(host="0.0.0.0"), lan=LanConfig(enabled=False))

    with pytest.raises(RuntimeError, match="must listen on 127.0.0.1"):
        resolve_bind_host(settings)
