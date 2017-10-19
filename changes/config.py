import textwrap
from collections import OrderedDict
from os.path import exists, expanduser, expandvars, join, curdir
import io
import os
import sys

import click
from pathlib import Path

import toml
import attr

import changes
from changes.models import GitRepository
from .commands import info, note


AUTH_TOKEN_ENVVAR = 'GITHUB_AUTH_TOKEN'

# via https://github.com/jakubroztocil/httpie/blob/6bdfc7a/httpie/config.py#L9
IS_WINDOWS = 'win32' in str(sys.platform).lower()
DEFAULT_CONFIG_FILE = str(os.environ.get(
    'CHANGES_CONFIG_FILE',
    expanduser('~/.changes') if not IS_WINDOWS else
    expandvars(r'%APPDATA%\\.changes')
))

PROJECT_CONFIG_FILE = '.changes.toml'
DEFAULT_RELEASES_DIRECTORY = 'docs/releases'


@attr.s
class Changes(object):
    auth_token = attr.ib()


def load_settings():
    tool_config_path = Path(str(os.environ.get(
        'CHANGES_CONFIG_FILE',
        expanduser('~/.changes') if not IS_WINDOWS else
        expandvars(r'%APPDATA%\\.changes')
    )))

    tool_settings = None
    if tool_config_path.exists():
        tool_settings = Changes(
            **(toml.load(tool_config_path.open())['changes'])
        )

    if not (tool_settings and tool_settings.auth_token):
        # prompt for auth token
        auth_token = os.environ.get(AUTH_TOKEN_ENVVAR)
        if auth_token:
            info('Found Github Auth Token in the environment')

        while not auth_token:
            info('No auth token found, asking for it')
            # to interact with the Git*H*ub API
            note('You need a Github Auth Token for changes to create a release.')
            click.pause('Press [enter] to launch the GitHub "New personal access '
                        'token" page, to create a token for changes.')
            click.launch('https://github.com/settings/tokens/new')
            auth_token = click.prompt('Enter your changes token')

        if not tool_settings:
            tool_settings = Changes(auth_token=auth_token)

        tool_config_path.write_text(
            toml.dumps({
                'changes': attr.asdict(tool_settings)
            })
        )

    return tool_settings


@attr.s
class Project(object):
    releases_directory = attr.ib()
    repository = attr.ib(default=None)
    bumpversion = attr.ib(default=None)
    labels = attr.ib(default=attr.Factory(dict))

    @property
    def bumpversion_configured(self):
        return isinstance(self.bumpversion, BumpVersion)

    @property
    def labels_selected(self):
        return len(self.labels) > 0


@attr.s
class BumpVersion(object):
    DRAFT_OPTIONS = [
        '--dry-run', '--verbose',
        '--no-commit', '--no-tag',
        '--allow-dirty',
    ]
    STAGE_OPTIONS = [
        '--verbose',
        '--no-commit', '--no-tag',
    ]

    current_version = attr.ib()
    version_files_to_replace = attr.ib(default=attr.Factory(list))

    def write_to_file(self, config_path: Path):
        bumpversion_cfg = textwrap.dedent(
            """\
            [bumpversion]
            current_version = {current_version}

            """
        ).format(**attr.asdict(self))

        bumpversion_files = '\n\n'.join([
            '[bumpversion:file:{}]'.format(file_name)
            for file_name in self.version_files_to_replace
        ])

        config_path.write_text(
            bumpversion_cfg + bumpversion_files
        )


def load_project_settings():
    project_settings = configure_changes()

    info('Indexing repository')
    project_settings.repository = GitRepository(
        auth_token=changes.settings.auth_token
    )

    project_settings.bumpversion = configure_bumpversion(project_settings)

    project_settings.labels = configure_labels(project_settings)

    return project_settings


def configure_labels(project_settings):
    if project_settings.labels_selected:
        return project_settings.labels

    github_labels = project_settings.repository.github_labels

    # since there are no labels defined
    # let's ask which github tags they want to track
    # TODO: streamlined support for github defaults: enhancement, bug
    changelog_worthy_labels = read_user_choices(
        'labels',
        [
            properties['name']
            for label, properties in github_labels.items()
        ]
    )

    # TODO: if not project_settings.labels_have_descriptions:
    described_labels = {}
    # auto-generate label descriptions
    for label_name in changelog_worthy_labels:
        label_properties = github_labels[label_name]
        # Auto-generate description as titlecase label name
        label_properties['description'] = label_name.title()
        described_labels[label_name] = label_properties

    return described_labels


def configure_changes():
    changes_project_config_path = Path(PROJECT_CONFIG_FILE)
    project_settings = None
    if changes_project_config_path.exists():
        project_settings = Project(
            **(toml.load(changes_project_config_path.open())['changes'])
        )
    if not project_settings:
        project_settings = Project(
            releases_directory=str(Path(click.prompt(
                'Enter the directory to store your releases notes',
                DEFAULT_RELEASES_DIRECTORY,
                type=click.Path(exists=True, dir_okay=True)
            )))
        )
        # write config file
        changes_project_config_path.write_text(
            toml.dumps({
                'changes': attr.asdict(project_settings)
            })
        )

    return project_settings


def configure_bumpversion(project_settings):
    # TODO: look in other supported bumpversion config locations
    bumpversion = None
    bumpversion_config_path = Path('.bumpversion.cfg')
    if not bumpversion_config_path.exists():
        user_supplied_versioned_file_paths = []

        version_file_path = None
        while not version_file_path == Path('.'):
            version_file_path = Path(click.prompt(
                'Enter a path to a file that contains a version number '
                "(enter a path of '.' when you're done selecting files)",
                type=click.Path(
                    exists=True,
                    dir_okay=True,
                    file_okay=True,
                    readable=True
                )
            ))

            if version_file_path != Path('.'):
                user_supplied_versioned_file_paths.append(version_file_path)

        bumpversion = BumpVersion(
            current_version=project_settings.repository.latest_version,
            version_files_to_replace=user_supplied_versioned_file_paths,
        )
        bumpversion.write_to_file(bumpversion_config_path)
    else:
        raise NotImplemented('')

    return bumpversion


def read_user_choices(var_name, options):
    """Prompt the user to choose from several options for the given variable.

    # cookiecutter/cookiecutter/prompt.py
    The first item will be returned if no input happens.

    :param str var_name: Variable as specified in the context
    :param list options: Sequence of options that are available to select from
    :return: Exactly one item of ``options`` that has been chosen by the user
    """
    raise NotImplementedError()
    #

    # Please see http://click.pocoo.org/4/api/#click.prompt
    if not isinstance(options, list):
        raise TypeError

    if not options:
        raise ValueError

    choice_map = OrderedDict(
        (u'{}'.format(i), value) for i, value in enumerate(options, 1)
    )
    choices = choice_map.keys()
    default = u'1'

    choice_lines = [u'{} - {}'.format(*c) for c in choice_map.items()]
    prompt = u'\n'.join((
        u'Select {}:'.format(var_name),
        u'\n'.join(choice_lines),
        u'Choose from {}'.format(u', '.join(choices))
    ))

    # TODO: multi-select
    user_choice = click.prompt(
        prompt, type=click.Choice(choices), default=default
    )
    return choice_map[user_choice]

DEFAULTS = {
    'changelog': 'CHANGELOG.md',
    'readme': 'README.md',
    'github_auth_token': None,
}


class Config:
    test_command = None
    pypi = None
    skip_changelog = None
    changelog_content = None
    repo = None

    def __init__(self, module_name, dry_run, debug, no_input, requirements,
                 new_version, current_version, repo_url, version_prefix):
        self.module_name = module_name
        # module_name => project_name => curdir
        self.dry_run = dry_run
        self.debug = debug
        self.no_input = no_input
        self.requirements = requirements
        self.new_version = (
            version_prefix + new_version
            if version_prefix
            else new_version
        )
        self.current_version = current_version


def project_config():
    """Deprecated"""
    project_name = curdir

    config_path = Path(join(project_name, PROJECT_CONFIG_FILE))

    if not exists(config_path):
        store_settings(DEFAULTS.copy())
        return DEFAULTS

    return toml.load(io.open(config_path)) or {}


def store_settings(settings):
    pass

