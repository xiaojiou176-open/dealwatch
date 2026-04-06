from __future__ import annotations

from dataclasses import dataclass
from typing import Final


#########################################################
# Migration Metadata
#########################################################
@dataclass(frozen=True, slots=True)
class MigrationNote:
    version: int
    summary: str


SCHEMA_VERSION_TARGET: Final[int] = 3
_MIGRATION_NOTES: Final[tuple[MigrationNote, ...]] = (
    MigrationNote(2, "Add store_id to price_history and backfill legacy rows."),
    MigrationNote(3, "Add skipped_count to runs for pipeline visibility."),
)


def get_schema_version_target() -> int:
    return SCHEMA_VERSION_TARGET


def describe_migrations(current: int, target: int | None = None) -> list[str]:
    effective_target = SCHEMA_VERSION_TARGET if target is None else target
    return [
        note.summary
        for note in _MIGRATION_NOTES
        if current < note.version <= effective_target
    ]
