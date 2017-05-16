#!/usr/bin/env python
'''The main entry point. Invoke as `switchboard' or `python -m switchboard'.

'''

import argparse
import sys

from switchboard.config import SwitchboardConfig
from switchboard.iodata import IOData
from switchboard.engine import SwitchboardEngine
from switchboard.app_manager import AppManager
from switchboard.cli import SwitchboardCli


def main():
    try:
        swb_config = SwitchboardConfig()
        iodata = IOData(swb_config)
        swb = SwitchboardEngine(swb_config, iodata)

        with AppManager(swb_config, swb) as app_manager:
            cli = SwitchboardCli(swb, swb_config, iodata, app_manager)

            arg_parser = argparse.ArgumentParser()
            arg_parser.add_argument('-c', '--config', help='specify .json config file')
            args = arg_parser.parse_args()

            if args.config:
                swb_config.load_config(args.config)
                iodata.init_config()
                swb.init_config()

                # Only once everything has been setup can we initialise the app manager
                app_manager.init_config()
            else:
                swb_config.initial_setup()

            swb.start()
            sys.exit(cli.run())

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
