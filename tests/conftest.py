import os

import pytest

from core.database import DEFAULT_DSN, Database


@pytest.fixture
def database():
    store = Database(os.getenv("DATABASE_URL", DEFAULT_DSN))
    if not store.init_db():
        pytest.skip("PostgreSQL недоступен")
    with store.connection.cursor() as cursor:
        cursor.execute(
            "TRUNCATE TABLE feedback, audio_requests, users RESTART IDENTITY CASCADE"
        )
    store.connection.commit()
    yield store
    store.close()
