
import pytest
from mock import MagicMock

from switchboard.device import get_device_suffix, RESTDevice, SwitchboardDevice

def test_get_device_suffix():
    test_cases = [  [ 'name_without_fullstop',  None ],
                    [ 'bad_suffix.a',           None ],
                    [ 'input.i',                'i' ],
                    [ 'output.o',               'o' ],
                    [ 'inout.io',               'io' ],
                    [ 'mult.iple.fullstops.i',  'i' ],
                    [ 'bad.mult.fullstops.abc', None ],
                    [ 'signal.s',               's' ] ]

    for test_case in test_cases:
        assert get_device_suffix(test_case[0]) == test_case[1]


def test_input_signal():
    device = SwitchboardDevice('input.i')
    input_signal = device.get_input_signal()
    device.value = 10.0
    device.error = 'Fatal error'

    assert input_signal.get_value() == 10.0
    assert input_signal.has_changed() == True
    assert input_signal.get_error() == 'Fatal error'


def test_output_signal():
    device = SwitchboardDevice('output.o')
    output_signal = device.get_output_signal()

    with pytest.raises(NotImplementedError):
        output_signal.set_value(10.0)


def test_rest_device_bad_name():
    bad_names = [ 'test', 'test.a', 'test.s', 'test_i' ]
    for bad_name in bad_names:
        with pytest.raises(Exception):
            RESTDevice({ 'name': bad_name, 'readable': True, 'writeable': True },
                    'http://test_url',
                    None)


def test_rest_input_device():
    with pytest.raises(Exception):
        RESTDevice({ 'name': 'input.i', 'readable': False, 'writeable': True },
                'http://test_url',
                None)

    dev = RESTDevice({ 'name': 'input.i', 'readable': True, 'writeable': False },
            'http://test_url',
            None)

    assert(dev.is_input == True)
    assert(hasattr(dev, 'input_signal'))
    assert(dev.is_output == False)
    assert(not hasattr(dev, 'output_signal'))

    # This is an input device only that should not have the set_value
    # method implemented
    with pytest.raises(NotImplementedError):
        dev.set_value(123)


def test_rest_output_device():
    callback = MagicMock()
    with pytest.raises(Exception):
        RESTDevice({ 'name': 'output.o', 'readable': False, 'writeable': False },
                'http://test_url',
                callback)

    dev = RESTDevice({ 'name': 'output.o', 'readable': False, 'writeable': True },
            'http://test_url',
            callback)

    assert(dev.is_input == False)
    assert(not hasattr(dev, 'input_signal'))
    assert(dev.is_output == True)
    assert(hasattr(dev, 'output_signal'))
    dev.output_signal.set_value(456)
    assert(dev.last_set_value == 456)
    callback.assert_called_with(dev, 456)


def test_rest_io_device():
    callback = MagicMock()
    dev = RESTDevice({ 'name': 'output.io', 'readable': True, 'writeable': True },
            'http://test_url',
            callback)

    assert(dev.is_input == True)
    assert(hasattr(dev, 'input_signal'))
    assert(dev.is_output == True)
    assert(hasattr(dev, 'output_signal'))
    assert(hasattr(dev, 'set_value'))


