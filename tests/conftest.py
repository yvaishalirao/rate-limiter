import os
import pytest

# Ensure tests always run with RATE_LIMIT_N=5 regardless of host env.
# Note: this affects in-process imports only. The live server at
# BASE_URL must also be started with RATE_LIMIT_N=5.
@pytest.fixture(autouse=True)
def set_rate_limit_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_N", "5")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_S", "60")
