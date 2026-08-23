from app.api import login_endpoint, register_endpoint
from app.database import initialize_database


def main():
    initialize_database()

    print(
        register_endpoint(
            {
                "username": "alice",
                "password": "password123",
            }
        )
    )

    print(
        login_endpoint(
            {
                "username": "alice",
                "password": "password123",
            }
        )
    )


if __name__ == "__main__":
    main()
