import sqlite3

import pytest

from dealwatch.legacy.db_repo import DatabaseRepository
from dealwatch.jobs.schema_audit import SchemaAuditJob


class _FakeRepo:
    def __init__(self, db_path):
        self.db_path = db_path
        self.backed_up = False
        self.initialized = False
        self._issues: list[str] = []
        self._version_issue: str | None = None

    async def backup_db(self, backup_dir):
        self.backed_up = True
        return backup_dir / "backup.db"

    async def initialize(self):
        self.initialized = True

    async def audit_schema(self):
        return list(self._issues)

    async def check_schema_version(self):
        return self._version_issue


@pytest.mark.asyncio
async def test_schema_audit_job_pass(tmp_path) -> None:
    repo = DatabaseRepository(tmp_path / "dealwatch.db")
    await repo.initialize()

    job = SchemaAuditJob(repo=repo, apply_migrations=False)
    code = await job.run()
    assert code == 0


@pytest.mark.asyncio
async def test_schema_audit_job_missing_db(tmp_path) -> None:
    repo = DatabaseRepository(tmp_path / "missing.db")
    job = SchemaAuditJob(repo=repo, apply_migrations=False)
    code = await job.run()
    assert code == 1


@pytest.mark.asyncio
async def test_schema_audit_job_strict_failure(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                product_key TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                last_updated TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    repo = DatabaseRepository(db_path)
    job = SchemaAuditJob(repo=repo, apply_migrations=False, strict=True)
    code = await job.run()
    assert code == 1


@pytest.mark.asyncio
async def test_schema_audit_job_non_strict_with_issues(tmp_path) -> None:
    repo = _FakeRepo(tmp_path / "dealwatch.db")
    repo._issues = ["missing table"]
    repo.db_path.write_text("", encoding="utf-8")
    job = SchemaAuditJob(repo=repo, apply_migrations=False, strict=False)
    code = await job.run()
    assert code == 0


@pytest.mark.asyncio
async def test_schema_audit_job_strict_without_issues(tmp_path) -> None:
    repo = _FakeRepo(tmp_path / "dealwatch.db")
    repo._issues = []
    repo.db_path.write_text("", encoding="utf-8")
    job = SchemaAuditJob(repo=repo, apply_migrations=False, strict=True)
    code = await job.run()
    assert code == 0


@pytest.mark.asyncio
async def test_schema_audit_job_backup_and_migrate(tmp_path) -> None:
    repo = _FakeRepo(tmp_path / "dealwatch.db")
    repo._issues = []
    backup_dir = tmp_path / "backups"
    job = SchemaAuditJob(repo=repo, backup_dir=backup_dir, apply_migrations=True, strict=False)
    code = await job.run()
    assert code == 0
    assert repo.backed_up is True
    assert repo.initialized is True


@pytest.mark.asyncio
async def test_schema_audit_job_strict_version_mismatch(tmp_path) -> None:
    db_path = tmp_path / "dealwatch.db"
    repo = DatabaseRepository(db_path)
    await repo.initialize()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE schema_version SET version = 1 WHERE id = 1;")
        conn.commit()
    finally:
        conn.close()

    job = SchemaAuditJob(repo=repo, apply_migrations=False, strict=True)
    code = await job.run()
    assert code == 1
