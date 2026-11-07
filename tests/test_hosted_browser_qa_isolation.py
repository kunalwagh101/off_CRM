"""A reproducible QA command must never inherit customer stores or credentials."""
from pathlib import Path
from dotenv import load_dotenv
from scripts.qa.hosted_tool_browser import child_environment, create_disposable_app


def test_browser_qa_child_preserves_runtime_trust_and_discards_operator_configuration(tmp_path, monkeypatch):
    parent = {'HOME':'/operator', 'PATH':'/runtime/bin', 'HTTP_PROXY':'http://session-proxy:8080',
        'SSL_CERT_FILE':'/runtime/trusted-ca.pem', 'OFFSETX_OUTREACH_DB':'/operator/customer.db',
        'OFFSETX_GMAIL_TOKEN':'/operator/mail.json', 'OFFSETX_SESSION_SECRET':'PARENT_SESSION_CANARY',
        'OPENAI_API_KEY':'PARENT_PROVIDER_CANARY', 'AWS_SECRET_ACCESS_KEY':'PARENT_STORAGE_CANARY', 'PORT':'99'}
    data, project = tmp_path/'private'/'data', Path(__file__).resolve().parents[1]
    child = child_environment(project, data, str(tmp_path/'private'/'hosted.db'), 'test-token-'+'x'*40, parent)
    assert child['HOME'] == parent['HOME'] and child['HTTP_PROXY'] == parent['HTTP_PROXY']
    assert child['SSL_CERT_FILE'] == parent['SSL_CERT_FILE']
    assert child['OFFSETX_OUTREACH_DB'] == str(data/'crm.db')
    assert child['OFFSETX_GMAIL_TOKEN'] == '' and child['OFFSETX_GMAIL_CLIENT_SECRETS'] == ''
    assert 'PORT' not in child and 'OPENAI_API_KEY' not in child and 'AWS_SECRET_ACCESS_KEY' not in child
    assert not any('PARENT_' in value for value in child.values())
    assert child['PYTHON_DOTENV_DISABLED'] == '1'
    poison = tmp_path/'operator.env'
    poison.write_text('OFFSETX_OUTREACH_DB=/operator/customer.db\nOFFSETX_UNRELATED_TRAP=private\n')
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', child['PYTHON_DOTENV_DISABLED'])
    monkeypatch.setenv('OFFSETX_OUTREACH_DB', child['OFFSETX_OUTREACH_DB'])
    monkeypatch.delenv('OFFSETX_UNRELATED_TRAP', raising=False)
    assert load_dotenv(poison) is False
    import os
    assert os.environ['OFFSETX_OUTREACH_DB'] == str(data/'crm.db')
    assert 'OFFSETX_UNRELATED_TRAP' not in os.environ


def test_browser_qa_factory_binds_paths_without_reading_operator_env(tmp_path, monkeypatch):
    import offsetx_apollo_builder.api.app as application
    data, project = tmp_path/'private'/'data', Path(__file__).resolve().parents[1]
    child = child_environment(project, data, str(tmp_path/'hosted.db'), 'test-token-'+'x'*40, {})
    for key, value in child.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv('OFF_CRM_QA_PORT', '12345')
    monkeypatch.setenv('OFFSETX_OUTREACH_DB', '/operator/customer.db')
    monkeypatch.setenv('OFFSETX_GMAIL_TOKEN', '/operator/mail.json')
    monkeypatch.setattr(application, 'create_app', lambda settings: settings)
    settings = create_disposable_app()
    assert settings.database_path == data/'crm.db' and settings.data_dir == data
    assert settings.export_dir == data/'exports'
    assert settings.gmail_client_secrets is None and settings.gmail_token is None
    assert settings.frontend_dist == project/'frontend'/'dist' and settings.port == 12345
