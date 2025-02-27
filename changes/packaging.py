import logging
from pathlib import Path
from shutil import rmtree

from changes import shell, util, venv, verification

log = logging.getLogger(__name__)


def build_distributions(context):
    """Builds package distributions"""
    rmtree('dist', ignore_errors=True)

    build_package_command = 'python setup.py clean sdist bdist_wheel'
    result = shell.dry_run(build_package_command, context.dry_run)
    packages = "nothing" if context.dry_run else Path('dist').files()

    if not result:
        raise Exception(f'Error building packages: {result}')
    else:
        log.info(f"Built {', '.join(packages)}")
    return packages


# tox
def install_package(context):
    """Attempts to install the sdist and wheel."""

    if not context.dry_run and build_distributions(context):
        with util.mktmpdir() as tmp_dir:
            venv.create_venv(tmp_dir=tmp_dir)
            for distribution in Path('dist').files():
                try:
                    venv.install(distribution, tmp_dir)
                    log.info('Successfully installed %s', distribution)
                    if context.test_command and verification.run_test_command(context):
                        log.info(
                            'Successfully ran test command: %s', context.test_command
                        )
                except Exception as e:
                    raise Exception(f'Error installing distribution {distribution}', e)
    else:
        log.info('Dry run, skipping installation')


# twine
def upload_package(context):
    """Uploads your project packages to pypi with twine."""

    if not context.dry_run and build_distributions(context):
        upload_args = 'twine upload ' + ' '.join(Path('dist').files())
        if context.pypi:
            upload_args += f' -r {context.pypi}'

        upload_result = shell.dry_run(upload_args, context.dry_run)
        if not context.dry_run and not upload_result:
            raise Exception(f'Error uploading: {upload_result}')
        else:
            log.info(
                'Successfully uploaded %s:%s', context.module_name, context.new_version
            )
    else:
        log.info('Dry run, skipping package upload')


def install_from_pypi(context):
    """Attempts to install your package from pypi."""

    tmp_dir = venv.create_venv()
    install_cmd = f'{tmp_dir}/bin/pip install {context.module_name}'

    package_index = 'pypi'
    if context.pypi:
        install_cmd += f'-i {context.pypi}'
        package_index = context.pypi

    try:
        result = shell.dry_run(install_cmd, context.dry_run)
        if not context.dry_run and not result:
            log.error(
                'Failed to install %s from %s', context.module_name, package_index
            )
        else:
            log.info(
                'Successfully installed %s from %s', context.module_name, package_index
            )

    except Exception as e:
        error_msg = f'Error installing {context.module_name} from {package_index}'
        log.exception(error_msg)
        raise Exception(error_msg, e)
