#!/usr/bin/env python

import argparse

from cli.ws_cli import SwitchboardWSCli
from switchboard.ws_ctrl import WSCtrlClient

def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-p', '--port', help='Switchboard control port to connect to', default='41200')
    arg_parser.add_argument('--host', help='Switchboard control host to connect to', default='localhost')
    args = arg_parser.parse_args()
    cli = SwitchboardWSCli()
    cli.ws_client = WSCtrlClient(ws_handler=cli)
    cli.run(args.host, args.port)

if __name__ == '__main__':
    main()
