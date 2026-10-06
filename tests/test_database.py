def test_statement_timeout_and_reconnect(database):
    with database.connection.cursor() as cursor:
        cursor.execute("SHOW statement_timeout")
        timeout = cursor.fetchone()[0]
    assert timeout == "5s"

    database.add_user(42, "student", "Ann", None)
    database.connection.close()
    assert database.get_language(42) == "ru"
    assert database.set_language(42, "en")
    assert database.get_language(42) == "en"


def test_migrations_apply_once(database):
    with database.connection.cursor() as cursor:
        cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
        versions = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT to_regclass('public.statistics'), to_regclass('public.users')")
        statistics, users = cursor.fetchone()
    assert versions == ["001_initial.sql"]
    assert statistics is None
    assert users == "users"
    assert database.apply_migrations()


def test_user_stats_and_language(database):
    telegram_id = 1001
    database.add_user(telegram_id, "student", "Ann", None)
    assert database.get_language(telegram_id) == "ru"
    assert database.set_language(telegram_id, "en")
    assert database.get_language(telegram_id) == "en"

    request_id = database.add_audio_request(
        telegram_id,
        "file-1",
        file_size=2048,
        duration=12.5,
        recognized_text="лекция",
    )
    assert request_id

    total, size, duration = database.get_user_stats(telegram_id)
    assert total == 1
    assert size == 2048
    assert duration == 12.5
    assert database.add_feedback(request_id, 5)
