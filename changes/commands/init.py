import changes
from changes.models.repository import GitHubRepository
from ..config import Project, Changes


def init():
    """
    Detects, prompts and initialises the project.

    Stores project and tool configuration in the `changes` module.
    """

    # Global changes settings
    changes.settings = Changes.load()

    # Project specific settings
    changes.project_settings = Project.load(
        GitHubRepository(
            auth_token=changes.settings.auth_token
        )
    )
