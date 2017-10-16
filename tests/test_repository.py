from plumbum.cmd import git
from semantic_version import Version

from changes import models


def test_repository_parses_remote_url(git_repo):
    repository = models.GitRepository()
    assert 'test_app' == repository.repo
    assert 'michaeljoseph' == repository.owner
    assert repository.github


def test_repository_parses_versions(git_repo_with_merge_commit):
    repository = models.GitRepository()

    v1 = Version('0.0.1')

    assert [v1] == repository.versions

    assert v1 == repository.latest_version


def test_latest_version_unreleased(git_repo):
    repository = models.GitRepository()

    assert 0 == len(repository.versions)

    assert models.GitRepository.VERSION_ZERO == repository.latest_version


def test_latest_version(git_repo_with_merge_commit):
    git('tag', '0.0.2')
    git('tag', '0.0.3')

    repository = models.GitRepository()

    expected_versions = [
        Version('0.0.1'),
        Version('0.0.2'),
        Version('0.0.3'),
    ]
    assert expected_versions == repository.versions

    assert Version('0.0.3') == repository.latest_version