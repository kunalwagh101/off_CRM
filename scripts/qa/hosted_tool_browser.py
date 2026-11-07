"""Real server/browser regression for hosted companion tool grants.

Uses only disposable data. PostgreSQL mode requires a disposable CREATEDB test
role in OFF_CRM_TEST_POSTGRES_URL. Generated credentials are never printed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

from cryptography.fernet import Fernet
import httpx
from playwright.sync_api import expect, sync_playwright


def child_environment(project: Path, data: Path, target: str, token: str, parent=None) -> dict[str, str]:
    """Preserve runtime/proxy trust, never an operator's app configuration."""
    source = os.environ if parent is None else parent
    runtime = {'PATH', 'HOME', 'USER', 'LOGNAME', 'LANG', 'LC_ALL', 'TZ', 'TMPDIR', 'TMP', 'TEMP',
        'VIRTUAL_ENV', 'LD_LIBRARY_PATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE',
        'CURL_CA_BUNDLE', 'NODE_EXTRA_CA_CERTS', 'CODEX_PROXY_CERT', 'SYSTEMROOT', 'WINDIR'}
    proxies = {'http_proxy', 'https_proxy', 'no_proxy', 'all_proxy'}
    env = {key:value for key,value in source.items() if key in runtime or key.lower() in proxies}
    env.update(PYTHONPATH=str(project), PYTHON_DOTENV_DISABLED='1',
        OFF_CRM_QA_PROJECT_ROOT=str(project), OFF_CRM_QA_DATA_ROOT=str(data),
        OFFSETX_DATABASE_URL=target, OFFSETX_OUTREACH_DB=str(data/'crm.db'),
        OFFSETX_SECRETS_KEY=Fernet.generate_key().decode(), OFFSETX_INSTALL_ID=str(uuid.uuid4()),
        OFFSETX_DATA_DIR=str(data), OFFSETX_LOCAL_API_TOKEN=token, OFFSETX_SESSION_SECRET=secrets.token_urlsafe(48),
        OFFSETX_GMAIL_TOKEN='', OFFSETX_GMAIL_CLIENT_SECRETS='', OFFSETX_DEMO_USERNAME='', OFFSETX_DEMO_PASSWORD='',
        OFFSETX_ALLOWED_HOSTS='127.0.0.1,localhost', OFFSETX_PRODUCTION='0', OFFSETX_PUBLIC_DEMO='0')
    return env


def create_disposable_app():
    """Factory with explicit private paths; never read an operator's .env."""
    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings
    project = Path(os.environ['OFF_CRM_QA_PROJECT_ROOT'])
    data = Path(os.environ['OFF_CRM_QA_DATA_ROOT'])
    return create_app(AppSettings(project_root=project, database_path=data/'crm.db', data_dir=data,
        export_dir=data/'exports', frontend_dist=project/'frontend'/'dist',
        host='127.0.0.1', port=int(os.environ['OFF_CRM_QA_PORT']),
        api_token=os.environ['OFFSETX_LOCAL_API_TOKEN'], secrets_key=os.environ['OFFSETX_SECRETS_KEY'],
        session_secret=os.environ['OFFSETX_SESSION_SECRET'], allowed_hosts=('127.0.0.1', 'localhost')))


def run(backend: str, artifacts: Path) -> dict:
    project = Path(__file__).resolve().parents[2]
    browser_executable = (os.getenv('OFF_CRM_QA_CHROMIUM') or shutil.which('chromium')
        or shutil.which('google-chrome') or shutil.which('chromium-browser'))
    if not browser_executable:
        raise SystemExit('Install Chromium/Google Chrome or set OFF_CRM_QA_CHROMIUM to its executable')
    if not (project/'frontend'/'dist'/'index.html').is_file():
        raise SystemExit('Build frontend/dist with npm run build before browser QA')
    base = os.getenv('OFF_CRM_TEST_POSTGRES_URL', '')
    if backend == 'postgres' and not base:
        raise SystemExit('PostgreSQL QA requires a disposable OFF_CRM_TEST_POSTGRES_URL with CREATEDB')
    artifacts = artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = Path(tempfile.mkdtemp(prefix='offcrm-hosted-tools-ui-'))
    data = temporary/'data'
    database = 'offcrm_browser_tools_'+uuid.uuid4().hex
    target = str(temporary/'hosted.db')
    if backend == 'postgres':
        target = urlunsplit(urlsplit(base)._replace(path='/'+database))
    token = secrets.token_urlsafe(48)
    env = child_environment(project, data, target, token)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    env['OFF_CRM_QA_PORT'] = str(port)
    url = 'http://127.0.0.1:'+str(port)
    process = None
    created = False
    log = (artifacts/'server.log').open('w')

    def stop_server():
        nonlocal process
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process = None

    def cli(*arguments):
        result = subprocess.run([sys.executable, '-m', 'offsetx_apollo_builder.ai.tool_cli',
            '--data-dir', str(data), *arguments], cwd=temporary, env=env,
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, 'tool CLI failed; inspect the private runtime diagnostics'

    def start_server(client):
        nonlocal process
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn',
            'scripts.qa.hosted_tool_browser:create_disposable_app', '--factory', '--host', '127.0.0.1',
            '--port', str(port), '--no-access-log'], cwd=temporary, env=env, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic()+30
        while True:
            try:
                if client.get('/health/live').status_code == 200:
                    break
            except httpx.TransportError:
                pass
            assert process.poll() is None, 'actual server failed; inspect server.log'
            assert time.monotonic() < deadline, 'actual server failed to become live'
            time.sleep(.1)
        assert not (data/'ai_tools.db').exists(), 'hosted runtime created a local tool registry'

    try:
        if backend == 'postgres':
            import psycopg
            from psycopg import sql
            with psycopg.connect(base, autocommit=True) as admin:
                admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
            created = True
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=project, text=True).strip()
        cli('register', '--name', 'hosted-browser-proof', '--repo',
            'https://github.com/kunalwagh101/off_CRM', '--commit', revision,
            '--image', 'python:3.12-slim', '--', 'python', '--version')
        with httpx.Client(base_url=url, headers={'X-Offsetx-Token':token}, timeout=5) as client:
            start_server(client)
            with sync_playwright() as automation:
                with automation.chromium.launch(executable_path=browser_executable,
                        headless=True, args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
                    page = browser.new_page(extra_http_headers={'X-Offsetx-Token':token},
                        viewport={'width':1280, 'height':900})
                    page.route('**/*', lambda route: route.continue_()
                        if route.request.url.startswith(url+'/') else route.abort())
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(url+'/#agentteam')
                    page.get_by_role('heading', name='Agent team', exact=True).wait_for()
                    page.get_by_label('Profile name', exact=True).fill('Hosted browser QA')
                    page.get_by_label('Profile instructions', exact=True).fill('Review public facts only.')
                    page.get_by_role('button', name='Create companion', exact=True).click()
                    page.get_by_label('Edit profile name', exact=True).wait_for()
                    page.get_by_role('checkbox', name='hosted-browser-proof', exact=True).check()
                    page.get_by_role('button', name='Save profile', exact=True).click()
                    page.get_by_role('status').filter(has_text='Profile updated').wait_for()
                    profile = next(item for item in client.get('/api/v1/companions').json()['items']
                        if item['name'] == 'Hosted browser QA')
                    assert len(profile['granted_tool_ids']) == 1
                    stop_server()
                    shutil.rmtree(data)
                    start_server(client)
                    page.reload()
                    page.get_by_label('Companion', exact=True).select_option(profile['id'])
                    expect(page.get_by_role('checkbox', name='hosted-browser-proof', exact=True)).to_be_checked()
                    page.screenshot(path=str(artifacts/'desktop-saved.png'), full_page=True)
                    cli('remove', 'hosted-browser-proof')
                    assert client.get('/api/v1/companion-tools').json()['items'] == []
                    page.reload()
                    page.get_by_label('Companion', exact=True).select_option(profile['id'])
                    page.get_by_label('Edit profile name', exact=True).wait_for()
                    unavailable = page.get_by_role('checkbox', name=re.compile('Unavailable saved tool'))
                    expect(unavailable).to_have_count(1)
                    expect(unavailable).to_be_checked()
                    page.screenshot(path=str(artifacts/'desktop-unavailable.png'), full_page=True)
                    page.set_viewport_size({'width':390, 'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    page.get_by_text('Granted registered tools', exact=True).locator('..').screenshot(
                        path=str(artifacts/'mobile-grants.png'))
                    unavailable.uncheck()
                    expect(unavailable).to_be_visible()
                    expect(unavailable).not_to_be_checked()
                    unavailable.check()
                    expect(unavailable).to_be_checked()
                    unavailable.uncheck()
                    assert client.get('/api/v1/companions/'+profile['id']).json()['granted_tool_ids'] == profile['granted_tool_ids']
                    page.get_by_role('button', name='Save profile', exact=True).click()
                    page.get_by_role('status').filter(has_text='Profile updated').wait_for()
                    assert client.get('/api/v1/companions/'+profile['id']).json()['granted_tool_ids'] == []
                    page.screenshot(path=str(artifacts/'mobile-cleared.png'), full_page=True)
                    assert not errors, 'browser JavaScript errors occurred'
        return {'actual_server':True, 'backend':backend, 'browser':'Chromium', 'desktop':1280, 'mobile':390,
            'process_and_folder_loss_recovered':True, 'grant_saved_and_reloaded':True,
            'removed_grant_cleared':True, 'javascript_errors':0}
    finally:
        stop_server()
        log.close()
        try:
            if created:
                import psycopg
                from psycopg import sql
                with psycopg.connect(base, autocommit=True) as admin:
                    admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
        finally:
            shutil.rmtree(temporary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=('sqlite', 'postgres'), default='sqlite')
    parser.add_argument('--artifacts', type=Path, default=Path('work/qa-hosted-tools'))
    args = parser.parse_args()
    print(json.dumps(run(args.backend, args.artifacts)))
