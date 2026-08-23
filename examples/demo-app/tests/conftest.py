import pytest

from app.database import set_db_path


@pytest.fixture(autouse=True)
def isolated_database(tmp_path):
    db_path = tmp_path / "test.db"

    set_db_path(db_path)

    yield db_path
