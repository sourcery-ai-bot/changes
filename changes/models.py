import re
import shlex

import attr
import semantic_version
import uritemplate
import requests
import giturlparse
from plumbum.cmd import git

MERGED_PULL_REQUEST = re.compile(
    r'^([0-9a-f]{5,40}) Merge pull request #(\w+)'
)

GITHUB_PULL_REQUEST_API = (
    'https://api.github.com/repos{/owner}{/repo}/issues{/number}'
)


def changes_to_release_type(repository):
    pull_request_labels = set()
    changes = repository.changes_since_last_version

    for change in changes:
        for label in change.labels:
            pull_request_labels.add(label)

    change_descriptions = [
        '\n'.join([change.title, change.description]) for change in changes
    ]

    current_version = repository.latest_version
    if 'BREAKING CHANGE' in change_descriptions:
        return 'major', Release.BREAKING_CHANGE, current_version.next_major()
    elif 'enhancement' in pull_request_labels:
        return 'minor', Release.FEATURE, current_version.next_minor()
    elif 'bug' in pull_request_labels:
        return 'patch', Release.FIX, current_version.next_patch()
    else:
        return None, Release.NO_CHANGE, current_version


class Release:
    NO_CHANGE = 'nochanges'
    BREAKING_CHANGE = 'breaking'
    FEATURE = 'feature'
    FIX = 'fix'

    version = '<current_version>'
    name = None
    title = "{formatted string}"
    title_format = ''
    description = "(optional)Release description"
    changes = []

    @property
    def title(self):
        return

@attr.s
class PullRequest:
    number = attr.ib()
    title = attr.ib()
    description = attr.ib()
    # default is 'body' key
    author = attr.ib()
    labels = attr.ib(default=attr.Factory(list))

    @classmethod
    def from_github(cls, api_response):
        return PullRequest(
            number = api_response['number'],
            title = api_response['title'],
            description = api_response['body'],
            author = api_response['user']['login'],
            labels = [
                label['name']
                for label in api_response['labels']
                # label['colour'] => https://gist.github.com/MicahElliott/719710
            ],
            # labels need a description => map for default github tags
        )


@attr.s
class GitRepository:
    VERSION_ZERO = semantic_version.Version('0.0.0')
    # TODO: handle multiple remotes (cookiecutter [non-owner maintainer])
    REMOTE_NAME = 'origin'

    auth_token = attr.ib(default=None)

    @property
    def parsed_repo(self):
        return giturlparse.parse(self.remote_url)

    @property
    def remote_url(self):
        return git(shlex.split('config --get remote.{}.url'.format(
            self.REMOTE_NAME
        )))

    @property
    def commit_history(self):
        return [
            commit_message
            for commit_message in git(shlex.split(
                'log --oneline --no-color'
            )).split('\n')
            if commit_message
        ]

    @property
    def first_commit_sha(self):
        return git(
            'rev-list', '--max-parents=0', 'HEAD'
        )

    @property
    def tags(self):
        return git(shlex.split('tag --list')).split('\n')

    @property
    def versions(self):
        versions = []
        for tag in self.tags:
            try:
                versions.append(semantic_version.Version(tag))
            except ValueError:
                pass
        return versions

    @property
    def latest_version(self) -> semantic_version.Version:
        return max(self.versions) if self.versions else self.VERSION_ZERO

    def merges_since(self, version=None):
        if version == semantic_version.Version('0.0.0'):
            version = self.first_commit_sha

        revision_range = ' {}..HEAD'.format(version) if version else ''

        merge_commits = git(shlex.split(
            'log --oneline --merges --no-color{}'.format(revision_range)
        )).split('\n')
        return merge_commits

    # TODO: pull_requests_since(version=None)
    @property
    def changes_since_last_version(self):
        pull_requests = []

        for index, commit_msg in enumerate(self.merges_since(self.latest_version)):
            matches = MERGED_PULL_REQUEST.findall(commit_msg)

            if matches:
                _, pull_request_number = matches[0]

                pull_requests.append(PullRequest.from_github(
                    self.github_pull_request(pull_request_number)
                ))
        return pull_requests

    def github_labels(self):
        # GET /repos/:owner/:repo/labels
        """
        [
          {
            "id": 208045946,
            "url": "https://api.github.com/repos/octocat/Hello-World/labels/bug",
            "name": "bug",
            "color": "f29513",
            "default": true
          }
        ]
        """
        pass

    def github_pull_request(self, pr_num):
        pull_request_api_url = uritemplate.expand(
            GITHUB_PULL_REQUEST_API,
            dict(
                owner=self.owner,
                repo=self.repo,
                number=pr_num
            ),
        )

        return requests.get(
            pull_request_api_url,
            headers={
                'Authorization': 'token {}'.format(self.auth_token)
            },
        ).json()

    @property
    def repo(self):
        return self.parsed_repo.repo

    @property
    def owner(self):
        return self.parsed_repo.owner

    @property
    def github(self):
        return self.parsed_repo.github

    @property
    def bitbucket(self):
        return self.parsed_repo.bitbucket
