"""Fresh scoped SQL connections for stores with explicit claim transactions."""
from __future__ import annotations
from typing import Any
from .connection import open_database

# Serialize short read/modify/write claims across application processes. Each
# connection has a five-second lock limit; no network action runs in this scope.
STORE_CLAIM_LOCK = 7_103_206_304


class StoreConnection:
    def __init__(self, target: str):
        self.database = open_database(target)
        self._transaction: Any = None

    def _begin(self):
        if self._transaction is not None:
            raise RuntimeError('A store transaction is already active')
        scope = self.database.transaction()
        scope.__enter__()
        self._transaction = scope
        try:
            if self.database.name == 'postgres':
                self.database.execute("SET LOCAL lock_timeout = '5s'")
                self.database.execute('SELECT pg_advisory_xact_lock(?)', [STORE_CLAIM_LOCK])
        except BaseException:
            self.rollback()
            raise

    def execute(self, statement: str, parameters=()):
        command = statement.strip().upper()
        if command == 'BEGIN IMMEDIATE':
            self._begin()
            return None
        if command == 'COMMIT':
            self.commit()
            return None
        if command == 'ROLLBACK':
            self.rollback()
            return None
        return self.database.execute(statement, parameters)

    def commit(self):
        scope, self._transaction = self._transaction, None
        if scope is not None:
            scope.__exit__(None, None, None)

    def rollback(self):
        scope, self._transaction = self._transaction, None
        if scope is not None:
            aborted = RuntimeError('Store transaction rolled back')
            scope.__exit__(RuntimeError, aborted, None)

    def close(self):
        try:
            self.rollback()
        finally:
            self.database.close()

    def __enter__(self):
        try:
            self._begin()
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, kind, value, traceback):
        try:
            scope, self._transaction = self._transaction, None
            return scope.__exit__(kind, value, traceback) if scope is not None else False
        finally:
            self.database.close()


class CachedStoreConnection(StoreConnection):
    """Thread-owned store transport whose contexts commit without closing it.

    ToolRegistry owns every cached transport and closes them together during
    runtime replacement. A context still owns an actual database transaction;
    direct readiness reads use the database's normal standalone statement path.
    """

    def __exit__(self, kind, value, traceback):
        scope, self._transaction = self._transaction, None
        return scope.__exit__(kind, value, traceback) if scope is not None else False
