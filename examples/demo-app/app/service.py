from app.auth import create_token, hash_password, verify_password
from app.database import create_user, get_user


def normalize_username(username: str) -> str:
    """Trim surrounding whitespace and normalize a username to lowercase."""
    return username.strip().lower()


def register_user(username: str, password: str):
    normalized_username = normalize_username(username)
    password_hash = hash_password(password)

    create_user(
        normalized_username,
        password_hash,
    )

    return {
        "username": normalized_username,
        "registered": True,
    }


def login_user(username: str, password: str):
    """Authenticate an existing user and return a token if successful."""
    user = get_user(username)

    if user is None:
        return None

    _, stored_username, stored_hash = user

    if not verify_password(password, stored_hash):
        return None

    return {
        "username": stored_username,
        "token": create_token(stored_username),
    }
