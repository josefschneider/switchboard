
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
                'client1': { 'url': 'http://localhost:51000' }
            },
            'modules': { 'test_module.module': 'enabled' },
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
        self.swb_clients = {
            'sys': {
                'client_url': 'http://localhost:54955',
                'client_alias': 'sys',
                'devices': [
                    {
                        'last_update_time': '2017-12-10 12:26:58.234680',
                        'name': 'sys.core_count.i',
                        'value': 4,
                        'last_set_value': None
                    }
                ]
            }
        }
        self.devices = { 'sys.core_count.i': self.swb_clients['sys']['devices'][0] }

    def send(self, command, args=[]):
        pass


@pytest.fixture(scope='module')
def cli_fixture(request):
    class CliTestFixture:
        def __init__(self):
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


def test_check_argument_count():
    do_f1 = MagicMock()
    do_f2 = MagicMock()
    do_f1.__name__ = 'do_f1'
    do_f2.__name__ = 'do_f2'

    class DerivedWSCli(SwitchboardWSCli):
        def __init__(self):
            self.test_func_1_arg = SwitchboardWSCli.check_argument_count(1)(do_f1)
            self.test_func_2_or_3_args = SwitchboardWSCli.check_argument_count(2, 3)(do_f2)

    cli = DerivedWSCli()
    # Test incorrect number of arguments
    cli.test_func_1_arg(cli, '')
    cli.test_func_1_arg(cli, 'arg1 arg2')
    cli.test_func_2_or_3_args(cli, 'arg1')
    cli.test_func_2_or_3_args(cli, 'arg1 arg2 arg3 arg4')
    do_f1.assert_not_called()
    do_f2.assert_not_called()

    # Now test with correct number of arguments and make sure the functions have been called
    cli.test_func_1_arg(cli, 'arg1')
    cli.test_func_2_or_3_args(cli, 'arg1 arg2')
    cli.test_func_2_or_3_args(cli, 'arg1 arg2 arg3')
    do_f1.assert_called_once()
    do_f2.call_count == 2


COMMANDS = [
    {  'name': 'addclient',     'args': ['localhost:51000', 'client1'] },
    {  'name': 'addclient',     'args': ['localhost:51000', 'client1', '1.3'] },
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
    {  'name': 'set',           'args': ['poll_period', '2'] },
    {  'name': 'start',         'args': [] },
    {  'name': 'stop',          'args': [] },
    {  'name': 'updateclient',  'args': ['client1'] },
    {  'name': 'updateclient',  'args': ['client1', '1.3'] },
]

def test_commands(cli_fixture):
    for command in COMMANDS:
        text_entry = ' '.join([command['name'], ' '.join(command['args'])])
        cli_fixture.write(text_entry)
