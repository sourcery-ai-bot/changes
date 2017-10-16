import os
import shlex

import pytest
import responses
from click.testing import CliRunner
from plumbum.cmd import git

pytest_plugins = 'pytester'

# TODO: textwrap.dedent.heredoc
INIT_CONTENT = [
    '"""A test app"""',
    '',
    "__version__ = '0.0.1'",
    "__url__ = 'https://github.com/someuser/test_app'",
    "__author__ = 'Some User'",
    "__email__ = 'someuser@gmail.com'"
]
SETUP_PY = [
    'from setuptools import setup',
    "setup(name='test_app'",
]
README_MARKDOWN = [
    '# Test App',
    '',
    'This is the test application.'
]

PYTHON_MODULE = 'test_app'

FILE_CONTENT = {
    '%s/__init__.py' % PYTHON_MODULE: INIT_CONTENT,
    'setup.py': SETUP_PY,
    'requirements.txt': ['pytest'],
    'README.md': README_MARKDOWN,
    'CHANGELOG.md': [''],
}
ISSUE_URL = 'https://api.github.com/repos/michaeljoseph/test_app/issues/{}'
AUTH_TOKEN_ENVVAR = 'GITHUB_AUTH_TOKEN'


@pytest.fixture
def python_module():
    with CliRunner().isolated_filesystem():
        os.mkdir(PYTHON_MODULE)

        for file_path, content in FILE_CONTENT.items():
            open(file_path, 'w').write(
                '\n'.join(content)
            )

        git_init(FILE_CONTENT.keys())

        yield


@pytest.fixture
def git_repo():
    with CliRunner().isolated_filesystem():
        readme_path = 'README.md'
        open(readme_path, 'w').write(
            '\n'.join(README_MARKDOWN)
        )
        git_init([readme_path])

        yield


def git_init(files_to_add):
    git('init')
    git(shlex.split('config --local user.email "you@example.com"'))
    git('remote', 'add', 'origin', 'https://github.com/michaeljoseph/test_app.git')
    for file_to_add in files_to_add:
        git('add', file_to_add)
    git('commit', '-m', 'Initial commit')


@pytest.fixture
@responses.activate
def git_repo_with_merge_commit(git_repo):
    git(shlex.split('tag 0.0.1'))
    github_merge_commit(111)


def github_merge_commit(pull_request_number):
    from haikunator import Haikunator

    branch_name = Haikunator().haikunate()
    commands = [
        'checkout -b {}'.format(branch_name),
        'commit --allow-empty -m "Test branch commit message"',
        'checkout master',
        'merge --no-ff {}'.format(branch_name),

        'commit --allow-empty --amend -m '
        '"Merge pull request #{} from test_app/{}"'.format(
            pull_request_number,
            branch_name,
        )
    ]
    for command in commands:
        git(shlex.split(command))


@pytest.fixture
def with_auth_token_prompt(mocker):
    _ = mocker.patch('changes.commands.init.click.launch')

    prompt = mocker.patch('changes.commands.init.click.prompt')
    prompt.return_value = 'foo'

    saved_token = None
    if os.environ.get(AUTH_TOKEN_ENVVAR):
        saved_token = os.environ[AUTH_TOKEN_ENVVAR]
        del os.environ[AUTH_TOKEN_ENVVAR]

    yield

    if saved_token:
        os.environ[AUTH_TOKEN_ENVVAR] = saved_token


@pytest.fixture
def with_auth_token_envvar():
    saved_token = None
    if os.environ.get(AUTH_TOKEN_ENVVAR):
        saved_token = os.environ[AUTH_TOKEN_ENVVAR]

    os.environ[AUTH_TOKEN_ENVVAR] = 'foo'

    yield

    if saved_token:
        os.environ[AUTH_TOKEN_ENVVAR] = saved_token