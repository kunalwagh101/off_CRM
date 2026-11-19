"""An app's workspace identity is fixed before authentication and request handling."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.workspaces import workspace_env

API='/api/v1'


def settings(root, workspace, **kwargs):
    return AppSettings(project_root=root, database_path=root/'crm.db', data_dir=root/'data',
        export_dir=root/'exports', frontend_dist=root/'dist', workspace_id=workspace,
        api_token=(workspace+'-')*32, allowed_hosts=("testserver",), **kwargs)


def test_two_apps_share_no_settings_keys_database_or_generated_auth(tmp_path):
    alice, bob = create_app(settings(tmp_path,'alice')), create_app(settings(tmp_path,'bob'))
    with TestClient(alice) as left, TestClient(bob) as right:
        a={'x-offsetx-token':settings(tmp_path,'alice').api_token}
        b={'x-offsetx-token':settings(tmp_path,'bob').api_token}
        assert left.get(API+'/workspace',headers=a).json()['workspace_id']=='alice'
        assert right.get(API+'/workspace',headers=b).json()['workspace_id']=='bob'
        assert left.get(API+'/workspace',headers=b).status_code==401
        assert right.get(API+'/workspace',headers=a).status_code==401
        assert alice.state.settings.data_dir != bob.state.settings.data_dir
        assert alice.state.settings.database_path != bob.state.settings.database_path
        assert left.post(API+'/ai/providers/openai/connect',headers=a,json={'api_key':'ALICE-KEY'}).status_code==200
        assert bob.state.ai_workspaces.key_for('bob','openai')==''
        assert alice.state.ai_workspaces.key_for('alice','openai')=='ALICE-KEY'
        assert right.get(API+'/ai/providers',headers=b).json()['workspace_id']=='bob'
        assert left.post(API+'/ai/workspace',headers=a,json={'positioning_line':'ALICE POSITION'}).status_code==200
        assert right.get(API+'/ai/providers',headers=b).json()['positioning_line']==''


def test_workspace_spoofing_headers_queries_and_body_never_select_identity(tmp_path):
    app=create_app(settings(tmp_path,'alice'))
    with TestClient(app) as client:
        headers={'x-offsetx-token':settings(tmp_path,'alice').api_token,'x-workspace-id':'bob','x-offsetx-workspace':'bob'}
        assert client.get(API+'/workspace?workspace_id=bob',headers=headers).json()['workspace_id']=='alice'
        response=client.post(API+'/ai/workspace?workspace_id=bob',headers=headers,json={'workspace_id':'bob','positioning_line':'SCOPED'})
        assert response.status_code==200 and response.json()['workspace_id']=='alice'
        assert app.state.ai_workspaces.raw('alice')['positioning_line']=='SCOPED'


def test_parallel_connects_use_only_their_bound_broker_and_store(tmp_path):
    alice,bob=create_app(settings(tmp_path,'alice')),create_app(settings(tmp_path,'bob'))
    with TestClient(alice) as left, TestClient(bob) as right:
        resolvers=(alice.state.ai_broker.credential_resolver,bob.state.ai_broker.credential_resolver)
        def connect(which):
            name,client=(('alice',left),('bob',right))[which]
            return client.post(API+'/ai/providers/openai/connect',headers={'x-offsetx-token':settings(tmp_path,name).api_token},json={'api_key':name+'-KEY'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert list(pool.map(connect,[0,1]))==[200,200]
        assert alice.state.ai_broker.credential_resolver is resolvers[0]
        assert bob.state.ai_broker.credential_resolver is resolvers[1]
        assert resolvers[0]('openai')=='alice-KEY' and resolvers[1]('openai')=='bob-KEY'


def test_environment_configuration_is_scoped_and_local_paths_remain_compatible(tmp_path,monkeypatch):
    monkeypatch.setenv('OFFSETX_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('OFFSETX_OUTREACH_DB',str(tmp_path/'crm.db'))
    monkeypatch.setenv('OFFSETX_LOCAL_API_TOKEN','GLOBAL-LOCAL-TOKEN'*4)
    monkeypatch.setenv('OFFSETX_GMAIL_TOKEN',str(tmp_path/'local-gmail.json'))
    local=AppSettings.from_env(tmp_path)
    assert local.workspace_id=='local' and local.data_dir==tmp_path/'data'
    assert local.api_token=='GLOBAL-LOCAL-TOKEN'*4
    monkeypatch.setenv('OFFSETX_WORKSPACE_ID','alice')
    alice=AppSettings.from_env(tmp_path)
    assert alice.data_dir==tmp_path/'data/workspaces/alice'
    assert alice.api_token != local.api_token
    assert alice.gmail_token is None
    monkeypatch.setenv('OFFSETX_WORKSPACE_ID','bob')
    bob=AppSettings.from_env(tmp_path)
    assert bob.api_token != alice.api_token
    assert bob.data_dir != alice.data_dir
    assert bob.scoped().data_dir==bob.data_dir
    assert workspace_env('blue-team','AI_OPENAI_KEY') != workspace_env('blue_team','AI_OPENAI_KEY')


def test_demo_cookie_cannot_be_replayed_across_workspace_instances(tmp_path):
    kwargs={'api_token':'','demo_username':'owner','demo_password':'test-only-long-password', 'session_secret':'test-secret-'*8}
    alice=settings(tmp_path,'alice');bob=settings(tmp_path,'bob')
    for key,value in kwargs.items():
        setattr(alice,key,value);setattr(bob,key,value)
    with TestClient(create_app(alice)) as left,TestClient(create_app(bob)) as right:
        assert left.post(API+'/auth/login',json={'username':'owner','password':kwargs['demo_password']}).status_code==200
        cookie=list(left.cookies.items())[0]
        assert right.get(API+'/ai/providers').status_code==401
        right.cookies.set(cookie[0],cookie[1])
        assert right.get(API+'/ai/providers').status_code==401
        # Even a client renaming the cookie cannot change its cryptographic audience.
        right.cookies.set(workspace_env('bob','SESSION'),cookie[1])
        assert right.get(API+'/ai/providers').status_code==401


def test_generated_token_refuses_symlink_to_another_workspace(tmp_path):
    import pytest
    alice=settings(tmp_path,'alice').scoped()
    alice.api_token=''
    alice.data_dir.mkdir(parents=True)
    foreign=tmp_path/'bob-token'
    foreign.write_text('BOB-PRIVATE-TOKEN'*4)
    (alice.data_dir/alice.TOKEN_FILENAME).symlink_to(foreign)
    with pytest.raises(ValueError,match='symbolic'):
        alice.ensure_api_token()
    assert foreign.read_text()=='BOB-PRIVATE-TOKEN'*4
