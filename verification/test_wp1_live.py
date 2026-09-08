"""WP1 browser and real production-container acceptance; no provider calls."""
import hashlib
import json
import os
import secrets
import subprocess
import time

import requests
from playwright.sync_api import expect

from test_live import EVIDENCE, app_server, chrome, page  # noqa: F401  (shared real-browser fixtures)

PASSPHRASE = 'synthetic-recovery-test-passphrase'


def test_browser_can_download_and_restore_the_complete_workspace(page, tmp_path):
    with app_server(tmp_path, evidence_name='wp1-browser-server.log') as (url, _):
        original = requests.post(url + '/api/v1/campaigns', json={'name': 'Retained customer campaign'}, timeout=10).json()['id']
        page.goto(url + '/#settings')
        panel = page.locator('section').filter(has=page.get_by_role('heading', name='Encrypted backup', exact=True))
        panel.get_by_label('Backup passphrase', exact=True).first.fill(PASSPHRASE)
        with page.expect_download() as event:
            panel.get_by_role('button', name='Create encrypted backup', exact=True).click()
        archive = EVIDENCE / 'wp1-browser.oxbackup'
        event.value.save_as(archive)
        expect(page.get_by_text('Encrypted workspace backup created', exact=True)).to_be_visible()
        expect(panel.get_by_label('Backup passphrase', exact=True).first).to_have_value('')
        requests.post(url + '/api/v1/campaigns', json={'name': 'After backup'}, timeout=10).raise_for_status()
        panel.get_by_label('Backup file', exact=True).set_input_files(str(archive))
        panel.get_by_label('Backup passphrase', exact=True).last.fill(PASSPHRASE)
        page.on('dialog', lambda dialog: dialog.accept())
        with page.expect_response(lambda response: response.url.endswith('/backups/restore') and response.request.method == 'POST') as restoration:
            panel.get_by_role('button', name='Restore backup', exact=True).click()
        assert restoration.value.status == 200, restoration.value.text()
        page.wait_for_timeout(1000)  # UI announces success, then reloads after 700ms.
        expect(page.get_by_role('heading', name='Encrypted backup', exact=True)).to_be_visible()
        assert requests.get(url + '/health/ready', timeout=5).status_code == 200
        campaigns = requests.get(url + '/api/v1/campaigns', timeout=10).json()['items']
        assert [campaign['id'] for campaign in campaigns] == [original]
        for endpoint in ('/sales/dashboard', '/ai/chats', '/email-delivery/jobs'):
            assert requests.get(url + '/api/v1' + endpoint, timeout=10).status_code == 200
        (EVIDENCE / 'wp1-browser-summary.json').write_text(json.dumps({'restored_campaign': original, 'archive_bytes': archive.stat().st_size, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'readiness': 'ready'}, indent=2))


def test_production_container_survives_kill_recreate_and_restore(tmp_path):
    name = 'offcrm-wp1-' + secrets.token_hex(5)
    volume = name + '-data'
    token = 'synthetic-production-acceptance-token-' + secrets.token_hex(16)
    env = dict(os.environ, OFFSETX_LOCAL_API_TOKEN=token)
    def docker(*args, check=True):
        return subprocess.run(['docker', *args], check=check, capture_output=True, text=True, timeout=90, env=env)
    headers = {'Authorization': 'Bearer ' + token}
    def start():
        docker('run', '-d', '--name', name, '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m', '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--cap-add', 'SETUID', '--cap-add', 'SETGID', '--security-opt', 'no-new-privileges', '-p', '127.0.0.1::8766', '-v', volume + ':/var/lib/offcrm', '-e', 'OFFSETX_PRODUCTION=1', '-e', 'OFFSETX_PERSISTENT_MOUNT=/var/lib/offcrm', '-e', 'OFFSETX_LOCAL_API_TOKEN', 'offcrm-wp1:acceptance')
        port = docker('port', name, '8766/tcp').stdout.strip().split(':')[-1]
        url = 'http://127.0.0.1:' + port
        until = time.monotonic() + 45
        while time.monotonic() < until:
            try:
                if requests.get(url + '/health/ready', timeout=1).status_code == 200:
                    return url
            except requests.RequestException:
                pass
            time.sleep(.2)
        raise AssertionError('Production container did not become ready: ' + docker('logs', name).stdout)
    try:
        docker('volume', 'create', volume)
        url = start()
        status = docker('exec', '--user', '10001:10001', name, 'python', '-c', "print(open('/proc/1/status').read())").stdout
        assert 'Uid:\t10001\t10001\t10001\t10001' in status
        assert 'CapEff:\t0000000000000000' in status
        created = requests.post(url + '/api/v1/campaigns', headers=headers, json={'name': 'Survives container replacement'}, timeout=10)
        assert created.status_code == 201, created.text
        cid = created.json()['id']
        docker('exec', '--user', '10001:10001', name, 'python', '-c', "from pathlib import Path; p=Path('/var/lib/offcrm/local_data/video_renders/durable.bin'); p.write_bytes(b'production-volume-asset')")
        archive = requests.post(url + '/api/v1/backups/export', headers=headers, json={'passphrase': PASSPHRASE}, timeout=30)
        assert archive.status_code == 200, archive.text
        docker('kill', name)
        docker('rm', name)
        url = start()
        assert requests.get(url + '/api/v1/campaigns', headers=headers, timeout=10).json()['items'][0]['id'] == cid
        assert docker('exec', '--user', '10001:10001', name, 'python', '-c', "from pathlib import Path; assert Path('/var/lib/offcrm/local_data/video_renders/durable.bin').read_bytes()==b'production-volume-asset'").returncode == 0
        requests.post(url + '/api/v1/campaigns', headers=headers, json={'name': 'Discard on restore'}, timeout=10).raise_for_status()
        restored = requests.post(url + '/api/v1/backups/restore', headers=headers, files={'file': ('workspace.oxbackup', archive.content)}, data={'passphrase': PASSPHRASE}, timeout=30)
        assert restored.status_code == 200, restored.text
        assert requests.get(url + '/api/v1/campaigns', headers=headers, timeout=10).json()['total'] == 1
        assert requests.get(url + '/health/ready', timeout=5).status_code == 200
        (EVIDENCE / 'wp1-container.json').write_text(json.dumps({'persistent_volume': True, 'kill_and_recreate': True, 'restored': restored.json(), 'uid': 10001, 'effective_capabilities': 0, 'root_readonly': True, 'campaign_id': cid}, indent=2))
    finally:
        logs = docker('logs', name, check=False)
        (EVIDENCE / 'wp1-container.log').write_text(logs.stdout + logs.stderr)
        docker('rm', '-f', name, check=False)
        docker('volume', 'rm', volume, check=False)
