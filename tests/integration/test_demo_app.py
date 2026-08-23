import sys
from pathlib import Path

import pytest


DEMO_ROOT = Path(__file__).resolve().parents[2] / "examples" / "demo-app"
sys.path.insert(0, str(DEMO_ROOT))

from app.api import login_endpoint  # noqa: E402
from app.database import get_user, initialize_database, set_db_path  # noqa: E402
from app.service import register_user  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    set_db_path(tmp_path / "test.db")


def test_demo_failed_login_returns_401():
    initialize_database()
    assert login_endpoint({"username": "missing", "password": "wrong"}) == {
        "status": 401,
        "error": "invalid credentials",
    }


def test_demo_registration_normalizes_username():
    initialize_database()
    result = register_user("  AliceExample  ", "password123")
    stored = get_user("aliceexample")

    assert result["username"] == "aliceexample"
    assert stored is not None and stored[1] == "aliceexample"
