
from datetime import datetime

def get_device_suffix(name):
    ''' Gets the device suffix indicating device type ('.i' for input,
        '.o' for output and '.io' for input+output. Return None in case
        of error '''
    VALID_SUFFIXES = [ 'i', 'o', 'io', 's' ]

    if not '.' in name:
        return None

    suffix = name.split('.')[-1]

    if not suffix in VALID_SUFFIXES:
        return None

    return suffix


class SwitchboardDevice(object):
    class BaseSignal(object):
        def __init__(self, device):
            self._device = device

        def get_error(self):
            return self._device.error

        def get_name(self):
            return self._device.name


    class InputSignal(BaseSignal):
        ''' Switchboard module facing input signal '''
        def get_value(self):
            return self._device.value

        def has_changed(self):
            return self._device.value != self._device.previous_value


    class OutputSignal(BaseSignal):
        ''' Switchboard module facing output signal '''
        def __init__(self, device):
            super(SwitchboardDevice.OutputSignal, self).__init__(device)
            self.driving_module = None

        def set_value(self, value):
            self._device.last_update_time = datetime.now()
            self._device.last_set_value = value
            self._device.set_value(value)


    def __init__(self, name):
        self.name = name

        # Used by input devices
        self.value = None
        self.previous_value = None

        # Used by output devices
        self.last_set_value = None

        self.is_input = False
        self.is_output = False

        self.error = None

        self.input_signal = None
        self.output_signal = None
        self.last_update_time = datetime.now()


    def create_input_signal(self):
        if not self.input_signal:
            self.input_signal = SwitchboardDevice.InputSignal(self)


    def create_output_signal(self):
        if not self.output_signal:
            self.output_signal = SwitchboardDevice.OutputSignal(self)


    def update_value(self, value):
        ''' To be called by the Switchboard engine when an input is updated'''
        self.previous_value = self.value
        self.value = value
        self.last_update_time = datetime.now()


    def set_value(self, value):
        ''' This method is expected to be overridden by the output device'''
        raise NotImplementedError('set_value needs to be overridden')


    def __str__(self):
        return 'name={} value={} input={} output={}'.format(
                self.name,
                self.value,
                self.is_input,
                self.is_output)



class SignalDevice(SwitchboardDevice):
    def __init__(self, name):
        device_name_suffix = get_device_suffix(name)
        if device_name_suffix != 's':
            raise Exception('Invalid device suffix. Must be .s for switchboard signals.')

        super(SignalDevice, self).__init__(name)

        self.is_input = True
        self.is_output = True
        self.create_input_signal()
        self.create_output_signal()


    def set_value(self, value):
        self.value = value



class RESTDevice(SwitchboardDevice):
    def __init__(self, device, host_url, set_value_callback):
        device_name_suffix = get_device_suffix(device['name'])
        if not device_name_suffix in ['i', 'o', 'io']:
            raise Exception('Invalid suffix for device {}. Must be .i, .o or .io for swtchboard REST devices.'.format(device['name']))

        super(RESTDevice, self).__init__(device['name'])

        self.host_url = host_url
        self._set_value_callback = set_value_callback

        if 'i' in device_name_suffix:
            if not device['readable']:
                raise Exception('Invalid device name: {} is an input (\'i\' at the end of the device name) but is not listed as readable'.format(device['name']))
            self.is_input = True
            self.create_input_signal()

        if 'o' in device_name_suffix:
            if not device['writeable']:
                raise Exception('Invalid device name: {} is an output (\'o\' at the end of the device name) but is not listed as writeable'.format(device['name']))
            self.is_output = True
            self.create_output_signal()


    def set_value(self, value):
        if not self.is_output:
            raise NotImplementedError('Cannot call set_value on {} as it is not an output device'.format(self.name))

        self._set_value_callback(self, value)
