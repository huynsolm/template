"""Provider tests use only temporary local scripts, never real AI CLIs."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.providers import CliProvider, PasteProvider, ProviderError


def config_for(tmp_path, body, name='codex', extra_args=()):
    script = tmp_path / 'fake_cli.py'
    script.write_text(body, encoding='utf-8')
    config = tmp_path / 'providers.toml'
    command = [sys.executable, str(script), *extra_args]
    config.write_text(f'[providers.{name}]\ncommand = {json.dumps(command)}\n', encoding='utf-8')
    return config


def test_paste_preserves_answer(tmp_path):
    answer = tmp_path / 'answer.txt'
    answer.write_text('  답변\n', encoding='utf-8')
    assert PasteProvider(answer).generate('ignored') == '  답변\n'


@pytest.mark.parametrize('kind', ['missing', 'empty', 'invalid_utf8'])
def test_paste_reports_safe_errors(tmp_path, kind):
    answer = tmp_path / 'secret-answer.txt'
    if kind == 'empty':
        answer.write_text(' \n')
    elif kind == 'invalid_utf8':
        answer.write_bytes(b'\xff')
    with pytest.raises(ProviderError) as error:
        PasteProvider(answer).generate('prompt')
    assert error.value.exit_code == 7
    assert str(answer) not in str(error.value)


@pytest.mark.parametrize('name', ['claude', 'codex', 'gemini'])
def test_cli_stdin_shell_false_and_clean_temporary_cwd(tmp_path, monkeypatch, name):
    config = config_for(tmp_path, '''import json, os, sys
print(json.dumps({'prompt': sys.stdin.read(), 'cwd': os.getcwd(), 'files': os.listdir('.')}))
''', name)
    real_run = subprocess.run
    calls = []
    def checked_run(*args, **kwargs):
        calls.append(kwargs)
        return real_run(*args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', checked_run)
    prompt = '한글 "quotes" $HOME `touch dangerous`\n'
    result = json.loads(CliProvider(name, config_path=config).generate(prompt))
    assert result['prompt'] == prompt
    assert result['files'] == []
    assert not Path(result['cwd']).exists()
    assert calls[0]['shell'] is False
    assert len(calls) == 1


def test_cli_answer_file_is_exact_marker_and_preserves_text(tmp_path):
    config = config_for(tmp_path, '''import pathlib, sys
assert sys.argv[1] == 'literal-{answer_file}'
pathlib.Path(sys.argv[2]).write_text('  final answer\\n', encoding='utf-8')
print('progress must not be the answer')
''', extra_args=['literal-{answer_file}', '{answer_file}'])
    assert CliProvider('codex', config_path=config).generate('prompt') == '  final answer\n'


@pytest.mark.parametrize(('body', 'exit_code'), [
    ("import sys; print('secret token', file=sys.stderr); sys.exit(9)", 7),
    ("import time; time.sleep(5)", 4),
    ("print('  ')", 7),
    ("import sys; print('Usage limit reached: secret', file=sys.stderr); sys.exit(1)", 5),
    ("import sys; print('Please log in: secret', file=sys.stderr); sys.exit(1)", 6),
    ("print('Quota exceeded: secret')", 5),
    ("print('Not authenticated: secret')", 6),
])
def test_cli_failure_types_do_not_expose_output(tmp_path, body, exit_code):
    config = config_for(tmp_path, body)
    with pytest.raises(ProviderError) as error:
        CliProvider('codex', config_path=config, timeout=0.1).generate('prompt secret')
    assert error.value.exit_code == exit_code
    assert 'secret' not in str(error.value)
    if exit_code == 5:
        assert 'paste' in str(error.value).lower()


def test_missing_executable(tmp_path):
    config = tmp_path / 'providers.toml'
    config.write_text('[providers.codex]\ncommand = ["/nonexistent-secret-cli"]\n')
    with pytest.raises(ProviderError) as error:
        CliProvider('codex', config_path=config).generate('prompt')
    assert error.value.exit_code == 3
    assert 'secret' not in str(error.value)


@pytest.mark.parametrize('content', [
    '[providers.codex]\ncommand="secret"',
    '[providers.codex]\ncommand=[]',
    '[providers.codex]\ncommand=[42]',
    'secret-invalid-config',
])
def test_invalid_config_is_redacted(tmp_path, content):
    config = tmp_path / 'providers.toml'
    config.write_text(content)
    with pytest.raises(ProviderError) as error:
        CliProvider('codex', config_path=config).generate('prompt')
    assert error.value.exit_code == 7
    assert 'secret' not in str(error.value)


@pytest.mark.parametrize('name', ['claude', 'gemini'])
def test_unverified_defaults_require_configuration(name):
    with pytest.raises(ProviderError) as error:
        CliProvider(name).generate('prompt')
    assert error.value.exit_code == 3
    assert 'configur' in str(error.value).lower()


def test_default_codex_config_has_verified_read_only_options():
    import tomllib
    data = tomllib.loads((ROOT / 'providers.toml').read_text())
    args = data['providers']['codex']['command']
    assert args[0:2] == ['codex', 'exec']
    assert args[args.index('--sandbox') + 1] == 'read-only'
    assert '--ignore-user-config' in args
    assert '--ephemeral' in args
    assert '--skip-git-repo-check' in args
    assert args[args.index('--output-last-message') + 1] == '{answer_file}'
    assert args[-1] == '-'
    assert not any('bypass' in arg for arg in args)


def test_successful_product_numbers_do_not_become_auth_or_quota_errors(tmp_path):
    answer = '{"headline": "Models 401 and 429", "subcopy": "Physical limit reached at stopper"}\n'
    config = config_for(tmp_path, f'import sys; sys.stdout.write({answer!r})')
    assert CliProvider('codex', config_path=config).generate('prompt') == answer


@pytest.mark.parametrize(('message', 'exit_code'), [
    ('HTTP 429 Too Many Requests', 5),
    ('HTTP 401 Unauthorized', 6),
])
def test_http_error_status_messages_are_classified(tmp_path, message, exit_code):
    config = config_for(tmp_path, f'print({message!r})')
    with pytest.raises(ProviderError) as error:
        CliProvider('codex', config_path=config).generate('prompt')
    assert error.value.exit_code == exit_code


@pytest.mark.parametrize('variable', [
    'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY',
    'ANTHROPIC_AUTH_TOKEN', 'CODEX_API_KEY',
])
def test_api_credentials_reject_cli_before_launch(tmp_path, monkeypatch, variable):
    launched = tmp_path / 'launched'
    config = config_for(tmp_path, f'from pathlib import Path; Path({str(launched)!r}).touch(); print("answer")')
    monkeypatch.setenv(variable, 'secret-api-credential')
    with pytest.raises(ProviderError) as error:
        CliProvider('codex', config_path=config).generate('prompt')
    assert error.value.exit_code == 6
    assert 'subscription' in str(error.value).lower()
    assert 'secret-api-credential' not in str(error.value)
    assert not launched.exists()


def test_subscription_oauth_variable_is_preserved(tmp_path, monkeypatch):
    config = config_for(tmp_path, "import os; assert os.environ['CODEX_ACCESS_TOKEN'] == 'subscription-oauth'; print('answer')")
    monkeypatch.setenv('CODEX_ACCESS_TOKEN', 'subscription-oauth')
    assert CliProvider('codex', config_path=config).generate('prompt') == 'answer\n'
