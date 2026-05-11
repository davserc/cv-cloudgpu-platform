import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure the service root and libs are on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Stub heavy dependencies before importing the app
sys.modules.setdefault("kafka", MagicMock())
sys.modules.setdefault("kafka.KafkaProducer", MagicMock())

# Stub common.db so the app doesn't need a real DB at import time
_db_mock = MagicMock()
sys.modules.setdefault("common", MagicMock())
sys.modules.setdefault("common.db", _db_mock)

# Stub contracts
_contracts_mock = MagicMock()
sys.modules.setdefault("contracts", MagicMock())
sys.modules.setdefault("contracts.events", _contracts_mock)


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("API_GATEWAY_API_KEY", "test-secret")
    return "test-secret"
