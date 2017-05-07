
import sys
import os

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    # `$ python setup.py test' installs minimal requirements and runs tests
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = [
            '--doctest-modules', '--verbose',
            './switchboard', './tests'
        ]
        self.test_suite = True

    def run_tests(self):
        import pytest
        sys.exit(pytest.main(self.test_args))


def get_console_scripts():
    console_scripts = [ 'switchboard = switchboard.__main__:main' ]
    setup_py_path = os.path.dirname(os.path.realpath(__file__))
    hosts_dir = setup_py_path + '/swb_clients'

    for root, dirs, filenames in os.walk(hosts_dir):
        for f in filenames:
            if f.startswith('swbc_'):
                swb_client_name = os.path.splitext(f)[0]
                print('Installing {}'.format(swb_client_name))
                console_scripts.append('{0} = swb_clients.{0}:main'.format(swb_client_name))

    return console_scripts


tests_require = [
    'pytest',
    'mock'
]


install_requires = [
    'requests',
    'termcolor',
    'bottle_websocket'
]


setup(
    name='switchboard',
    version='0.1.0',
    packages=find_packages(),
    package_data={ 'switchboard': ['*.html'] },
    entry_points={
        'console_scripts': get_console_scripts(),
    },
    tests_require=tests_require,
    install_requires=install_requires,
    cmdclass={'test': PyTest}
)
