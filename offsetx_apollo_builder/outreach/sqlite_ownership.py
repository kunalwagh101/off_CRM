"""One ownership guard for every operation on the CRM SQLite connection."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager


class SerializedCursor(sqlite3.Cursor):
    def execute(self, sql, parameters=()):
        with self.connection.guard:
            return super().execute(sql, parameters)

    def executemany(self, sql, parameters):
        with self.connection.guard:
            return super().executemany(sql, parameters)

    def executescript(self, script):
        with self.connection.guard:
            if self.connection.in_transaction:
                raise sqlite3.ProgrammingError("A script cannot implicitly commit an owned transaction")
            return super().executescript(script)

    def fetchone(self):
        with self.connection.guard:
            return super().fetchone()

    def fetchmany(self, size=None):
        with self.connection.guard:
            return super().fetchmany() if size is None else super().fetchmany(size)

    def fetchall(self):
        with self.connection.guard:
            return super().fetchall()

    def __next__(self):
        with self.connection.guard:
            return super().__next__()

    def close(self):
        with self.connection.guard:
            return super().close()


class SerializedConnection(sqlite3.Connection):
    """Bare statements autocommit; explicit transactions own the same guard.

    This is a native SQLite connection, so SQLite's backup API and named SQL
    bindings retain their normal semantics. There is no import-time patching.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guard = threading.RLock()
        self._savepoint = 0

    def cursor(self, factory=SerializedCursor):
        if factory is not SerializedCursor:
            raise ValueError("CRM cursors must use the connection ownership guard")
        with self.guard:
            return super().cursor(factory)

    def execute(self, sql, parameters=()):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql, parameters):
        return self.cursor().executemany(sql, parameters)

    def executescript(self, script):
        return self.cursor().executescript(script)

    @contextmanager
    def transaction(self, *, immediate=False):
        with self.guard:
            nested = self.in_transaction
            self._savepoint += 1
            name = f"offcrm_{self._savepoint}"
            self.execute(f"SAVEPOINT {name}" if nested else "BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield self
                self.execute(f"RELEASE SAVEPOINT {name}" if nested else "COMMIT")
            except BaseException:
                if self.in_transaction:
                    self.execute(f"ROLLBACK TO SAVEPOINT {name}" if nested else "ROLLBACK")
                    if nested:
                        self.execute(f"RELEASE SAVEPOINT {name}")
                raise

    def commit(self):
        with self.guard:
            return super().commit()

    def rollback(self):
        with self.guard:
            return super().rollback()

    def backup(self, target, **kwargs):
        with self.guard:
            return super().backup(target, **kwargs)

    def close(self):
        with self.guard:
            return super().close()
