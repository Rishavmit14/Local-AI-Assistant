"""Disposable execution qualification; no canonical Project tasks are consumed.

Default cases replace only the HTTP model transport, retaining LocalLLM and role
routing. Opt-in live cases use the configured local Qwen endpoint unchanged.
"""
from __future__ import annotations

import difflib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from local_ai_assistant.agent.code_agent import run_intelligent_validation
from local_ai_assistant.common.config import AppConfig
from local_ai_assistant.execution.errors import ToolExecutionError
from local_ai_assistant.execution.loop import ExecutionLoop, LoopLimits
from local_ai_assistant.execution.registry import ToolContext, default_registry
from local_ai_assistant.isolation.checkpoints import CheckpointManager
from local_ai_assistant.isolation.models import NetworkPolicy, ResourcePolicy
from local_ai_assistant.isolation.sandbox import BubblewrapSandbox
from local_ai_assistant.isolation.worktrees import WorktreeManager
from local_ai_assistant.llm.client import LocalLLM
from local_ai_assistant.planning.analysis import scope_guard_from_plan
from local_ai_assistant.planning.models import plan_approval_token
from local_ai_assistant.planning.service import PlannerService
from local_ai_assistant.roles import Role, RoleOrchestrator
from tests.unit.test_planning import FakeLLM, planning_repo, response_for


def action(tool, arguments, mutates=False):
    return {'tool': tool, 'arguments': arguments, 'rationale': 'Qualify bounded execution',
            'expected_outcome': 'Validate the scoped candidate', 'plan_step': 1,
            'mutation_intended': mutates}


def run_case(tmp_path, case, live=False):
    root, canonical, index = planning_repo.__wrapped__(tmp_path)
    # Boundary/invalid-input assertions are baseline acceptance evidence, never
    # weakened by a generated edit.
    tests = canonical / 'tests/test_service.py'
    tests.write_text("from app.service import login_user\n\ndef test_login():\n    assert login_user('a')\n    assert not login_user('')\n    assert not login_user(None)\n    assert not login_user(123)\n")
    if case == 'contract_stale_expectation':
        tests.write_text(tests.read_text().replace("assert login_user('a')", "assert login_user('a') is False"))
        (canonical / 'ACCEPTANCE.md').write_text(
            'Non-empty strings must return True; empty strings and non-strings must return False.\n'
        )
    subprocess.run(['git', 'add', '.'], cwd=canonical, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Qualification contract'], cwd=canonical, check=True, capture_output=True)
    index.refresh(full=True)
    created_files = (
        ['MODEL_CARD.md'] if case == 'documentation'
        else ['tests/test_generated.py'] if case == 'test_creation'
        else []
    )
    planned_new_symbols = (
        ['tests.test_generated.test_login_rejects_empty_and_non_string_values']
        if case == 'test_creation'
        else ['app.service._has_nonempty_string'] if case == 'helper_add'
        else []
    )
    response = response_for(index, files_to_modify=['app/service.py', 'tests/test_service.py'],
                            files_to_create=created_files,
                            symbols_to_create=planned_new_symbols)
    artifact = PlannerService(canonical, index, FakeLLM(response), root / 'plans').generate(
        'Make login_user return True exactly for non-empty strings, False for empty strings, None and non-strings. '
        + ('Create MODEL_CARD.md explaining behavior and limitations.' if case == 'documentation' else '')
        + ('Create tests/test_generated.py with a function named '
           'test_login_rejects_empty_and_non_string_values covering empty and non-string input.'
           if case == 'test_creation' else '')
        + ('Add a private helper named _has_nonempty_string(value) in app/service.py and use it '
           'from login_user.' if case == 'helper_add' else '')
        + ('Expand tests/test_service.py test_login with a whitespace-only input regression.'
           if case == 'owner_test_required' else '')
        + ('Follow ACCEPTANCE.md and correct only a contradictory expected literal in tests/test_service.py.'
           if case == 'contract_stale_expectation' else '')
    )
    token = plan_approval_token(artifact.plan)
    manager = WorktreeManager(root / 'worktrees')
    identity = manager.create(canonical, artifact.plan.task_id, artifact.starting_commit, token)
    repo = Path(identity.worktree)
    checkpoints = CheckpointManager(root / 'checkpoints')
    checkpoint = checkpoints.create(repo, artifact.plan.task_id, token, 'baseline')
    context = ToolContext(repo, artifact, scope_guard_from_plan(artifact.plan), index, token,
                          sandbox=BubblewrapSandbox(), sandbox_task_root=root / 'sandbox',
                          sandbox_resources=ResourcePolicy(wall_seconds=30),
                          sandbox_network=NetworkPolicy.DENY, canonical_repository=canonical)
    config = AppConfig.from_env({'LOCAL_AI_VAR_DIR': str(root / 'state')})
    config.paths.code_index_dir.mkdir(parents=True)
    model = LocalLLM(config=config)
    symbol = artifact.plan.symbols_to_modify[0]
    good = action('replace_symbol_body', {'symbol': symbol, 'content': 'return isinstance(name, str) and bool(name)'}, True)
    actions = []
    if case in {'syntax', 'name_error', 'type_error', 'assertion'}:
        body = {'syntax': 'if invalid syntax', 'name_error': 'return missing_name',
                'type_error': 'return name + 1', 'assertion': 'return False'}[case]
        actions.append(action('replace_symbol_body', {'symbol': symbol, 'content': body}, True))
        if case != 'syntax':
            actions.append(action('run_tests', {'command': 'python -m pytest'}))
    if case == 'repeated_failed_validation':
        actions.append(action('replace_symbol_body', {'symbol': symbol, 'content': 'return False'}, True))
        actions.extend([
            action('run_tests', {'command': 'python -m pytest'}),
            action('run_tests', {'command': 'python -m pytest'}),
        ])
    if case == 'scope':
        actions.append(action('replace_file', {'path': 'app/api.py', 'content': 'out_of_scope = True\n'}, True))
    actions.append(good)
    if case == 'contract_stale_expectation':
        before_tests = tests.read_text()
        after_tests = before_tests.replace("assert login_user('a') is False",
                                           "assert login_user('a') is True")
        test_patch = 'diff --git a/tests/test_service.py b/tests/test_service.py\n' + ''.join(
            difflib.unified_diff(before_tests.splitlines(keepends=True),
                                 after_tests.splitlines(keepends=True),
                                 fromfile='a/tests/test_service.py', tofile='b/tests/test_service.py')
        )
        actions.extend([
            action('run_tests', {'command': 'python -m pytest'}),
            action('apply_patch', {'patch': test_patch}, True),
        ])
    if case == 'owner_test_required':
        before_tests = tests.read_text()
        after_tests = before_tests.replace("    assert not login_user(123)\n",
                                           "    assert not login_user(123)\n    assert login_user(' ')\n")
        test_patch = 'diff --git a/tests/test_service.py b/tests/test_service.py\n' + ''.join(
            difflib.unified_diff(before_tests.splitlines(keepends=True),
                                 after_tests.splitlines(keepends=True),
                                 fromfile='a/tests/test_service.py', tofile='b/tests/test_service.py')
        )
        actions.extend([
            action('run_tests', {'command': 'python -m pytest'}),
            action('apply_patch', {'patch': test_patch}, True),
        ])
    if case == 'documentation':
        actions.append(action('create_file', {'path': 'MODEL_CARD.md', 'content': '# Input validation\n\nAccepts only non-empty strings. This is input validation, not authentication.\n'}, True))
    if case == 'test_creation':
        actions.append(action('create_file', {'path': 'tests/test_generated.py', 'content':
            "from app.service import login_user\n\ndef test_login_rejects_empty_and_non_string_values():\n"
            "    assert login_user('') is False\n    assert login_user(None) is False\n"
            "    assert login_user(123) is False\n"}, True))
    actions = [
        action('read_file', {'path': 'app/service.py'}),
        action('read_file', {'path': 'tests/test_service.py'}),
        *([action('read_file', {'path': 'ACCEPTANCE.md'})] if case == 'contract_stale_expectation' else []),
        *actions,
    ]
    actions.extend([action('run_tests', {'command': 'python -m pytest'}), action('finish', {})])
    if case == 'repeated_validation':
        actions.insert(-1, action('run_tests', {'command': 'python -m pytest'}))
    calls = []
    if not live:
        iterator = iter(actions)
        def respond(request):
            payload = json.loads(request.content)
            schema = payload.get('response_format', {}).get('json_schema', {}).get('name')
            if schema == 'bounded_repair':
                before = (repo / 'app/service.py').read_text()
                after = "def login_user(name):\n    return isinstance(name, str) and bool(name)\n"
                patch = 'diff --git a/app/service.py b/app/service.py\n' + ''.join(difflib.unified_diff(
                    before.splitlines(keepends=True), after.splitlines(keepends=True),
                    fromfile='a/app/service.py', tofile='b/app/service.py'))
                value = {'rationale': 'Repair the actual scoped candidate defect', 'patch': patch}
            elif 'response_format' not in payload:
                value = {'summary': 'Scripted deterministic harness review', 'findings': []}
            else:
                assert payload['response_format']['type'] == 'json_schema'
                calls.append(payload['response_format']['type'])
                value = next(iterator, action('finish', {}))
            content = json.dumps(value)
            reason = 'stop'
            if case == 'malformed':
                content = '{invalid'
            if case == 'truncated':
                reason = 'length'
            return httpx.Response(200, json={'id': 'qualification', 'object': 'chat.completion',
                'created': 0, 'model': 'local-fixture', 'choices': [{'index': 0,
                'message': {'role': 'assistant', 'content': content}, 'finish_reason': reason}]})
        model.client = OpenAI(base_url='http://127.0.0.1:8080/v1', api_key='local', max_retries=0,
                              http_client=httpx.Client(transport=httpx.MockTransport(respond)))
    roles = RoleOrchestrator(model)
    result = None
    validation_ok = False
    try:
        try:
            result = ExecutionLoop(roles.client(Role.CODER), default_registry(), context,
                                  LoopLimits(max_steps=14, max_mutations=5, max_repairs=2)).run()
        except ToolExecutionError:
            assert case in {'malformed', 'truncated'} or live
        if live:
            print('bounded model sequence:', json.dumps({
                'status': result.status if result else 'protocol_failure',
                'mutations': result.mutations if result else 0,
                'steps': result.steps if result else 0,
                'events': [{'tool': event.tool_name, 'success': event.success,
                            'summary': event.output_summary[:120],
                            'mutation': event.mutation_summary,
                            'scope': event.decision_metadata.get('scope_mapping'),
                            'arguments': event.decision_metadata.get('argument_names')}
                           for event in context.events],
            }))
            if case in {'valid', 'documentation', 'repair_name', 'repair_assertion'}:
                assert result is not None and result.status == 'complete', (
                    f'live Qwen did not complete the approved edit/validation plan: '
                    f'{result.status if result else "protocol_failure"}'
                )
        if not live and case not in {'malformed', 'truncated', 'scope'}:
            assert result is not None and result.status == 'complete', (
                [(event.tool_name, event.success, event.affected_files, event.output_summary[-180:])
                 for event in context.events if event.tool_name in {'replace_symbol_body', 'replace_file'}]
                if result else 'no result',
                [(item.kind, item.success, item.summary[-150:]) for item in result.observations] if result else [],
            )
            assert any(event.tool_name == 'run_tests' and event.success for event in context.events)
        if case == 'repeated_failed_validation' and not live:
            failed_runs = [event for event in context.events
                           if event.tool_name == 'run_tests' and not event.success]
            assert len(failed_runs) == 1
            assert any('already failed' in item.summary for item in result.observations)
        if case == 'owner_test_required' and not live:
            assert any(item.kind == 'owner_requirement_required' for item in result.observations)
            assert any(event.tool_name == 'apply_patch'
                       and 'tests/test_service.py' in event.affected_files
                       for event in context.events)
        if case == 'contract_stale_expectation' and not live:
            assert any(event.tool_name == 'run_tests' and not event.success for event in context.events)
            assert any(event.tool_name == 'apply_patch' and event.success for event in context.events)
            assert (repo / 'app/service.py').read_text() == (
                'def login_user(name):\n    return isinstance(name, str) and bool(name)\n'
            )
            assert "assert login_user('a') is True" in (repo / 'tests/test_service.py').read_text()
            assert "assert not login_user('')" in (repo / 'tests/test_service.py').read_text()
        if case in {'malformed', 'truncated'} and not live:
            assert len(calls) == 2  # One bounded corrective response, no mutation.
            assert (repo / 'app/service.py').read_text() == (canonical / 'app/service.py').read_text()
            if result is not None and result.status == 'complete':
                if case in {'repair_name', 'repair_assertion'}:
                    test_symbol = next(
                        item for item in index.symbols
                        if item.path.endswith('tests/test_service.py') and item.name == 'test_login'
                    )
                    default_registry().invoke('replace_symbol_body', {
                        'symbol': test_symbol.identifier,
                        'content': (
                            "assert login_user('a') is True\n"
                            "assert login_user('') is False\n"
                            "assert login_user(None) is False\n"
                            "assert login_user(123) is False\n"
                            "assert login_user([]) is False\n"
                        ),
                        '_mutation_intended': True,
                    }, context)
                    body = 'return missing_name' if case == 'repair_name' else 'return False'
                default_registry().invoke('replace_symbol_body', {'symbol': symbol, 'content': body,
                    '_mutation_intended': True}, context)
            rag = SimpleNamespace(symbol_index=index, llm=model)
            validation_ok, _reason, _digest = run_intelligent_validation(
                repo, artifact, rag, config, context=context, max_repairs=2, roles=roles)
            if case in {'repair_name', 'repair_assertion'}:
                assert validation_ok, _reason
            if case in {'repair_name', 'repair_assertion'} and not live:
                report = json.loads((config.paths.code_index_dir / 'validations' / f'{artifact.plan.task_id}.json').read_text())
                assert report['repair_attempts'] == 1
        if live and case == 'documentation':
            assert (repo / 'MODEL_CARD.md').is_file()
        if live and case == 'test_creation':
            created_test = repo / 'tests/test_generated.py'
            assert created_test.is_file() and 'def test_' in created_test.read_text()
        if live and case == 'helper_add':
            service_source = (repo / 'app/service.py').read_text()
            assert 'def _has_nonempty_string' in service_source
            assert '_has_nonempty_string(' in service_source.split('def login_user', 1)[-1]
        if not live:
            assert calls
    finally:
        checkpoints.restore(repo, checkpoint)
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--ignored=matching'], cwd=repo).strip()
        assert not subprocess.check_output(['git', 'status', '--porcelain', '--ignored=matching'], cwd=canonical).strip()
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=canonical, text=True).strip() == artifact.starting_commit
        manager.cleanup(identity, delete_branch=True, allow_active=True)
        assert not repo.exists()
    return ('validated' if validation_ok else result.status) if result else 'safe_protocol_failure'


@pytest.mark.parametrize('case', ['valid', 'syntax', 'name_error', 'type_error', 'assertion', 'documentation', 'scope', 'malformed', 'truncated', 'repair_name', 'repair_assertion', 'repeated_validation', 'repeated_failed_validation', 'owner_test_required', 'contract_stale_expectation'])
def test_deterministic_execution_qualification(tmp_path, case):
    run_case(tmp_path, case)


@pytest.mark.skipif(os.environ.get('FRIDAY_LIVE_QWEN_SOAK') != '1', reason='Explicit live local-Qwen qualification only')
@pytest.mark.parametrize('case', ['valid', 'helper_add', 'documentation', 'test_creation', 'repair_name', 'repair_assertion'])
def test_live_qwen_qualification(tmp_path, case):
    status = run_case(tmp_path, case, live=True)
    print(f'local-Qwen {case}: {status}; isolated repository restored and removed')
