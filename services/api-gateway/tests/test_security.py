import pytest
from fastapi import HTTPException

from app.security import require_api_key


def test_missing_api_key_raises_401(monkeypatch):
    monkeypatch.setenv("API_GATEWAY_API_KEY", "secret")
    with pytest.raises(HTTPException) as exc:
        require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


def test_wrong_api_key_raises_403(monkeypatch):
    monkeypatch.setenv("API_GATEWAY_API_KEY", "secret")
    with pytest.raises(HTTPException) as exc:
        require_api_key(x_api_key="wrong")
    assert exc.value.status_code == 403


def test_correct_api_key_passes(monkeypatch):
    monkeypatch.setenv("API_GATEWAY_API_KEY", "secret")
    require_api_key(x_api_key="secret")  # Should not raise


def test_unconfigured_api_key_raises_503(monkeypatch):
    monkeypatch.setenv("API_GATEWAY_API_KEY", "")
    with pytest.raises(HTTPException) as exc:
        require_api_key(x_api_key="anything")
    assert exc.value.status_code == 503
