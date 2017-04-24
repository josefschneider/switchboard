
import sys

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


tests_require = [
    'pytest',
    'mock'
]


install_requires = [
    'requests',
    'bottle',
    'termcolor'
]


setup(
    name='switchboard',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'switchboard = switchboard.__main__:main',
        ],
    },
    tests_require=tests_require,
    install_requires=install_requires,
    cmdclass={'test': PyTest}
)
