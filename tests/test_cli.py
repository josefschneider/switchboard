
import io
import sys
from threading import Thread, Lock

import pytest
from mock import MagicMock

from cli.ws_cli import SwitchboardWSCli


class MockSwitchboardClient:
    def __init__(self):
        self.lock = Lock()
        self.run_ws_client = MagicMock()

        self.swb_config = {
            'poll_period': '1.0',
            'clients': {
                'client1': {
                    'url': 'http://localhost:51000'
                },
                'client2': {
                    'url': 'http://localhost:51001'
                }
            },
            'modules': [
                'test_module.module'
            ],
            'ws_port': 44371,
            'apps': {
                'swb_system_info': {
                    'command': 'swb_system_info --client_port 44573',
                    'client_port': 44573,
                    'client_alias': 'sys'
                }
            },
            'running': True
        }


@pytest.fixture(scope='module')
def cli_fixture(request):
    class CliTestFixture:
        def __init__(self):
            print('Creating fixture')
            self.cli = SwitchboardWSCli(io.StringIO(), io.StringIO())
            self.cli.ws_client = MockSwitchboardClient()
            self.config = self.cli.ws_client.swb_config

        def write(self, command):
            self.cli.cmdqueue.append(command)

    f = CliTestFixture()
    f.cli.update_current_config(f.config)

    thread = Thread(target=f.cli.run, kwargs={'host': 0, 'port': 0})
    thread.daemon = True
    thread.start()

    request.addfinalizer(lambda f=f: f.write('exit'))
    return f


COMMANDS = [
        {  'name': 'addclient',     'args': ['localhost:51000', 'client1'] },
        {  'name': 'addmodule',     'args': ['test_module.module'] },
        {  'name': 'disable',       'args': ['test_module.module'] },
        {  'name': 'enable',        'args': ['test_module.module'] },
        {  'name': 'get',           'args': ['sys.core_count.i'] },
        {  'name': 'killapp',       'args': ['swb_system_info'] },
        {  'name': 'launchapp',     'args': ['swb_system_info'] },
        {  'name': 'list',          'args': ['apps'] },
        {  'name': 'list',          'args': ['clients'] },
        {  'name': 'list',          'args': ['devices'] },
        {  'name': 'list',          'args': ['modules'] },
        {  'name': 'list',          'args': ['values'] },
        {  'name': 'remove',        'args': ['client1'] },
        {  'name': 'set',           'args': ['poll_period'] },
        {  'name': 'start',         'args': [] },
        {  'name': 'stop',          'args': [] },
        {  'name': 'updateclient',  'args': ['client1'] },
]

def test_commands(cli_fixture):
    for command in COMMANDS:
        cli_fixture.write()
