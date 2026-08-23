from app.api import login_endpoint
from app.database import initialize_database


def test_failed_login_returns_401():
    initialize_database()

    response = login_endpoint(
        {
            "username": "does-not-exist",
            "password": "wrong-password",
        }
    )

    assert response["status"] == 401
    assert response["error"] == "invalid credentials"
