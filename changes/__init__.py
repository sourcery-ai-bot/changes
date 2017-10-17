"""Generates a github changelog, tags and uploads your python library"""

__version__ = '0.7.0'
__url__ = 'https://github.com/michaeljoseph/changes'
__author__ = 'Michael Joseph'
__email__ = 'michaeljoseph@gmail.com'


from .cli import main  # noqa

settings = None
project_settings = None
environment = None