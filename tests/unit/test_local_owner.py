import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from local_ai_assistant.interface.api import create_presentation_app
from local_ai_assistant.interface.conversation import FridayConversationService
from local_ai_assistant.interface.local_owner import LocalOwnerTrust
from local_ai_assistant.interface.runtime import FridayRuntime


class Model:
    def stream_chat(self, *args, **kwargs):
        return iter(())


def app(trust=None):
    runtime = FridayRuntime("local-owner-test")
    return create_presentation_app(
        runtime, FridayConversationService(Model(), runtime),
        local_owner_trust=trust,
        project_execution_sessions=trust.sessions if trust else None,
        project_execution_allowed_origins=("http://127.0.0.1:5191",),
    )


def headers(path):
    return {"Origin": "http://127.0.0.1:5191",
            "X-Friday-Local-Owner": json.loads(path.read_text())["capability"]}


def test_restart_restores_session_without_exposing_capability(tmp_path, caplog):
    path = tmp_path / "private" / "owner.json"
    first = LocalOwnerTrust(path, tmp_path)
    original = path.read_bytes()
    previous = None
    for trust in (first, LocalOwnerTrust(path, tmp_path)):
        with TestClient(app(trust), base_url="http://127.0.0.1:8766", client=("127.0.0.1", 50000)) as client:
            if previous:
                assert trust.sessions.principal(*previous) is None
            response = client.post('/api/v1/project-execution/restore', headers=headers(path))
            assert response.status_code == 200
            csrf = response.json()['csrf_token']
            cookie = client.cookies.get('friday_project_session')
            assert trust.sessions.principal(cookie, csrf) == 'local-owner'
            refreshed = client.post('/api/v1/project-execution/restore', headers=headers(path))
            assert refreshed.status_code == 200
            assert refreshed.json()['csrf_token'] == csrf
            assert client.cookies.get('friday_project_session') == cookie
            assert 'HttpOnly' in response.headers['set-cookie']
            assert 'SameSite=strict' in response.headers['set-cookie']
            capability = headers(path)['X-Friday-Local-Owner']
            assert capability not in response.text + str(response.headers) + str(client.cookies) + caplog.text
            assert capability not in str(response.request.url)
            assert path.read_bytes() == original
            previous = cookie, csrf
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize('peer,origin,capability,status', [
    ('192.0.2.1', 'http://127.0.0.1:5191', True, 401),
    ('127.0.0.1', 'https://attacker.invalid', True, 403),
    ('127.0.0.1', '', True, 403),
    ('127.0.0.1', 'http://127.0.0.1:5191', False, 401),
])
def test_restore_requires_local_peer_origin_and_server_capability(tmp_path, peer, origin, capability, status):
    path = tmp_path / 'private' / 'owner.json'
    trust = LocalOwnerTrust(path, tmp_path)
    supplied = headers(path)
    supplied['Origin'] = origin
    if not capability:
        supplied.pop('X-Friday-Local-Owner')
    with TestClient(app(trust), base_url='http://127.0.0.1:8766', client=(peer, 50000)) as client:
        assert client.post('/api/v1/project-execution/restore', headers=supplied).status_code == status


def test_interactive_mode_does_not_inherit_local_trust(tmp_path):
    with TestClient(app(), base_url='http://127.0.0.1:8766', client=('127.0.0.1', 50000)) as client:
        response = client.post('/api/v1/project-execution/restore', headers={'Origin': 'http://127.0.0.1:5191'})
        assert response.json() == {'mode': 'interactive'}
        assert not client.cookies


def test_revoke_and_wrong_installation_fail_closed(tmp_path):
    path = tmp_path / 'private' / 'owner.json'
    trust = LocalOwnerTrust(path, tmp_path)
    supplied = headers(path)['X-Friday-Local-Owner']
    other = tmp_path / 'other'
    other.mkdir()
    with pytest.raises(ValueError, match='installation'):
        LocalOwnerTrust(path, other)
    path.unlink()
    assert trust.restore(supplied, '127.0.0.1', 'localhost') is None


@pytest.mark.parametrize('mode', [0o644, 0o660, 0o400])
def test_insecure_file_rejected(tmp_path, mode):
    path = tmp_path / 'private' / 'owner.json'
    LocalOwnerTrust(path, tmp_path)
    path.chmod(mode)
    with pytest.raises(ValueError, match='private'):
        LocalOwnerTrust(path, tmp_path)


def test_symlink_and_repository_storage_rejected(tmp_path):
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    (tmp_path / 'alias').symlink_to(private, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        LocalOwnerTrust(tmp_path / 'alias' / 'owner.json', tmp_path)
    (tmp_path / '.git').mkdir()
    with pytest.raises(ValueError, match='outside Git'):
        LocalOwnerTrust(private / 'owner.json', tmp_path)


def test_capability_not_in_frontend_sources(tmp_path):
    path = tmp_path / 'private' / 'owner.json'
    LocalOwnerTrust(path, tmp_path)
    secret = headers(path)['X-Friday-Local-Owner'].encode()
    for source in Path('frontend/src').rglob('*'):
        if source.is_file():
            assert secret not in source.read_bytes()
    assert os.getuid() == json.loads(path.read_text())['uid']


def test_restored_identity_still_requires_csrf_and_execution_scope(tmp_path):
    from local_ai_assistant.gateway.auth import GatewayAuth
    from local_ai_assistant.gateway.models import GatewayScope

    path = tmp_path / 'private' / 'owner.json'
    trust = LocalOwnerTrust(path, tmp_path)
    runtime = FridayRuntime('csrf-negative')
    application = create_presentation_app(
        runtime, FridayConversationService(Model(), runtime),
        local_owner_trust=trust, project_execution_sessions=trust.sessions,
        project_execution_allowed_origins=('http://127.0.0.1:5191',),
        objective_execution_auth=GatewayAuth('0' * 64, frozenset({GatewayScope.READ_STATUS})),
    )
    with TestClient(application, base_url='http://127.0.0.1:8766', client=('127.0.0.1', 50000)) as client:
        restored = client.post('/api/v1/project-execution/restore', headers=headers(path))
        csrf = restored.json()['csrf_token']
        route = '/api/v1/objectives/unknown/approval'
        origin = {'Origin': 'http://127.0.0.1:5191'}
        assert client.post(route, headers=origin, json={}).status_code == 401
        assert client.post(route, headers={**origin, 'X-Friday-CSRF': 'wrong'}, json={}).status_code == 401
        assert client.post(route, headers={**origin, 'X-Friday-CSRF': csrf}, json={}).status_code == 403
