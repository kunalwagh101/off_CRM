"""Start a disposable loopback-only transaction pooler on the CI runner.

Uses the PostgreSQL service's published test credential, never a customer URL.
The single backend plus forced session reset exercises routing without affinity.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import psycopg


def main():
    executable = shutil.which('pgbouncer')
    if not executable:
        raise RuntimeError('Install the CI PgBouncer package before the pooler acceptance step')
    root = Path(tempfile.mkdtemp(prefix='offcrm-ci-pooler-'))
    auth = root / 'users.txt'
    auth.write_text('"postgres" "ci-only-password"\n')
    auth.chmod(0o600)
    config = root / 'pgbouncer.ini'
    config.write_text(f'''[databases]
* = host=127.0.0.1 port=5432 user=postgres password=ci-only-password
[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6543
auth_type = trust
auth_file = {auth}
admin_users = postgres
pool_mode = transaction
default_pool_size = 1
max_client_conn = 60
server_reset_query = DISCARD ALL
server_reset_query_always = 1
logfile = {root / 'pooler.log'}
pidfile = {root / 'pooler.pid'}
''')
    config.chmod(0o600)
    subprocess.run([executable, '-d', str(config)], check=True, capture_output=True)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with psycopg.connect('postgresql://postgres:ci-only-password@127.0.0.1:6543/pgbouncer', autocommit=True, connect_timeout=1, cursor_factory=psycopg.ClientCursor) as connection:
                version = connection.execute('SHOW VERSION').fetchone()[0]
                if 'PgBouncer' not in version:
                    raise RuntimeError('The acceptance endpoint is not PgBouncer')
            print(f'Disposable {version} ready: transaction mode, one backend, forced session reset')
            return
        except psycopg.OperationalError:
            time.sleep(0.25)
    raise RuntimeError('The disposable CI pooler did not become ready on loopback')


if __name__ == '__main__':
    main()
