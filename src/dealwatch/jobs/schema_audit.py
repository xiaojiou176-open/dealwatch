from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from dealwatch.infra.config import Settings
from dealwatch.legacy.db_repo import DatabaseRepository


#########################################################
# Constants
#########################################################
_DEFAULT_LOG_LEVEL: Final[str] = "INFO"


#########################################################
# Schema Audit
#########################################################
@dataclass(slots=True)
class SchemaAuditJob:
    repo: DatabaseRepository
    backup_dir: Path | None = None
    apply_migrations: bool = True
    strict: bool = False
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.backup_dir is not None and not isinstance(self.backup_dir, Path):
            self.backup_dir = Path(self.backup_dir)
        self.logger = logging.getLogger(__name__)

    async def run(self) -> int:
        if not self.repo.db_path.exists() and not self.apply_migrations:
            self.logger.error("Database file not found: %s", self.repo.db_path)
            return 1

        if self.backup_dir is not None:
            backup_path = await self.repo.backup_db(self.backup_dir)
            if backup_path is None:
                self.logger.warning("Database backup not created.")
            else:
                self.logger.info("Database backup created: %s", backup_path)

        if self.apply_migrations:
            await self.repo.initialize()

        issues = await self.repo.audit_schema()
        version_issue = await self.repo.check_schema_version()
        if version_issue:
            issues.append(version_issue)
        if issues:
            for issue in issues:
                self.logger.error("Schema issue detected: %s", issue)
            return 1 if self.strict else 0

        self.logger.info("Schema audit passed with no issues.")
        return 0


#########################################################
# CLI
#########################################################
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit SQLite schema versioning.")
    parser.add_argument("--db", default="", help="Override DB path.")
    parser.add_argument("--backup", action="store_true", help="Create DB backup before audit.")
    parser.add_argument("--backup-dir", default="", help="Backup directory path.")
    parser.add_argument("--no-migrate", action="store_true", help="Skip migrations.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if issues found.")
    parser.add_argument("--log-level", default=_DEFAULT_LOG_LEVEL, help="Log level.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    settings = Settings()
    if args.db:
        settings.DB_PATH = Path(args.db)

    logging.basicConfig(level=str(args.log_level).upper())
    repo = DatabaseRepository(settings.DB_PATH)

    backup_dir = Path(args.backup_dir) if args.backup_dir else None
    job = SchemaAuditJob(
        repo=repo,
        backup_dir=backup_dir if args.backup else None,
        apply_migrations=not args.no_migrate,
        strict=bool(args.strict),
    )
    raise SystemExit(asyncio.run(job.run()))


if __name__ == "__main__":
    main()
