
import io
from threading import Thread, Lock

import pytest
from mock import MagicMock

from cli.ws_cli import SwitchboardWSCli


class MockSwitchboardClient:
    def __init__(self):
        self.lock = Lock()
        self.run_ws_client = MagicMock()
        self.swb_config = {} # TODO: prepopulate with iodata and swb configs


class StaticTestFixture:
    def __init__(self):
        cli = SwitchboardWSCli()
        cli.ws_client = MockSwitchboardClient()
