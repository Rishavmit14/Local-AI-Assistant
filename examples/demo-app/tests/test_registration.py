from app.database import get_user, initialize_database
from app.service import register_user


def test_registration_normalizes_username():
    initialize_database()

    result = register_user(
        "  AliceExample  ",
        "password123",
    )

    assert result["username"] == "aliceexample"

    stored_user = get_user("aliceexample")

    assert stored_user is not None
    assert stored_user[1] == "aliceexample"
