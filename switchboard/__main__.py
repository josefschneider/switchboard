#! /usr/bin/env python
"""The main entry point. Invoke as `switchboard' or `python -m switchboard'.

"""

import argparse
import sys

from switchboard.config import SwitchboardConfig
from switchboard.switchboard import SwitchboardEngine
from switchboard.cli import SwitchboardCli


def main():
    try:
        swb_config = SwitchboardConfig()
        swb = SwitchboardEngine(swb_config)
        cli = SwitchboardCli(swb, swb_config)

        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('-c', '--config', help='specify .json config file')
        args = arg_parser.parse_args()

        if args.config:
            swb_config.load_config(args.config)
            swb.init_config()

        sys.exit(cli.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
