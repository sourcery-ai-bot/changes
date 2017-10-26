import os
import textwrap

import pytest
import responses

from changes.commands import init
from .conftest import AUTH_TOKEN_ENVVAR, LABEL_URL


BUG_LABEL_JSON = [
    {
        'id': 52048163,
        'url': 'https://api.github.com/repos/michaeljoseph/changes/labels/bug',
        'name': 'bug',
        'color': 'fc2929',
        'default': True
    }
]


@pytest.fixture
def answer_prompts(mocker):
    _ = mocker.patch(
        'changes.config.click.launch',
        autospec=True,
    )

    prompt = mocker.patch(
        'changes.config.click.prompt',
        autospec=True,
    )
    prompt.side_effect = [
        'foo',
        'docs/releases',
        'version.txt',
        '.'
    ]

    prompt = mocker.patch(
        'changes.config.choose_labels',
        autospec=True
    )
    prompt.return_value = ['bug']

    saved_token = None
    if os.environ.get(AUTH_TOKEN_ENVVAR):
        saved_token = os.environ[AUTH_TOKEN_ENVVAR]
        del os.environ[AUTH_TOKEN_ENVVAR]

    yield

    if saved_token:
        os.environ[AUTH_TOKEN_ENVVAR] = saved_token


@responses.activate
def test_init_prompts_for_auth_token_and_writes_tool_config(
    capsys,
    git_repo,
    changes_config_in_tmpdir,
    answer_prompts,
):
    responses.add(
        responses.GET,
        LABEL_URL,
        json=BUG_LABEL_JSON,
        status=200,
        content_type='application/json'
    )

    init.init()

    assert changes_config_in_tmpdir.exists()
    expected_config = textwrap.dedent(
        """\
        [changes]
        auth_token = "foo"
        """
    )
    assert expected_config == changes_config_in_tmpdir.read_text()

    expected_output = textwrap.dedent(
        """\
        No auth token found, asking for it...
        You need a Github Auth Token for changes to create a release.
        Releases directory docs/releases not found, creating it....
        """
    )
    out, _ = capsys.readouterr()
    assert expected_output == out


@responses.activate
def test_init_finds_auth_token_in_environment(
    capsys,
    git_repo,
    with_auth_token_envvar,
    changes_config_in_tmpdir,
    with_releases_directory_and_bumpversion_file_prompt,
):
    responses.add(
        responses.GET,
        LABEL_URL,
        json=BUG_LABEL_JSON,
        status=200,
        content_type='application/json'
    )

    init.init()

    # envvar setting is not written to the config file
    assert not changes_config_in_tmpdir.exists()

    expected_output = textwrap.dedent(
        """\
        Found Github Auth Token in the environment...
        Releases directory docs/releases not found, creating it....
        """
    )
    out, _ = capsys.readouterr()
    assert expected_output == out
