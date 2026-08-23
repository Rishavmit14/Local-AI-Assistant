from app.service import login_user, register_user


def register_endpoint(payload: dict):
    username = payload.get("username")
    if username:
        username = username.strip()
    else:
        username = ""
    password = payload.get("password")

    if not username or not password:
        return {
            "status": 400,
            "error": "username and password are required",
        }

    result = register_user(
        username,
        password,
    )

    return {
        "status": 201,
        "data": result,
    }


def login_endpoint(payload: dict):
    username = payload.get("username")
    password = payload.get("password")

    result = login_user(
        username,
        password,
    )

    # Deliberate bug:
    # unsuccessful authentication should return 401,
    # but this implementation incorrectly returns 200.
    if result is None:
        return {
            "status": 401,
            "error": "invalid credentials",
        }

    return {
        "status": 200,
        "data": result,
    }
