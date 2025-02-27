import os
import shlex
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner
from plumbum.cmd import git

import changes
from changes import compat

pytest_plugins = 'pytester'

# TODO: textwrap.dedent.heredoc
INIT_CONTENT = [
    '"""A test app"""',
    '',
    "__version__ = '0.0.1'",
    "__url__ = 'https://github.com/someuser/test_app'",
    "__author__ = 'Some User'",
    "__email__ = 'someuser@gmail.com'",
]
SETUP_PY = ['from setuptools import setup', "setup(name='test_app'"]
README_MARKDOWN = ['# Test App', '', 'This is the test application.']

PYTHON_MODULE = 'test_app'

PYTHON_PROJECT_CONTENT = {
    f'{PYTHON_MODULE}/__init__.py': INIT_CONTENT,
    'setup.py': SETUP_PY,
    'requirements.txt': ['pytest'],
}


FILE_CONTENT = {
    'version.txt': ['0.0.1'],
    'README.md': README_MARKDOWN,
    'CHANGELOG.md': [''],
}

AUTH_TOKEN_ENVVAR = 'GITHUB_AUTH_TOKEN'

BUG_LABEL_JSON = [
    {
        'id': 52048163,
        'url': 'https://api.github.com/repos/michaeljoseph/changes/labels/bug',
        'name': 'bug',
        'color': 'fc2929',
        'default': True,
    }
]

ISSUE_URL = 'https://api.github.com/repos/michaeljoseph/test_app/issues/111'
PULL_REQUEST_JSON = {
    'number': 111,
    'title': 'The title of the pull request',
    'body': 'An optional, longer description.',
    'user': {'login': 'michaeljoseph'},
    'labels': [{'id': 1, 'name': 'bug'}],
    'url': 'https://api.github.com/repos/michaeljoseph/test_app/issues/111',
}

LABEL_URL = 'https://api.github.com/repos/michaeljoseph/test_app/labels'
BUG_LABEL_JSON = [
    {
        'id': 52048163,
        'url': 'https://api.github.com/repos/michaeljoseph/test_app/labels/bug',
        'name': 'bug',
        'color': 'fc2929',
        'default': True,
    }
]

RELEASES_URL = 'https://api.github.com/repos/michaeljoseph/test_app/releases'


@pytest.fixture
def git_repo(tmpdir):
    with CliRunner().isolated_filesystem() as repo_dir:
        for file_path, content in FILE_CONTENT.items():
            open(file_path, 'w').write('\n'.join(content))

        git('init')
        git(shlex.split('config --local user.email "you@example.com"'))
        git(shlex.split('config --local user.name "Your Name"'))
        git(
            shlex.split(
                'remote add origin https://github.com/michaeljoseph/test_app.git'
            )
        )

        tmp_push_repo = Path(str(tmpdir))
        git('init', '--bare', str(tmp_push_repo))
        git(shlex.split(f'remote set-url --push origin {tmp_push_repo.as_uri()}'))

        git('add', list(FILE_CONTENT.keys()))

        git('commit', '-m', 'Initial commit')
        git(shlex.split('tag 0.0.1'))

        yield repo_dir


@pytest.fixture
def python_module(git_repo):
    os.mkdir(PYTHON_MODULE)

    for file_path, content in PYTHON_PROJECT_CONTENT.items():
        open(file_path, 'w').write('\n'.join(content))

    git('add', list(PYTHON_PROJECT_CONTENT.keys()))
    git('commit', '-m', 'Python project initialisation')

    yield


def github_merge_commit(pull_request_number):
    from haikunator import Haikunator

    branch_name = Haikunator().haikunate()
    commands = [
        f'checkout -b {branch_name}',
        'commit --allow-empty -m "Test branch commit message"',
        'checkout master',
        f'merge --no-ff {branch_name}',
        f'commit --allow-empty --amend -m "Merge pull request #{pull_request_number} from test_app/{branch_name}"',
    ]

    for command in commands:
        git(shlex.split(command))


# prompts_for_tool_configuration
@pytest.fixture
def with_releases_directory_and_bumpversion_file_prompt(mocker):
    prompt = mocker.patch('changes.config.click.prompt', autospec=True)
    prompt.side_effect = [
        # release_directory
        'docs/releases',
        # bumpversion files
        'version.txt',
        # quit prompt
        '.',
        # label descriptions
        # 'Features',
        # 'Bug Fixes'
    ]

    prompt = mocker.patch('changes.config.prompt.choose_labels', autospec=True)
    prompt.return_value = ['bug']


@pytest.fixture
def with_auth_token_prompt(mocker):
    mocker.patch('changes.config.click.launch')

    prompt = mocker.patch('changes.config.click.prompt')
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
    else:
        del os.environ[AUTH_TOKEN_ENVVAR]


@pytest.fixture
def changes_config_in_tmpdir(monkeypatch, tmpdir):
    changes_config_file = Path(str(tmpdir.join('.changes')))
    monkeypatch.setattr(
        changes.config,
        'expandvars' if compat.IS_WINDOWS else 'expanduser',
        lambda x: str(changes_config_file),
    )
    assert not changes_config_file.exists()
    return changes_config_file


@pytest.fixture
def configured(git_repo, changes_config_in_tmpdir):
    changes_config_in_tmpdir.write_text(
        textwrap.dedent(
            """\
        [changes]
        auth_token = "foo"
        """
        )
    )

    Path('.changes.toml').write_text(
        textwrap.dedent(
            """\
        [changes]
        releases_directory = "docs/releases"

        [changes.labels.bug]
        default = true
        id = 208045946
        url = "https://api.github.com/repos/michaeljoseph/test_app/labels/bug"
        name = "bug"
        description = "Bug"
        color = "f29513"
        """
        )
    )

    Path('.bumpversion.cfg').write_text(
        textwrap.dedent(
            """\
        [bumpversion]
        current_version = 0.0.1

        [bumpversion:file:version.txt]
        """
        )
    )

    for file_to_add in ['.changes.toml', '.bumpversion.cfg']:
        git('add', file_to_add)
    git('commit', '-m', 'Add changes configuration files')

    return str(changes_config_in_tmpdir)
