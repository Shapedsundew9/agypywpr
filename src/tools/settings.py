"""Transactional Antigravity settings updates."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import TracebackType
from typing import Any

from .permissions import augment_permissions


class SettingsError(RuntimeError):
    """Raised when settings cannot be safely updated or restored."""


class SettingsTransaction:
    """Temporarily augment settings and restore their original bytes on exit."""

    def __init__(self, path: Path, additions: dict[str, list[str]]) -> None:
        self.path = path.expanduser()
        self.additions = additions
        self.lock_path = self.path.with_name(f".{self.path.name}.agypywpr.lock")
        self.journal_path = self.path.with_name(f".{self.path.name}.agypywpr-journal")
        self._lock_file: Any = None
        self._original: bytes | None = None
        self._temporary: bytes | None = None

    def __enter__(self) -> "SettingsTransaction":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.journal_path.exists():
            raise SettingsError(f"recovery journal exists: {self.journal_path}")
        try:
            self._lock_file = self.lock_path.open("x", encoding="ascii")
        except FileExistsError as error:
            raise SettingsError(f"settings are already locked: {self.path}") from error
        try:
            existed = self.path.exists()
            self._original = self.path.read_bytes() if existed else None
            settings = json.loads(self._original or b"{}")
            updated = augment_permissions(settings, self.additions)
            self.journal_path.write_text(
                json.dumps({"existed": existed, "original": self._original.decode("utf-8") if self._original else None}),
                encoding="utf-8",
            )
            self.journal_path.chmod(0o600)
            self._atomic_write(updated)
            self._temporary = self.path.read_bytes()
            return self
        except Exception:
            self._cleanup_lock()
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.restore()
        finally:
            self._cleanup_lock()

    def restore(self) -> None:
        """Restore the exact bytes present before the transaction."""
        if self.path.exists() and self._temporary is not None:
            current = self.path.read_bytes()
            if current != self._temporary:
                raise SettingsError(
                    "settings changed during the run; use agypywpr restore after review"
                )
        if self._original is None:
            if self.path.exists():
                self.path.unlink()
        else:
            self._atomic_write_bytes(self._original)
        if self.journal_path.exists():
            self.journal_path.unlink()

    def _atomic_write(self, settings: dict[str, Any]) -> None:
        payload = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
        self._atomic_write_bytes(payload.encode("utf-8"))

    def _atomic_write_bytes(self, payload: bytes) -> None:
        mode = self.path.stat().st_mode & 0o777 if self.path.exists() else 0o600
        descriptor, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=f".{self.path.name}.")
        try:
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _cleanup_lock(self) -> None:
        if self._lock_file is not None:
            self._lock_file.close()
            self._lock_file = None
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass


def restore_from_journal(path: Path) -> None:
    """Restore a settings file from a durable interrupted-run journal."""
    path = path.expanduser()
    journal_path = path.with_name(f".{path.name}.agypywpr-journal")
    if not journal_path.exists():
        raise SettingsError(f"no recovery journal exists: {journal_path}")
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        original = journal["original"]
        existed = journal["existed"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SettingsError(f"invalid recovery journal: {journal_path}") from error
    if existed:
        if not isinstance(original, str):
            raise SettingsError("recovery journal does not contain original settings")
        payload = original.encode("utf-8")
        mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
        descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            os.fchmod(descriptor, mode)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    elif path.exists():
        path.unlink()
    journal_path.unlink()