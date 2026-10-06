from services.backup_service import BackupService


def test_database_dump_contains_saved_text(database, tmp_path):
    database.add_user(7, "student", "Ann", None)
    assert database.add_audio_request(7, "file-1", 10, 1.5, "lecture")

    service = BackupService(backup_dir=str(tmp_path / "backups"), dsn=database.dsn)
    dump_path = service.create_backup()

    assert dump_path
    dump = open(dump_path, encoding="utf-8").read()
    assert "INSERT INTO audio_requests" in dump
    assert "lecture" in dump
