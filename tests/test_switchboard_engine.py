
from copy import deepcopy

import pytest
import time
from threading import Thread
from mock import MagicMock

from switchboard.engine import SwitchboardEngine, EngineError, _Client
from switchboard.module import SwitchboardModule

class TimeElapsed:
    def __enter__(self):
        self.start_time = time.time()

    def __exit__(self, type, value, traceback):
        self.elapsed = time.time() - self.start_time


class EngineTest(SwitchboardEngine):
    def __init__(self):
        super(EngineTest, self).__init__(self, self)
        self.loop_count = 0
        self.configs = { 'poll_period': 0.05 }
        self.running = True
        self.modules = { 'mod1': MagicMock(), 'mod2': MagicMock() }


def test_terminate():
    def loop():
        eng.loop_count += 1
        time.sleep(0.05)
        if eng.loop_count > 6: raise KeyboardInterrupt

    eng = EngineTest()
    eng.switchboard_loop = loop

    # Make sure that setting terminate stops the engine
    eng.start()
    time.sleep(0.12)
    eng.terminate = True
    eng._swb_thread.join()
    assert eng.loop_count == 3

    # Same with KeyboardInterrupt
    eng.terminate = False
    eng.start()
    time.sleep(0.22)
    eng._swb_thread.join()
    assert eng.loop_count == 7


def TestSwitchboardLoop():

    @pytest.fixture
    def engine():
        eng = EngineTest()
        eng._update_devices_values = MagicMock()
        eng.take_snapshot = MagicMock()
        return eng

    def test_loop_no_delay(self, eng):
        ''' Run a standard loop with no delay '''
        with TimeElapsed() as t:
            eng.switchboard_loop()

        assert t.elapsed < 0.01
        eng._update_devices_values.assert_called_once()
        eng.modules['mod1'].assert_called_once()
        eng.modules['mod2'].assert_called_once()
        eng.take_snapshot.assert_called_once()

    def test_full_delay(self, eng):
        ''' Run a loop with delay and modules disabled '''
        eng.prev_cycle_time = time.time()
        eng.running = False
        with TimeElapsed() as t:
            eng.switchboard_loop()

        assert t.elapsed > 0.05 and t.elapsed < 0.06
        eng._update_devices_values.assert_called_once()
        eng.modules['mod1'].assert_not_called()
        eng.modules['mod2'].assert_not_called()
        eng.take_snapshot.assert_called_once()

    def test_lock(self, eng):
        ''' Test the locking logic '''
        def block():
            with eng.lock:
                time.sleep(0.05)
                eng._update_devices_values.assert_not_called()
        Thread(target=block).start()

        with TimeElapsed() as t:
            eng.switchboard_loop()

        assert t.elapsed > 0.05 and t.elapsed < 0.06
        eng._update_devices_values.assert_called_once()


def test_add_and_update_client():
    ''' Ensure various checks are performed when adding or updating clients '''
    eng = EngineTest()
    eng._upsert_client = MagicMock()

    eng.clients = { 'client1': None }
    with pytest.raises(EngineError):
        eng.add_client('http://abc', 'client1')

    eng.clients = { 'client1': _Client('http://abc', None, None, None) }
    with pytest.raises(EngineError):
        eng.add_client('http://abc', 'client2')

    with pytest.raises(EngineError):
        eng.update_client('client3')

    eng._upsert_client.assert_not_called()


def test_upsert_client():
    # TODO
    pass


def test_get_modules_using_client():
    eng = EngineTest()

    @SwitchboardModule(['other_in'], ['out'])
    def uses_out(inp, out): pass

    @SwitchboardModule(['in'], ['other_out'])
    def uses_in(inp, out): pass

    @SwitchboardModule(['other_in'], ['other_out'])
    def uses_nothing(inp, out): pass

    eng.clients = { 'client1': _Client(None, None, { 'in': None, 'out': None }, None) }
    eng.modules = { 'uses_out': uses_out,
                    'uses_in': uses_in,
                    'uses_nothing': uses_nothing }

    modules_using_client = eng.get_modules_using_client('client1')
    assert modules_using_client == set(['uses_in', 'uses_out'])
