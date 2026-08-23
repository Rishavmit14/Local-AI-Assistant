import hashlib
import hmac


SECRET_KEY = "demo-secret-key"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    candidate = hash_password(password)
    return hmac.compare_digest(candidate, stored_hash)


def create_token(username: str) -> str:
    payload = f"{username}:{SECRET_KEY}"
    return hashlib.sha256(payload.encode()).hexdigest()


def verify_token(username: str, token: str) -> bool:
    expected = create_token(username)
    return hmac.compare_digest(expected, token)
