"""D-314: a CRM SELECT must own the read lock through cursor materialisation.

GuardedConnection.execute() serialises *issuing* a SQLite statement. Returning
its live cursor and fetching from a different thread after the guard releases
must not be allowed to corrupt a successful campaign-create response.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from offsetx_apollo_builder.outreach.engine import OutreachEngine


def test_campaign_read_holds_connection_lock_until_fetchone_returns(tmp_path):
    engine = OutreachEngine(tmp_path / "crm.sqlite3")
    original = engine.store.connection
    campaign_id = engine.create_campaign(name="Read-lock contract")
    fetching = Event()
    release = Event()

    class DelayedCursor:
        def __init__(self, cursor):
            self.cursor = cursor

        def fetchone(self):
            fetching.set()
            assert release.wait(5), "The read-lock test did not release the cursor"
            return self.cursor.fetchone()

    class ControlledConnection:
        def execute(self, query, parameters=()):
            cursor = original.execute(query, parameters)
            if query == "SELECT * FROM campaigns WHERE id = ?":
                return DelayedCursor(cursor)
            return cursor

        def __getattr__(self, name):
            return getattr(original, name)

    engine.store.connection = ControlledConnection()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(engine.store.get_campaign, campaign_id)
            assert fetching.wait(5), "Campaign SELECT never reached fetchone"
            stole_lock = engine.store._write_lock.acquire(blocking=False)
            if stole_lock:
                engine.store._write_lock.release()
            release.set()
            assert future.result(timeout=5)["id"] == campaign_id
            assert not stole_lock, (
                "A second thread acquired the shared SQLite lock while the "
                "first thread was still fetching the campaign row"
            )
    finally:
        release.set()
        engine.store.connection = original
        engine.close()
