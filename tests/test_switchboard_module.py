
from copy import deepcopy

import pytest
from mock import MagicMock

from switchboard.module import SwitchboardModule, ModuleError
from switchboard.device import RESTDevice, get_device_suffix


def set_value_callback(device, value):
    set_value_callback.values[device.name] = value
set_value_callback.values = {}

def dic(name):
    ''' Creates the json device definitions based on the device name '''
    d = { 'name': name }
    d['readable'] = True if 'i' in get_device_suffix(name) else False
    d['writeable'] = True if 'o' in get_device_suffix(name) else False
    return d


class ModuleTestEnv:
    def __init__(self):
        self.module_class = self.DefaultModule.module_class
        self.module_class.enabled = True

        self.device_list = {
                'input1.io':    RESTDevice(dic('input1.io'), 'http://url', set_value_callback),
                'input2.i':     RESTDevice(dic('input2.i'), 'http://url', set_value_callback),
                'output1.o':    RESTDevice(dic('output1.o'), 'http://url', set_value_callback),
                'output2.io':   RESTDevice(dic('output2.io'), 'http://url', set_value_callback)
        }

    @SwitchboardModule(
            inputs = [ 'input1.io', 'input2.i' ],
            outputs = { 'output1.o': 1, 'output2.io': None })
    def DefaultModule(self, in1, in2, out1, out2):
        out1.set_value(in1.get_value() - in2.get_value())
        out2.set_value(in1.get_value() + in2.get_value())



def test_class_module_init():
    ''' Make sure the decorator is doing everything it's supposed to '''
    test_env = ModuleTestEnv()
    module = test_env.module_class

    assert module.inputs == [ 'input1.io', 'input2.i' ]
    assert module.outputs == { 'output1.o': 1, 'output2.io': None }
    assert module.name == 'DefaultModule'
    assert module.is_class_method == True


def test_standalone_module_init():
    ''' Make sure the decorator is doing everything it's supposed to '''
    @SwitchboardModule(
            inputs = [ 'input1.io', 'input2.i' ],
            outputs = { 'output1.o': 1, 'output2.io': 2 },
            static_variables = { 'abc': 123 } )
    def StandaloneModule(in1, in2, out1, out2):
        pass

    module = StandaloneModule.module_class

    assert module.inputs == [ 'input1.io', 'input2.i' ]
    assert module.outputs == { 'output1.o': 1, 'output2.io': 2 }
    assert module.name == 'StandaloneModule'
    assert hasattr(StandaloneModule, 'abc')
    assert StandaloneModule.abc == 123
    assert module.is_class_method == False


def test_switchboard_class_module_with_statics_error():
    ''' A class switchboard module is not allowed to have statics '''
    with pytest.raises(ModuleError):
        class InvalidModule:
            @SwitchboardModule(inputs = [], outputs = [], static_variables = { 'abc': 101 })
            def StandaloneModule(self):
                pass


def test_create_argument_list_success():
    test_env = ModuleTestEnv()
    test_env.module_class.create_argument_list(test_env.device_list)

    assert test_env.module_class.enabled == True
    assert test_env.module_class.error == None

    # We should be able to call create_argument_list multiple times
    # without errors
    test_env.module_class.create_argument_list(test_env.device_list)

    assert test_env.module_class.enabled == True
    assert test_env.module_class.error == None


def test_create_argument_list_missing_input_device_error():
    test_env = ModuleTestEnv()
    del test_env.device_list['input1.io']

    with pytest.raises(ModuleError):
        test_env.module_class.create_argument_list(test_env.device_list)

    assert test_env.module_class.enabled == False
    assert test_env.module_class.error != None


def test_create_argument_list_missing_output_device_error():
    test_env = ModuleTestEnv()
    del test_env.device_list['output2.io']

    with pytest.raises(ModuleError):
        test_env.module_class.create_argument_list(test_env.device_list)

    assert test_env.module_class.enabled == False
    assert test_env.module_class.error != None


def test_create_argument_list_not_an_input_error():
    @SwitchboardModule(inputs = [ 'output1.o' ])
    def ClashingTestModule(input):
        pass

    module_class = ClashingTestModule.module_class
    with pytest.raises(ModuleError):
        module_class.create_argument_list(ModuleTestEnv().device_list)

    assert module_class.enabled == False
    assert module_class.error != None


def test_create_argument_list_not_an_output_error():
    @SwitchboardModule(outputs = { 'input2.i': 1 })
    def ClashingTestModule(out):
        pass

    module_class = ClashingTestModule.module_class
    with pytest.raises(ModuleError):
        module_class.create_argument_list(ModuleTestEnv().device_list)

    assert module_class.enabled == False
    assert module_class.error != None


def test_create_argument_list_multiple_drivers_error():
    test_env = ModuleTestEnv()
    test_env.module_class.create_argument_list(test_env.device_list)

    @SwitchboardModule(outputs = { 'output1.o': 1 })
    def ClashingTestModule(out):
        pass

    # Because ClashingTestModule also drives output1.o, creating the
    # argument list should cause an error
    module_class = ClashingTestModule.module_class
    module_class.enabled = True
    with pytest.raises(ModuleError):
        module_class.create_argument_list(test_env.device_list)

    assert test_env.module_class.enabled == True
    assert module_class.enabled == False
    assert module_class.error != None


def test_check_module_io_error():
    test_env = ModuleTestEnv()
    test_env.module_class.create_argument_list(test_env.device_list)

    assert test_env.module_class.check_module_io_error() == False

    test_env.device_list['output1.o'].error = 'Some error'
    assert test_env.module_class.check_module_io_error() == True
    assert test_env.module_class.error != None

    test_env.device_list['output1.o'].error = 'Some other error'
    assert test_env.module_class.check_module_io_error() == True
    assert test_env.module_class.error != None

    test_env.device_list['output1.o'].error = None
    assert test_env.module_class.check_module_io_error() == False
    assert test_env.module_class.error == None


def test_call_swtchboard_class_module():
    test_env = ModuleTestEnv()
    test_env.module_class.create_argument_list(test_env.device_list)

    test_env.device_list['input1.io'].update_value(10)
    test_env.device_list['input2.i'].update_value(5)

    test_env.DefaultModule()

    assert set_value_callback.values['output1.o'] == 5
    assert set_value_callback.values['output2.io'] == 15


def test_call_swtchboard_io_error():
    test_env = ModuleTestEnv()
    test_env.module_class.create_argument_list(test_env.device_list)

    test_env.device_list['input1.io'].update_value(10)
    test_env.device_list['input2.i'].update_value(5)

    test_env.DefaultModule()
    assert set_value_callback.values['output1.o'] == 5
    assert set_value_callback.values['output2.io'] == 15

    test_env.device_list['input2.i'].error = 'Some error has occurred'

    test_env.DefaultModule()
    assert set_value_callback.values['output1.o'] == 1      # Set to error value
    assert set_value_callback.values['output2.io'] == 15    # Unchanged as error value is None

    test_env.device_list['input2.i'].error = None

    test_env.DefaultModule()
    assert set_value_callback.values['output1.o'] == 5
    assert set_value_callback.values['output2.io'] == 15


def test_call_swtchboard_standalone_module():
    test_env = ModuleTestEnv()

    @SwitchboardModule(
            inputs = [ 'input1.io', 'input2.i' ],
            outputs = { 'output1.o': 1 },
            static_variables = { 'abc': 101 })
    def StandaloneModule(in1, in2, out):
        out.set_value(in1.get_value() + in2.get_value() + StandaloneModule.abc)

    module_class = StandaloneModule.module_class
    module_class.create_argument_list(test_env.device_list)
    module_class.enabled = True

    test_env.device_list['input1.io'].update_value(10)
    test_env.device_list['input2.i'].update_value(5)

    StandaloneModule()

    assert set_value_callback.values['output1.o'] == 10 + 5 + 101

