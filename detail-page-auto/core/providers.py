"""File and official-CLI providers; no SDKs or paid API credentials are used."""
from __future__ import annotations

from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory
import tomllib
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
API_AUTH_VARIABLES = (
    'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_API_KEY',
    'ANTHROPIC_AUTH_TOKEN', 'CODEX_API_KEY',
)


class Provider(Protocol):
    def generate(self, prompt_text: str) -> str:
        """Return the complete, unmodified answer text."""
        ...


class ProviderError(ValueError):
    """A safe, user-facing failure with a stable CLI exit code."""

    def __init__(self, message: str, exit_code: int = 7):
        super().__init__(message)
        self.exit_code = exit_code


class PasteProvider:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def generate(self, prompt_text: str) -> str:
        try:
            answer = self.path.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            raise ProviderError('Cannot read the answer file as UTF-8.') from None
        if not answer.strip():
            raise ProviderError('The answer file is empty.')
        return answer


class CliProvider:
    """Run one CLI invocation; validation and retry policy belong to the workflow."""

    def __init__(self, name: str, config_path: str | Path = ROOT / 'providers.toml',
                 timeout: float = 300):
        self.name = name
        self.config_path = Path(config_path)
        self.timeout = timeout

    def _command(self) -> list[str]:
        if self.name not in {'claude', 'codex', 'gemini'}:
            raise ProviderError('Unsupported CLI provider; choose claude, codex, or gemini.')
        try:
            with self.config_path.open('rb') as stream:
                settings = tomllib.load(stream)
            providers = settings.get('providers', {})
            if not isinstance(providers, dict):
                raise ValueError
            entry = providers.get(self.name)
            if entry is None:
                raise ProviderError('CLI provider requires configuration in providers.toml.', 3)
            if not isinstance(entry, dict):
                raise ValueError
            if entry.get('configured') is False:
                raise ProviderError('CLI provider requires configuration in providers.toml.', 3)
            command = entry.get('command')
            if (not isinstance(command, list) or not command
                    or not all(isinstance(arg, str) and '\x00' not in arg for arg in command)
                    or not command[0].strip()):
                raise ValueError
        except ProviderError:
            raise
        except (OSError, ValueError, TypeError):
            raise ProviderError('Cannot read a valid CLI command configuration.') from None
        return command

    def generate(self, prompt_text: str) -> str:
        command = self._command()
        if any(os.environ.get(name) for name in API_AUTH_VARIABLES):
            raise ProviderError(
                'CLI mode requires subscription login. Remove API credential '
                'environment variables before retrying.', 6,
            )
        if (isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float))
                or not 0 < self.timeout < float('inf')):
            raise ProviderError('CLI timeout must be a positive finite number.')
        with TemporaryDirectory(prefix='detail-page-cli-') as working_dir:
            answer_file = Path(working_dir) / 'answer.txt'
            uses_answer_file = '{answer_file}' in command
            command = [str(answer_file) if arg == '{answer_file}' else arg for arg in command]
            try:
                result = subprocess.run(
                    command, input=prompt_text, capture_output=True, text=True,
                    encoding='utf-8', errors='replace', shell=False,
                    cwd=working_dir, timeout=self.timeout,
                )
            except FileNotFoundError:
                raise ProviderError('CLI executable is not installed or unavailable.', 3) from None
            except subprocess.TimeoutExpired:
                raise ProviderError('CLI time limit exceeded.', 4) from None
            except (OSError, ValueError):
                raise ProviderError('CLI could not be started.') from None
            # Inspect diagnostics only in memory; never include them in errors or logs.
            diagnostics = (result.stdout + '\n' + result.stderr).lower()
            quota_markers = ('usage limit', 'quota exceeded', 'quota exhausted',
                             'rate limit', 'too many requests', 'usage cap',
                             'http 429', 'http status 429', 'status code 429')
            auth_markers = ('not authenticated', 'unauthenticated', 'not logged in',
                            'please log in', 'please login', 'authentication required',
                            'authentication failed', 'login required', 'invalid api key',
                            'unauthorized', 'http 401', 'http status 401',
                            'status code 401')
            if any(marker in diagnostics for marker in quota_markers):
                raise ProviderError('CLI usage limit reached; switch to paste mode.', 5)
            if any(marker in diagnostics for marker in auth_markers):
                raise ProviderError('CLI login required; sign in using the official CLI.', 6)
            if result.returncode != 0:
                raise ProviderError('CLI exited unsuccessfully.')
            if uses_answer_file:
                try:
                    answer = answer_file.read_text(encoding='utf-8')
                except (OSError, UnicodeError):
                    raise ProviderError('CLI did not produce a readable answer file.') from None
            else:
                answer = result.stdout
            if not answer.strip():
                raise ProviderError('CLI returned an empty answer.')
            return answer
