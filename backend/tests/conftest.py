import os

# Must happen BEFORE `app` is imported anywhere: it decides which
# DATABASE_URL app/config.py picks up. Tests never touch MySQL —
# they run fully offline against an in-memory SQLite DB.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402  (import order is intentional, see above)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
