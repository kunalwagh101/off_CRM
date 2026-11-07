"""Opt-in real Docker boundary and hosted tool-receipt acceptance.

Pull the official image explicitly before running; the product sandbox itself
uses --pull=never and --network=none. No live provider or customer data is used.
"""
import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest

from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.ai.sandbox import SandboxWorkspace
from offsetx_apollo_builder.ai.sandbox import SandboxPolicy

pytestmark = pytest.mark.skipif(os.getenv('OFF_CRM_TEST_REAL_TOOLS') != '1',
    reason='requires explicitly provisioned real Docker daemon and public pinned image')

PROBE = '''import os,json
from pathlib import Path
def denied(path):
    try: Path(path).write_text("public probe")
    except OSError: return True
    return False
Path("/work/public-result").write_text("ok")
status=Path("/proc/self/status").read_text()
print(json.dumps({"uid":os.getuid(),"interfaces":os.listdir("/sys/class/net"),
"root_readonly":bool(os.statvfs("/").f_flag & os.ST_RDONLY),
"root_denied":denied("/root-write"),"inbox_denied":denied("/inbox/write"),
"store_absent":not Path("/store").exists(),"socket_absent":not Path("/var/run/docker.sock").exists(),
"privilege_limits":"CapEff:\\t0000000000000000" in status and "NoNewPrivs:\\t1" in status,
"no_app_secrets":not any(key in os.environ for key in ("OFFSETX_SECRETS_KEY","OFF_CRM_TEST_POSTGRES_URL"))}))
'''


@pytest.mark.parametrize('backend', ['sqlite', 'postgres'])
def test_actual_pinned_tool_has_no_network_or_private_mount_and_persists_receipt(tmp_path, monkeypatch, request, backend):
    for key in ('DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH', 'RENDER'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('DOCKER_HOST', 'unix:///var/run/docker.sock')
    monkeypatch.setenv('OFFSETX_SANDBOX_ALLOW_NESTED', '1')
    target = str(tmp_path/'durable.db') if backend == 'sqlite' else request.getfixturevalue('isolated_postgres_target')
    digest = subprocess.check_output(['docker', 'image', 'inspect', 'python:3.12-slim',
        '--format', '{{index .RepoDigests 0}}'], text=True).strip()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert len(PROBE) <= 1000
    registry = ToolRegistry(tmp_path/'ephemeral'/'ai_tools.db', database_target=target)
    workspace = SandboxWorkspace(root=tmp_path/'sandbox').prepare()
    workspace.store.mkdir(mode=0o700)
    (workspace.store/'private-canary').write_text('public test canary; must stay on host')
    try:
        tool = registry.register(name='boundary-probe', repository_url='https://github.com/kunalwagh101/off_CRM',
            commit_sha=revision, image=digest, command=['python', '-c', PROBE], workspace_id='alpha')
        run = registry.run(tool.id, workspace=workspace, workspace_id='alpha', timeout_seconds=30)
        assert run.ok, run.stderr
        result = json.loads(run.stdout)
        assert result == {'uid':65534, 'interfaces':['lo'], 'root_readonly':True,
            'root_denied':True, 'inbox_denied':True, 'store_absent':True, 'socket_absent':True,
            'privilege_limits':True, 'no_app_secrets':True}
        assert (workspace.work/'public-result').read_text() == 'ok'
        landed = subprocess.check_output(['git', '-C', str(workspace.inbox/'source'), 'rev-parse', 'HEAD'], text=True).strip()
        assert landed == revision
    finally:
        registry.close()
    reopened = ToolRegistry(tmp_path/'ephemeral'/'ai_tools.db', database_target=target)
    try:
        assert reopened.runs(workspace_id='alpha')[0]['id'] == run.id
        assert reopened.runs(workspace_id='beta') == []
        with reopened.connection() as database:
            row = database.execute('SELECT stdout FROM ai_tool_runs WHERE id=?', [run.id]).fetchone()
            assert json.loads(row['stdout']) == result
    finally:
        reopened.close()


def test_timed_out_tool_does_not_leave_its_actual_container_running(tmp_path, monkeypatch):
    for key in ('DOCKER_CONTEXT', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH', 'RENDER'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('DOCKER_HOST', 'unix:///var/run/docker.sock')
    monkeypatch.setenv('OFFSETX_SANDBOX_ALLOW_NESTED', '1')
    label = 'offcrm-timeout-test-'+uuid.uuid4().hex
    class LabeledPolicy(SandboxPolicy):
        def docker_command(self, **kwargs):
            command = super().docker_command(**kwargs)
            return command[:2]+['--label=codex.task='+label]+command[2:]
    registry = ToolRegistry(tmp_path/'ephemeral'/'ai_tools.db', database_target=str(tmp_path/'durable.db'))
    try:
        digest = subprocess.check_output(['docker', 'image', 'inspect', 'python:3.12-slim',
            '--format', '{{index .RepoDigests 0}}'], text=True).strip()
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        tool = registry.register(name='timeout-probe', repository_url='https://github.com/kunalwagh101/off_CRM',
            commit_sha=revision, image=digest, command=['python', '-c',
                'import time;from pathlib import Path;Path("/work/started").write_text("yes");time.sleep(30)'])
        workspace = SandboxWorkspace(root=tmp_path/'sandbox')
        run = registry.run(tool.id, workspace=workspace,
            timeout_seconds=10, fetch_source=False, policy=LabeledPolicy())
        assert run.status == 'timeout'
        assert (workspace.work/'started').read_text() == 'yes', 'the fixture must enter the running container before timeout'
        live = subprocess.check_output(['docker', 'ps', '-q', '--filter', 'label=codex.task='+label], text=True).strip()
        assert not live, 'a timeout must stop the container, not only the attached Docker client'
        assert registry.runs()[0]['status'] == 'timeout'
    finally:
        owned = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'label=codex.task='+label], text=True).split()
        if owned:
            subprocess.run(['docker', 'rm', '-f', '-v', *owned], check=True, capture_output=True)
        registry.close()
