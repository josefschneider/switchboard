
import sys
import time
import json
import importlib
import requests

from threading import Lock, Thread

from switchboard.device import RESTDevice
from switchboard.module import SwitchboardModule
from switchboard.utils import load_attribute

class EngineError(Exception):
    pass


class SwitchboardEngine:
    def __init__(self, config, iodata):
        # Determines if the SwitchboardEngine logic is running or not
        self.running = False

        # Set to true if SwitchboardEngine should terminate
        self.terminate = False

        # The switchboard config object
        self.config = config

        # Object used to encode and disseminate the consecutive IO state
        self._iodata = iodata

        # Map of host alias -> Host object
        self.hosts = {}

        # Map of module name -> _Module object
        self.modules = {}

        # Map of all the Switchboard devices (name -> device instance)
        self.devices = {}

        # Lock used to synchronise switchboard with its settings
        self.lock = Lock()

        # Startup the Switchboard thread
        self._swb_thread = Thread(target=self.run)
        self._swb_thread.daemon = True
        self._swb_thread.start()


    def init_config(self):
        ''' Initialise the switchboard hosts and modules according to
            the config file '''

        print("Initialising switchboard config...")

        for host_url, host_alias in self.config.get('hosts'):
            try:
                self._upsert_host(host_url, host_alias)
            except Exception as e:
                sys.exit('Error adding host {}({}): {}'.format(host_alias, host_url, e))

        for module in self.config.get('modules'):
            try:
                self.upsert_switchboard_module(module)
            except Exception as e:
                sys.exit('Error adding module {}: {}'.format(module, e))

        self.running = self.config.get('running')


    def add_host(self, host_url, host_alias):
        print('Adding host {}({})'.format(host_alias, host_url))

        if host_alias in self.hosts:
            raise EngineError('Host with alias "{}" already exists'.format(host_alias))

        for host in self.hosts.values():
            if host.url == host_url:
                raise EngineError('Host with URL "{}" already exists with'
                        'alias {}'.format(host_url, host.alias))

        self._upsert_host(host_url, host_alias)


    def update_host(self, host_alias):
        if not host_url.startswith('http://'):
            host_url = 'http://' + host_url

        print('Updating host {}({})'.format(host_alias, host_url))

        if not host_alias in self.hosts:
            raise EngineError('Unknown host alias "{}"'.format(host_alias))

        self._upsert_host(self.hosts[host_alias].url, host_alias)


    def _upsert_host(self, host_url, host_alias):
        ''' Insert or update a Switchboard host. This method throws
            an exception if any issues are encountered and complies to
            the strong exception guarantee (i.e., if an error is raised
            SwitchboardEngine will keep running without changing state) '''

        # Get the info of all the devices
        info_url = host_url + '/devices_info'
        try:
             req = requests.get(info_url).json()
        except Exception as e:
            raise EngineError('Unable to connect to {}: {}'.format(info_url, e))


        # TODO check formatting for host_url + '/devices_value'
        host_devices = req['devices']
        print('Adding devices:')

        new_devices = {}

        for device in host_devices:
            # Preprend the host name to the device name so that identical
            # devices on different hosts have different names
            name = '{}.{}'.format(host_alias, device['name'])
            device['name'] = name

            # Check we don't have duplicate devices on this host
            if name in new_devices:
                raise EngineError('Device "{}" exists twice on host {}'.format(name, host_url))

            # Make sure we don't add a device that already exists on a
            # different host
            if name in self.devices and self.devices[name].host_url != host_url:
                clashing_host = self.devices[name].host_url
                msg = 'Device "{}" already exists for host {}'.format(name, clashing_host)
                raise EngineError(msg)

            new_devices[name] = RESTDevice(device, host_url, self.set_remote_device_value)
            print('\t{}'.format(name))

        # In case we are updating a host we need to delete all its
        # known 'old' devices and remove it from the input hosts set
        if host_url in self.hosts:
            for old_device in self.hosts[host_url].devices:
                del self.devices[old_device]

        # TODO make sure that any deleted devices aren't used by modules

        # And now add all the 'new' host information
        self.devices.update(new_devices)
        self.hosts[host_alias] = Host(host_url, host_alias, new_devices.keys())

        # Load the initial values
        self._update_devices_values()

        # Let iodata now we may have a new table structure
        self._iodata.reset_table()


    def upsert_switchboard_module(self, module_name):
        # Instantiate the module and update data structures
        print('Adding module {}'.format(module_name))
        swbmodule = load_attribute(module_name)
        swbmodule.module_class.enabled = True
        self.modules[module_name] = swbmodule

        # Make sure all the inputs and outputs line up correctly
        swbmodule.module_class.create_argument_list(self.devices)


    def enable_switchboard_module(self, module_name):
        if not module_name in modules:
            raise EngineError('Unknown module {}'.format(module_name))

        module_class = modules[module_name].module_class

        if module_class.error:
            print('Module {} enabled but will not run due to error: {}'.format(
                module_name, module_class.error))

        module_class.enabled = True


    def disable_switchboard_module(self, module_name):
        if not module_name in modules:
            raise EngineError('Unknown module {}'.format(module_name))

        modules[module_name].module_class.enabled = False


    def run(self):
        prev_cycle_time = 0.0
        while not self.terminate:
            try:
                time_diff = time.time() - prev_cycle_time
                sleep_time = float(self.config.get('poll_period')) - time_diff
                if sleep_time > 0.0:
                    time.sleep(sleep_time)
                prev_cycle_time = time.time()

                with self.lock:
                    self._update_devices_values()
                    if self.running:
                        self._check_modules()
                self._iodata.take_snapshot(self.hosts, self.devices)
            except KeyboardInterrupt:
                break


    def set_remote_device_value(self, device, value):
        # Strip the host alias from the device name so that the remote
        # host recognises its local device
        local_device_name = device.name[device.name.find('.') + 1:]
        payload = json.dumps({'name': local_device_name, 'value': str(value)})
        r = requests.put(device.host_url + '/device_set', data=payload)
        try:
            response = r.json()
            if 'error' in response:
                print('Error: ' + response['error'])
        except Exception as e:
            print('Exception "{}" when setting the output value of {}: {}'.format(e, device.name, r.content))


    def _check_modules(self):
        for module in self.modules.values():
            module()


    def _update_devices_values(self):
        ''' Get updated values from all the input devices '''

        for host in self.hosts.values():
            values_url = host.url + '/devices_value'

            try:
                values = requests.get(values_url)
                host.connected = True
            except:
                host.connected = False
                host.on_error('Unable to access host {}'.format(host.url))
                continue

            try:
                values_json = values.json()
            except:
                host.on_error('Invalid json formatting for host {}'.format(url))
                continue

            error = self._check_values_json_formatting(host.url, values_json)
            if error:
                host.on_error(error)
            else:
                host.on_no_error()
                for device_json in values_json['devices']:
                    self._update_device_value(host.alias, device_json)


    def _check_values_json_formatting(self, url, values_json):
        ''' Check that the request body is correctly formatted '''

        if 'error' in values_json:
            return 'Error for host {}: {}'.format(url, values_json['error'])

        if not 'devices' in values_json:
            return 'Error for host {}: no "devices" field'.format(url)

        for device_json in values_json['devices']:
            if not 'name' in device_json:
                return 'Error for host {}: found device with no name'.format(url)

            if not 'value' in device_json and not 'error' in device_json:
                return 'Error for host {}: device {} has no value or error field'.format(
                        url, device_json['name'])


    def _update_device_value(self, host_alias, device_json):
        ''' Given a correctly formatted json encoded device value,
            update the local device object '''

        global_dev_name = '{}.{}'.format(host_alias, device_json['name'])
        device = self.devices[global_dev_name]

        if 'error' in device_json:
            if not device.error:
                print('Device {} has reported an error: {}'.format(
                    global_dev_name, device_json['error']))
            device.error = device_json['error']

        elif 'value' in device_json:
            if device.error:
                print('Device {} no longer reporting error'.format(
                    global_dev_name))
                device.error = None
            device.update_value(device_json['value'])



class Host:
    def __init__(self, url, alias, devices):
        self.url = url
        self.alias = alias
        self.connected = False
        self.error = None
        self.devices = set(devices)


    def on_error(self, msg):
        if not self.error:
            print('Encountered error for host {}: {}'.format(self.url, msg))
            self.error = msg

            for device in self.devices.values():
                device.error = "Host error"


    def on_no_error(self):
        if self.error:
            print('Host {} no longer in error state'.format(self.url))
            self.error = None

            for device in self.devices:
                device.error = None
