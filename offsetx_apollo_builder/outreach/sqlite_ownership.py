"""Serialize ownership of the legacy shared OutreachStore SQLite connection.

The CRM currently has one long-lived ``sqlite3.Connection`` behind an
``OutreachStore``.  SQLite may be compiled in serialized mode, but a transaction
still belongs to the *connection*, not to a Python thread.  Two threads can
therefore interleave ``BEGIN``/``ROLLBACK`` on the same connection and one
request can undo another request's acknowledged work.

This module gives that connection one explicit owner at a time.  It is installed
at the outreach package boundary before ``OutreachEngine`` is imported, so API,
sales, delivery, automation and direct ``OutreachStore`` users all get the same
rule.  The wrapper deliberately exposes only the sqlite methods the store uses;
it is not a second persistence abstraction.
"""
from __future__ import annotations

import sqlite3
import threading
from functools import wraps
from typing import Any, Iterable


class SerializedCursor:
    """A cursor whose reads cannot race another operation on the connection."""

    def __init__(self, cursor: sqlite3.Cursor, gate: threading.RLock):
        self._cursor = cursor
        self._gate = gate

    def fetchone(self) -> Any:
        with self._gate:
            return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        with self._gate:
            return self._cursor.fetchall()

    def fetchmany(self, size: int | None = None) -> list[Any]:
        with self._gate:
            return self._cursor.fetchmany() if size is None else self._cursor.fetchmany(size)

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                return
            yield row

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class SerializedConnection:
    """One sqlite connection with transaction ownership serialized by thread.

    ``OutreachStore.transaction`` already defines the correct transaction
    boundary.  The defect was that nothing held ownership from its ``BEGIN`` to
    its ``COMMIT``/``ROLLBACK``.  We acquire an ``RLock`` when BEGIN starts and
    release it only when the outer transaction ends.  RLock keeps ordinary store
    helpers usable from inside a transaction.  Nested transactions in the same
    thread are represented as savepoints rather than issuing an illegal nested
    BEGIN.
    """

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection
        self._gate = threading.RLock()
        self._local = threading.local()

    def _depth(self) -> int:
        return int(getattr(self._local, "depth", 0))

    def _savepoints(self) -> list[str]:
        value = getattr(self._local, "savepoints", None)
        if value is None:
            value = []
            self._local.savepoints = value
        return value

    @staticmethod
    def _is_begin(sql: str) -> bool:
        return str(sql).lstrip().upper().startswith("BEGIN")

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> SerializedCursor:
        if self._is_begin(sql):
            depth = self._depth()
            if depth == 0:
                self._gate.acquire()
                try:
                    cursor = self._connection.execute(sql, tuple(parameters))
                except Exception:
                    self._gate.release()
                    raise
                self._local.depth = 1
                return SerializedCursor(cursor, self._gate)
            name = f"offcrm_nested_{threading.get_ident()}_{depth}"
            cursor = self._connection.execute(f"SAVEPOINT {name}")
            self._savepoints().append(name)
            self._local.depth = depth + 1
            return SerializedCursor(cursor, self._gate)
        with self._gate:
            return SerializedCursor(self._connection.execute(sql, tuple(parameters)), self._gate)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]) -> SerializedCursor:
        with self._gate:
            return SerializedCursor(
                self._connection.executemany(sql, seq_of_parameters), self._gate
            )

    def executescript(self, script: str) -> SerializedCursor:
        with self._gate:
            return SerializedCursor(self._connection.executescript(script), self._gate)

    def commit(self) -> None:
        depth = self._depth()
        if depth > 1:
            name = self._savepoints().pop()
            self._connection.execute(f"RELEASE SAVEPOINT {name}")
            self._local.depth = depth - 1
            return
        if depth == 1:
            try:
                self._connection.commit()
            finally:
                self._local.depth = 0
                self._local.savepoints = []
                self._gate.release()
            return
        with self._gate:
            self._connection.commit()

    def rollback(self) -> None:
        depth = self._depth()
        if depth > 1:
            name = self._savepoints().pop()
            try:
                self._connection.execute(f"ROLLBACK TO SAVEPOINT {name}")
            finally:
                self._connection.execute(f"RELEASE SAVEPOINT {name}")
                self._local.depth = depth - 1
            return
        if depth == 1:
            try:
                self._connection.rollback()
            finally:
                self._local.depth = 0
                self._local.savepoints = []
                self._gate.release()
            return
        with self._gate:
            self._connection.rollback()

    def close(self) -> None:
        with self._gate:
            self._connection.close()

    @property
    def raw_connection(self) -> sqlite3.Connection:
        """Trusted maintenance access; callers must already have drained work."""
        return self._connection

    def __getattr__(self, name: str) -> Any:
        # Row factory and harmless connection metadata are read through here.
        # Mutating SQL methods used by OutreachStore are explicitly wrapped above.
        return getattr(self._connection, name)


def harden_outreach_store(store_class: type[Any]) -> None:
    """Install serialized connection ownership exactly once on OutreachStore."""
    if getattr(store_class, "_offcrm_serialized_connection", False):
        return
    original_init = store_class.__init__

    @wraps(original_init)
    def safe_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        if not isinstance(self.connection, SerializedConnection):
            self.connection = SerializedConnection(self.connection)

    store_class.__init__ = safe_init
    store_class._offcrm_serialized_connection = True
