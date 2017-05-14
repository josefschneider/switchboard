
import sys
import argparse
import json

from copy import deepcopy

from switchboard.client import SwitchboardClient
from switchboard.iodata import IODataClient


def check_port_arg(args, port_name):
    if hasattr(args, port_name):
        port = getattr(args, port_name)
        if port:
            if port.isdigit() and int(port) > 0 and int(port) < 65536:
                return True
            print('Incorrect value for port "--{}", must be integer > 0 and < 65536'.format(port_name))
        else:
            print('Error: value for port "--{}" not defined'.format(port_name))
    else:
        print('Error: unknown argument "--{}"'.format(port_name))
    return False


class App(object):
    def __init__(self, configs={}, **kwargs):
        arguments = deepcopy(configs)
        arguments['getconf'] = {
            'args': ['--getconf', '-gc'],
            'kwargs': {
                'help': 'Get a JSON representation of the application config options',
                'action': 'store_true'
            }
        }

        arg_parser = argparse.ArgumentParser()
        for argument in arguments.values():
            arg_parser.add_argument(*argument['args'], **argument['kwargs'])

        self.args = arg_parser.parse_args()

        if self.args.getconf:
            print('{}'.format(json.dumps(configs)))
            sys.exit(0)


class ClientApp(SwitchboardClient, App):
    def __init__(self, configs={}, **kwargs):
        configs['Client port'] = {
            'args': ['--client_port', '-cp'],
            'kwargs': { 'help': 'Switchboard client listening port' }
        }

        super(ClientApp, self).__init__(**kwargs, configs=configs)

        if not check_port_arg(self.args, 'client_port'):
            sys.exit(1)

    def run(self):
        try:
            self.run_client(int(self.args.client_port))
        except KeyboardInterrupt:
            sys.exit(0)


class IODataApp(IODataClient, App):
    def __init__(self, iodata_agent, configs={}, **kwargs):
        configs['IOData port'] = {
            'args': ['--iodata_port', '-ip'],
            'kwargs': { 'help': 'IOData server port to connect to' }
        }
        configs['IOData host'] = {
            'args': ['--iodata_host', '-ih'],
            'kwargs': { 'help': 'IOData server host to connect to' }
        }
        configs['autokill'] = {
            'args': ['--autokill', '-a'],
            'kwargs': {
                'help': 'Automatically kill this application if Switchboard disconnects',
                'action': 'store_true'
            }
        }

        super(IODataApp, self).__init__(**kwargs, configs=configs, iodata_agent=iodata_agent)

        if not check_port_arg(self.args, 'iodata_port'):
            sys.exit(1)

    def run(self):
        try:
            self.run_iodata(
                self.args.iodata_host,
                int(self.args.iodata_port),
                self.args.autokill)
        except KeyboardInterrupt:
            sys.exit(0)


class ClientAndIODataApp(ClientApp, IODataApp):
    def __init__(self, **kwargs):
        super(ClientAndIODataApp, self).__init__(**kwargs)

    def run(self):
        try:
            thread = Thread(target=self.run_client(int(self.args.client_port)))
            thread.daemon = True
            thread.start()

            self.run_iodata(int(self.args.iodata_port))
        except KeyboardInterrupt:
            sys.exit(0)
