
import json
from functools import wraps

from bottle import Bottle, request, response


class _SwitchboardDevice(object):
    def __init__(self, name, read_callback, write_callback, readable, writeable, classname):
        if name.split('.')[-1] != self.SUFFIX:
            raise Exception('Invalid name {} for device type {}, the name must end in ".{}"'.format(name, classname, self.SUFFIX))
        self.name = name
        self.read_callback = read_callback
        self.write_callback = write_callback
        if self.read_callback:
            self.value = read_callback()
        self.readable = readable
        self.writeable = writeable

    def _get_info(self):
        return { 'name': self.name, 'writeable': self.writeable, 'readable': self.readable }

    def _get_value(self):
        ''' Only returns a value if this is an input capable device
            or if there is an error with the device '''
        info = { }
        if self.read_callback:
            info['name'] = self.name
            try:
                # The device might also be output only, in which
                # case the read_callback checks for errors
                info['value'] = self.read_callback()

                if self.readable:
                    return info
            except Exception as e:
                info['error'] = str(e)
        return info


class SwitchboardInputDevice(_SwitchboardDevice):
    SUFFIX = 'i'

    def __init__(self, name, read_callback):
        super(SwitchboardInputDevice, self).__init__(name, read_callback, None, True, False, self.__class__.__name__)


class SwitchboardOutputDevice(_SwitchboardDevice):
    SUFFIX = 'o'
    def __init__(self, name, write_callback, error_check_callback = None):
        super(SwitchboardOutputDevice, self).__init__(name, error_check_callback, write_callback, False, True, self.__class__.__name__)


class SwitchboardIODevice(_SwitchboardDevice):
    SUFFIX = 'io'
    def __init__(self, name, read_callback, write_callback):
        super(SwitchboardIODevice, self).__init__(name, read_callback, write_callback, True, True, self.__class__.__name__)


class SwitchboardDeviceStore(object):
    def __init__(self, **kwargs):
        super(SwitchboardDeviceStore, self).__init__(**kwargs)
        self._devices = {}

    def add_device(self, device):
        ''' Adds a device to the store '''
        if device.name in self._devices:
            raise Exception('Could not add device {} as it already exists'.format(device.name))
        self._devices[device.name] = device

    def _get_devices_info(self):
        ''' Gets an array with all the device info '''
        devices_info = []
        for device in self._devices.values():
            devices_info.append(device._get_info())
        return devices_info

    def _get_devices_value(self):
        ''' Gets an array with all the device values '''
        devices_value = []
        for device in self._devices.values():
            value = device._get_value()
            if len(value) > 0:
                devices_value.append(value)
        return devices_value

    def _set_device_value(self, name, value):
        if not name in self._devices:
            raise KeyError('Could not set value of device {} as it does not exist'.format(name))
        if not self._devices[name].writeable:
            raise KeyError('Could not set value for device {} as it is not writeable'.format(name))
        return self._devices[name].write_callback(value)


class SwitchboardClient(SwitchboardDeviceStore):
    def __init__(self, quiet=True, **kwargs):
        super(SwitchboardClient, self).__init__(**kwargs)
        self._quiet = quiet
        self._app = Bottle()
        self._app.route('/devices_info', method='GET', callback=self._devices_info)
        self._app.route('/devices_value', method='GET', callback=self._devices_value)
        self._app.route('/device_set', method='PUT', callback=self._device_set)

    def run_client(self, port, host='0.0.0.0'):
        self._app.run(host=host, port=port, debug=False, quiet=self._quiet)

    def _devices_info(self):
        response.headers['Content-Type'] = 'application/json'
        devices_list = { 'devices': self._get_devices_info() }
        return json.dumps(devices_list)

    def _devices_value(self):
        response.headers['Content-Type'] = 'application/json'
        devices_list = { 'devices': self._get_devices_value() }
        return json.dumps(devices_list)

    def _device_set(self):
        response.headers['Content-Type'] = 'application/json'
        retval = { }

        try:
            try:
                data = json.loads(request.body.read().decode('ascii'))
            except:
                raise ValueError('Unable to decode json data from PUT request')

            if data is None:
                raise ValueError('No data sent in body of PUT request')

            if not 'value' in data:
                raise KeyError('No "name" field in body of PUT request')

            if not 'value' in data:
                raise KeyError('No "value" field in body of PUT request')

            self._set_device_value(data['name'], data['value'])

        except Exception as e:
            retval['error'] = str(e)

        return json.dumps(retval)
