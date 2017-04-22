
import inspect
from functools import wraps

from switchboard.device import SignalDevice, get_device_suffix


class ModuleError(Exception):
    pass


def determine_if_class_method(frames):
    # Bit of a hacky way to determine if the decorated function is
    # defined in a class or is standalone. See:
    # http://stackoverflow.com/questions/8793233/python-can-a-decorator-determine-if-a-function-is-being-defined-inside-a-class
    if len(frames) > 2:
        maybe_class_frame = frames[2]
        statement_list = maybe_class_frame[4]
        if statement_list:
            first_statment = statement_list[0]
            if first_statment.strip().startswith('class '):
                return True

    return False


class SwitchboardModule:
    def __init__(self, inputs=[], outputs={}, static_variables={}):
        # Input and output devices/signals this module uses
        self.inputs = inputs
        self.outputs = outputs
        self.static_variables = static_variables

        # Tuple of devices that will act as arguments to the module
        self._arguments = ()

        # List of lambdas to be called in case of device error
        # This list is used to set outputs to a default state.
        self._call_if_error = []

        self.name = None

        # Modules are never removed, just enabled/disabled
        self.enabled = False

        # Error string that is set if the module can't run
        self.error = None

        # Indicates whether the module has been removed
        self.removed = False

        self.is_class_method = False


    def create_argument_list(self, device_list):
        ''' Associates the module inputs and outputs (as given by the
            decorator) with the actual device instances. If an internal
            switchboard signal is defined it will be created on the spot
            and added to device_list

            Does not change any state if an error occurs '''

        def on_error(msg):
            self.enabled = False
            self.error = msg
            raise ModuleError(msg)

        self._arguments = ()

        for input in self.inputs:
            device = self._get_signal(input, device_list)

            if not device.is_input:
                on_error('Can not use {} as an input to module {} as the device isn\'t readable'.format(input, self.name))

            self._arguments += (device.input_signal, )

        for output, error_value in self.outputs.items():
            device = self._get_signal(output, device_list)

            if not device.is_output:
                on_error('Can not use {} as an output to module {} as the device isn\'t writeable: {}'.format(output, self.name, device))

            output_signal = device.output_signal
            if output_signal.driving_module and output_signal.driving_module != self.name:
                on_error('Cannot drive signal/device {} with module {}. It is already being driven by module {}.'.format(device.name, self.name, output_signal.driving_module))

            self._arguments += (output_signal, )

            if error_value:
                self._call_if_error.append(lambda ev=error_value, os=output_signal: os.set_value(ev))

        # Only assign driving modules once we're sure there are no errors
        for output in self.outputs.keys():
            output_signal = self._get_signal(output, device_list).output_signal
            output_signal.driving_module = self.name


    def _get_signal(self, signal_name, device_list):
        ''' Gets the instance of the device associated with the signal.
            If the signal is internal to the design a SignalDevice is
            automatically created. '''

        if not signal_name in device_list:
            if get_device_suffix(signal_name) == 's':
                print('Creating signal {}'.format(signal_name))
                signal = SignalDevice(signal_name)
                device_list.append(signal)
                return signal
            else:
                self.error = 'Unkown io device {}'.format(signal_name)
                self.enabled = False
                raise ModuleError(self.error)

        return device_list[signal_name]


    def check_module_io_error(self):
        ''' Checks all the devices that are inputs or outputs to the
            module to see if the module may run or not. The first error
            encountered is the one that is reported '''

        for device in self._arguments:
            if device.get_error() and device.get_error() != self.error:
                msg = 'Disabling module {} due to device {} error: {}'.format(
                        self.name, device.get_name(), device.get_error())
                print('Error: ' + msg)
                self.error = device.get_error()
                return True

        if self.error:
            print('Error resolved, re-enabling module {}'.format(self.name))
            self.error = None

        return False


    def set_output_error_values(self):
        ''' Sets all the outputs to their given error value '''
        for error_callback in self._call_if_error:
            error_callback()


    def __call__(self, f):
        @wraps(f)
        def wrapped_func(*args):
            # *args is used in case this is a class method, in which
            # case 'self' needs to be passed as the first argument
            assert len(args) <= 1

            if self.enabled:
                error_previously = self.error != None
                if self.check_module_io_error():
                    if not error_previously == None:
                        self.set_output_error_values()
                    return

                f(*(args + self._arguments))

        self.is_class_method = determine_if_class_method(inspect.stack())

        if self.is_class_method and len(self.static_variables) > 0:
            raise ModuleError('Static variables are not permitted for'
                    ' switchboard modules that are class methods')

        # Initialise all the static variables
        for variable, init_value in self.static_variables.items():
            setattr(wrapped_func, variable, init_value)

        wrapped_func.module_class = self
        self.name = f.__name__
        return wrapped_func

