from __future__ import annotations

import json
import logging
import os
import shutil
import stat
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Final, Iterator

from dealwatch.infra.config import (
    DEFAULT_DEDICATED_CHROME_USER_DATA_DIR,
    DEFAULT_EXTERNAL_CACHE_DIR,
    DEFAULT_LOGS_DIR,
    DEFAULT_OPERATOR_DIR,
    DEFAULT_RUNS_DIR,
)
from dealwatch.legacy.db_repo import DatabaseRepository

try:
    import fcntl
except ImportError:  # pragma: no cover - POSIX-only locking is sufficient for current runtime targets.
    fcntl = None


#########################################################
# Constants
#########################################################
_RUNS_DIR: Final[Path] = DEFAULT_RUNS_DIR
_LOGS_DIR: Final[Path] = DEFAULT_LOGS_DIR
_RUN_DATE_FORMAT: Final[str] = "%Y-%m-%d"
_REPORTS_DIR_NAME: Final[str] = "reports"
_REPORT_TIMESTAMP_FORMAT: Final[str] = "%Y%m%d_%H%M%S"
_WATCH_TASKS_DIR_NAME: Final[str] = "watch-tasks"
_ACTIVE_LOG_SUFFIX: Final[str] = ".log"


#########################################################
# Reporting
#########################################################
@dataclass(slots=True)
class MaintenanceAction:
    kind: str
    path: Path
    size_bytes: int
    reason: str
    applied: bool


@dataclass(slots=True)
class MaintenanceSummary:
    dry_run: bool
    actions: list[MaintenanceAction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    legacy_price_history_deleted: int | None = None
    vacuum_attempted: bool = False
    vacuum_completed: bool = False

    @property
    def matched_count(self) -> int:
        return len(self.actions)

    @property
    def estimated_bytes(self) -> int:
        return sum(action.size_bytes for action in self.actions)

    def render_text(self) -> str:
        mode = "dry-run" if self.dry_run else "apply"
        lines = [
            "DealWatch maintenance",
            f"mode={mode}",
            f"matched={self.matched_count}",
            f"estimated_reclaim_bytes={self.estimated_bytes}",
        ]
        for action in self.actions:
            applied = "applied" if action.applied else "planned"
            lines.append(
                f"- {action.kind} | {applied} | {action.path} | {action.size_bytes} bytes | {action.reason}"
            )
        if self.legacy_price_history_deleted is not None:
            lines.append(
                f"legacy_price_history_deleted={self.legacy_price_history_deleted}"
            )
        if self.vacuum_attempted:
            lines.append(
                f"legacy_vacuum={'completed' if self.vacuum_completed else 'failed'}"
            )
        if self.notes:
            lines.append("notes:")
            lines.extend(f"- {note}" for note in self.notes)
        return "\n".join(lines)


#########################################################
# Locking
#########################################################
@contextmanager
def maintenance_lock(lock_path: Path) -> Iterator[bool]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    acquired = False
    try:
        if fcntl is None:
            acquired = True
        else:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                acquired = False
        if acquired:
            handle.seek(0)
            handle.truncate()
            handle.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "acquired_at": datetime.now(timezone.utc).isoformat(),
                    },
                    ensure_ascii=False,
                )
            )
            handle.flush()
        yield acquired
    finally:
        if acquired and fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


#########################################################
# Maintenance
#########################################################
@dataclass(slots=True)
class MaintenanceJob:
    repo: DatabaseRepository | None = None
    runs_dir: Path = _RUNS_DIR
    logs_dir: Path = _LOGS_DIR
    operator_dir: Path = DEFAULT_OPERATOR_DIR
    external_cache_dir: Path = DEFAULT_EXTERNAL_CACHE_DIR
    backups_dir: Path | None = None
    runs_keep_days: int = 30
    reports_keep_days: int = 30
    backups_keep_days: int = 30
    price_history_keep_days: int = 180
    log_retention_days: int = 14
    cache_budget_bytes: int = 4_294_967_296
    dry_run: bool = False
    clean_runtime: bool = True
    clean_legacy: bool = True
    logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.runs_dir, Path):
            self.runs_dir = Path(self.runs_dir)
        if not isinstance(self.logs_dir, Path):
            self.logs_dir = Path(self.logs_dir)
        if self.operator_dir == DEFAULT_OPERATOR_DIR and self.runs_dir != _RUNS_DIR:
            self.operator_dir = self.runs_dir.parent / "operator"
        if not isinstance(self.operator_dir, Path):
            self.operator_dir = Path(self.operator_dir)
        if self.external_cache_dir == DEFAULT_EXTERNAL_CACHE_DIR and self.runs_dir != _RUNS_DIR:
            self.external_cache_dir = self.runs_dir.parent / ".external-cache"
        if not isinstance(self.external_cache_dir, Path):
            self.external_cache_dir = Path(self.external_cache_dir)
        if self.backups_dir is not None and not isinstance(self.backups_dir, Path):
            self.backups_dir = Path(self.backups_dir)
        if self.clean_legacy and self.backups_dir is None:
            repo_db_path = getattr(self.repo, "db_path", None)
            if repo_db_path:
                self.backups_dir = Path(repo_db_path).parent / "backups"
        self.logger = logging.getLogger(__name__)

    async def run(self) -> MaintenanceSummary:
        summary = MaintenanceSummary(dry_run=self.dry_run)
        if self.clean_runtime:
            self._cleanup_runs(summary)
            self._cleanup_reports(summary)
            self._cleanup_logs(summary)
            self._enforce_cache_budget(summary)
        if self.clean_legacy:
            self._cleanup_backups(summary)
            await self._cleanup_price_history(summary)
            await self._vacuum_db(summary)
        return summary

    #########################################################
    # Runs Cleanup
    #########################################################
    def _cleanup_runs(self, summary: MaintenanceSummary) -> None:
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.runs_keep_days)
        if not self.runs_dir.exists():
            self.logger.info("Runs directory does not exist: %s", self.runs_dir)
            return
        self._cleanup_dated_runs(summary, cutoff_dt.date())
        self._cleanup_watch_task_runs(summary, cutoff_dt)

    def _cleanup_dated_runs(
        self,
        summary: MaintenanceSummary,
        cutoff_date: date,
    ) -> None:
        for path in self.runs_dir.iterdir():
            if not path.is_dir():
                continue
            run_date = self._parse_run_date(path.name)
            if run_date is None or run_date >= cutoff_date:
                continue
            self._record_path_action(
                summary,
                kind="run-dir",
                path=path,
                reason="dated run directory older than RUNS_KEEP_DAYS",
                remove_dir=True,
            )

    def _cleanup_watch_task_runs(
        self,
        summary: MaintenanceSummary,
        cutoff_dt: datetime,
    ) -> None:
        watch_tasks_dir = self.runs_dir / _WATCH_TASKS_DIR_NAME
        if not watch_tasks_dir.exists():
            return

        for task_dir in sorted(watch_tasks_dir.iterdir(), key=lambda path: path.name):
            if not task_dir.is_dir():
                continue
            candidates: list[Path] = []
            for run_dir in sorted(task_dir.iterdir(), key=lambda path: path.name):
                if not run_dir.is_dir():
                    continue
                run_timestamp = self._resolve_watch_task_run_timestamp(run_dir)
                if run_timestamp < cutoff_dt:
                    candidates.append(run_dir)

            for run_dir in candidates:
                self._record_path_action(
                    summary,
                    kind="watch-task-run",
                    path=run_dir,
                    reason="watch-task run directory older than RUNS_KEEP_DAYS",
                    remove_dir=True,
                )

            if self._task_dir_should_be_removed(task_dir, candidates, dry_run=self.dry_run):
                self._record_path_action(
                    summary,
                    kind="watch-task-task-dir",
                    path=task_dir,
                    reason="watch-task task directory became empty after cleanup",
                    remove_dir=True,
                )

    @staticmethod
    def _parse_run_date(name: str):
        try:
            return datetime.strptime(name, _RUN_DATE_FORMAT).date()
        except ValueError:
            return None

    def _resolve_watch_task_run_timestamp(self, run_dir: Path) -> datetime:
        summary_path = run_dir / "task_run_summary.json"
        if summary_path.is_file():
            timestamp = self._summary_timestamp(summary_path)
            if timestamp is not None:
                return timestamp
            try:
                return datetime.fromtimestamp(summary_path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return datetime.now(timezone.utc)

    @staticmethod
    def _summary_timestamp(summary_path: Path) -> datetime | None:
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

        run_payload = payload.get("run")
        if not isinstance(run_payload, dict):
            run_payload = {}
        observation_payload = payload.get("observation")
        if not isinstance(observation_payload, dict):
            observation_payload = {}

        candidates = (
            payload.get("captured_at"),
            run_payload.get("finished_at"),
            run_payload.get("started_at"),
            observation_payload.get("observed_at"),
        )
        for candidate in candidates:
            parsed = MaintenanceJob._parse_iso_datetime(candidate)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _parse_iso_datetime(raw: object) -> datetime | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        normalized = raw.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _task_dir_should_be_removed(
        task_dir: Path,
        candidates: list[Path],
        *,
        dry_run: bool,
    ) -> bool:
        if not candidates:
            return False
        if not dry_run:
            return task_dir.exists() and not any(task_dir.iterdir())
        candidate_set = set(candidates)
        for child in task_dir.iterdir():
            if child not in candidate_set:
                return False
        return True

    #########################################################
    # Reports Cleanup
    #########################################################
    def _cleanup_reports(self, summary: MaintenanceSummary) -> None:
        reports_dir = self.runs_dir / _REPORTS_DIR_NAME
        if not reports_dir.exists():
            self.logger.info("Reports directory does not exist: %s", reports_dir)
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.reports_keep_days)
        for path in reports_dir.iterdir():
            if not path.is_file():
                continue
            if path.suffix not in {".json", ".html"}:
                continue

            timestamp = self._parse_report_timestamp(path.name)
            if timestamp is None:
                try:
                    timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                except OSError as exc:
                    self.logger.warning("Failed to stat report %s: %s", path, exc)
                    continue

            if timestamp < cutoff:
                self._record_path_action(
                    summary,
                    kind="report",
                    path=path,
                    reason="report older than REPORTS_KEEP_DAYS",
                    remove_dir=False,
                )

    @staticmethod
    def _parse_report_timestamp(name: str) -> datetime | None:
        try:
            stem = Path(name).stem
            parts = stem.rsplit("_", 2)
            if len(parts) < 3:
                return None
            stamp = f"{parts[-2]}_{parts[-1]}"
            return datetime.strptime(stamp, _REPORT_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    #########################################################
    # Logs Cleanup
    #########################################################
    def _cleanup_logs(self, summary: MaintenanceSummary) -> None:
        if not self.logs_dir.exists():
            self.logger.info("Logs directory does not exist: %s", self.logs_dir)
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.log_retention_days)
        for path in sorted(self.logs_dir.iterdir(), key=lambda candidate: candidate.name):
            if not path.is_file():
                continue
            if path.name == ".gitkeep":
                continue
            if path.name.endswith(_ACTIVE_LOG_SUFFIX):
                # Never delete the currently-active base log files.
                continue
            try:
                timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except OSError as exc:
                self.logger.warning("Failed to stat log file %s: %s", path, exc)
                continue
            if timestamp < cutoff:
                self._record_path_action(
                    summary,
                    kind="log",
                    path=path,
                    reason="rotated log older than LOG_RETENTION_DAYS",
                    remove_dir=False,
                )

    #########################################################
    # Budget Enforcement
    #########################################################
    def _enforce_cache_budget(self, summary: MaintenanceSummary) -> None:
        budget = max(int(self.cache_budget_bytes), 1)

        used_bytes = self._budget_scope_size()
        summary.notes.append(f"cache_budget_bytes={budget}")
        summary.notes.append(f"cache_budget_used_bytes={used_bytes}")
        if used_bytes <= budget:
            return

        overage = used_bytes - budget
        summary.notes.append(f"cache_budget_exceeded_by_bytes={overage}")

        for candidate in self._budget_cleanup_candidates():
            if used_bytes <= budget:
                break
            if not candidate.exists():
                continue
            size_bytes = self._path_size(candidate)
            if size_bytes <= 0:
                continue
            remove_dir = candidate.is_dir() and not candidate.is_symlink()
            self._record_path_action(
                summary,
                kind="cache-budget",
                path=candidate,
                reason="reclaimed during cache budget enforcement",
                remove_dir=remove_dir,
            )
            used_bytes -= size_bytes

        summary.notes.append(f"cache_budget_used_bytes_after_cleanup={max(used_bytes, 0)}")
        if used_bytes > budget:
            summary.notes.append("budget_exceeded_but_protected")

    def _budget_scope_size(self) -> int:
        total = 0
        protected_roots = tuple(self._protected_cache_roots())
        for root in (self.runs_dir.parent, self.external_cache_dir):
            if root.exists():
                total += self._path_size(root, excluded_roots=protected_roots)
        return total

    def _budget_cleanup_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        candidates.extend(self._operator_budget_candidates())
        cache_dir = self.runs_dir.parent / "cache"
        candidates.extend(self._runtime_cache_budget_candidates(cache_dir))
        candidates.extend(self._external_cache_budget_candidates())

        unique: list[Path] = []
        seen: set[Path] = set()
        for path in candidates:
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _operator_budget_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        for rel in ("temp", "smoke", "browser-debug"):
            path = self.operator_dir / rel
            if path.exists():
                candidates.append(path)

        gif_candidates = [
            self.operator_dir / name
            for name in ("gif-frames", "gif-frames-final", "gif-frames-final2", "gif-frames-new")
            if (self.operator_dir / name).is_dir()
        ]
        if len(gif_candidates) > 1:
            latest = max(gif_candidates, key=lambda path: path.stat().st_mtime)
            for path in gif_candidates:
                if path != latest:
                    candidates.append(path)
        return candidates

    @staticmethod
    def _runtime_cache_budget_candidates(cache_dir: Path) -> list[Path]:
        if not cache_dir.exists():
            return []

        candidates: list[Path] = []
        for path in sorted(cache_dir.iterdir(), key=lambda item: item.name):
            if path.name == "state":
                continue
            if path.suffix == ".db" or path.name.endswith("-preview.db"):
                candidates.append(path)
        return candidates

    def _external_cache_budget_candidates(self) -> list[Path]:
        if not self.external_cache_dir.exists():
            return []

        candidates: list[Path] = []
        for rel in ("temp", "smoke", "browser-debug", "staging"):
            path = self.external_cache_dir / rel
            if path.exists():
                candidates.append(path)
        browser_root = self.external_cache_dir / "browser"
        protected_browser_root = self._persistent_browser_profile_root()
        if browser_root.exists():
            for child in sorted(browser_root.iterdir(), key=lambda item: item.name):
                if child == protected_browser_root:
                    continue
                candidates.append(child)
        return candidates

    def _persistent_browser_profile_root(self) -> Path:
        if self.external_cache_dir == DEFAULT_EXTERNAL_CACHE_DIR:
            return DEFAULT_DEDICATED_CHROME_USER_DATA_DIR
        return self.external_cache_dir / "browser" / "chrome-user-data"

    def _protected_cache_roots(self) -> list[Path]:
        protected: list[Path] = []
        browser_root = self._persistent_browser_profile_root()
        if browser_root.exists():
            protected.append(browser_root.resolve())
        return protected

    #########################################################
    # Backups Cleanup
    #########################################################
    def _cleanup_backups(self, summary: MaintenanceSummary) -> None:
        if self.backups_dir is None:
            self.logger.info("Backups directory not configured; skipping.")
            return
        if not self.backups_dir.exists():
            self.logger.info("Backups directory does not exist: %s", self.backups_dir)
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.backups_keep_days)
        for path in self.backups_dir.iterdir():
            if not path.is_file():
                continue
            if path.suffix != ".db":
                continue

            timestamp = self._parse_backup_timestamp(path.name)
            if timestamp is None:
                try:
                    timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                except OSError as exc:
                    self.logger.warning("Failed to stat backup %s: %s", path, exc)
                    continue
            if timestamp < cutoff:
                self._record_path_action(
                    summary,
                    kind="backup",
                    path=path,
                    reason="backup older than BACKUPS_KEEP_DAYS",
                    remove_dir=False,
                )

    @staticmethod
    def _parse_backup_timestamp(name: str) -> datetime | None:
        try:
            stem = Path(name).stem
            parts = stem.rsplit("_", 2)
            if len(parts) < 3:
                return None
            stamp = f"{parts[-2]}_{parts[-1]}"
            return datetime.strptime(stamp, _REPORT_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    #########################################################
    # Database Cleanup
    #########################################################
    async def _cleanup_price_history(self, summary: MaintenanceSummary) -> None:
        if self.repo is None:
            summary.notes.append("legacy price_history cleanup skipped because repo is not configured")
            return
        if self.dry_run:
            summary.notes.append("legacy price_history cleanup skipped during dry-run")
            return
        try:
            deleted = await self.repo.cleanup_price_history(
                older_than_days=self.price_history_keep_days
            )
            summary.legacy_price_history_deleted = deleted
            self.logger.info("Cleaned price_history rows: %s", deleted)
        except Exception as exc:
            self.logger.exception("Cleanup price_history failed: %s", exc)

    async def _vacuum_db(self, summary: MaintenanceSummary) -> None:
        if self.repo is None:
            summary.notes.append("legacy VACUUM skipped because repo is not configured")
            return
        if self.dry_run:
            summary.notes.append("legacy VACUUM skipped during dry-run")
            return
        summary.vacuum_attempted = True
        try:
            await self.repo.vacuum()
            summary.vacuum_completed = True
            self.logger.info("Database VACUUM completed.")
        except Exception as exc:
            self.logger.exception("Database VACUUM failed: %s", exc)

    #########################################################
    # Internal
    #########################################################
    def _record_path_action(
        self,
        summary: MaintenanceSummary,
        *,
        kind: str,
        path: Path,
        reason: str,
        remove_dir: bool,
    ) -> None:
        size_bytes = self._path_size(path)
        applied = False
        if self.dry_run:
            applied = False
        else:
            try:
                if remove_dir:
                    shutil.rmtree(path)
                else:
                    path.unlink()
                applied = True
            except OSError as exc:
                self.logger.exception("Failed to delete %s: %s", path, exc)
                summary.notes.append(f"failed to delete {path}: {exc}")
        summary.actions.append(
            MaintenanceAction(
                kind=kind,
                path=path,
                size_bytes=size_bytes,
                reason=reason,
                applied=applied,
            )
        )

    @staticmethod
    def _path_size(path: Path, *, excluded_roots: tuple[Path, ...] = ()) -> int:
        if not path.exists():
            return 0
        try:
            resolved_path = path.resolve()
        except OSError:
            resolved_path = path
        if any(
            resolved_path == excluded_root or excluded_root in resolved_path.parents
            for excluded_root in excluded_roots
        ):
            return 0
        if path.is_symlink():
            try:
                return path.lstat().st_size
            except OSError:
                return 0
        if path.is_file():
            try:
                return path.stat().st_size
            except OSError:
                return 0

        total = 0
        for child in path.rglob("*"):
            try:
                resolved_child = child.resolve()
            except OSError:
                continue
            if any(
                resolved_child == excluded_root or excluded_root in resolved_child.parents
                for excluded_root in excluded_roots
            ):
                continue
            try:
                mode = child.lstat().st_mode
            except OSError:
                continue
            if stat.S_ISREG(mode):
                try:
                    total += child.lstat().st_size
                except OSError:
                    continue
        return total
