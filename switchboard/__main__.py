#!/usr/bin/env python
'''The main entry point. Invoke as `switchboard' or `python -m switchboard'.

'''

import argparse
import sys

from switchboard.config import SwitchboardConfig
from switchboard.engine import SwitchboardEngine
from switchboard.cli import SwitchboardCli
from switchboard.iodata import IOData
from switchboard.websocket_server import WebsocketServer


def main():
    try:
        iodata = IOData()

        swb_config = SwitchboardConfig()
        swb = SwitchboardEngine(swb_config, iodata)
        cli = SwitchboardCli(swb, swb_config)

        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('-c', '--config', help='specify .json config file')
        arg_parser.add_argument('-p', '--port', help='dashbord port')
        args = arg_parser.parse_args()

        if args.port:
            iodata.add_consumer(WebsocketServer(args.port))

        if args.config:
            swb_config.load_config(args.config)
            swb.init_config()

        sys.exit(cli.run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
