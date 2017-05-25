
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

        # Map of client alias -> _Client object
        self.clients = {}

        # Map of module name -> _Module object
        self.modules = {}

        # Map of all the Switchboard devices (name -> device instance)
        self.devices = {}

        # Lock used to synchronise switchboard with its settings
        self.lock = Lock()


    def start(self):
        # Startup the Switchboard thread
        self._swb_thread = Thread(target=self.run)
        self._swb_thread.daemon = True
        self._swb_thread.start()


    def init_clients(self):
        ''' Initialise the switchboard clients according to the config file '''

        print("Initialising switchboard clients...")
        for client_url, client_alias in self.config.get('clients'):
            try:
                self.add_client(client_url, client_alias)
            except Exception as e:
                sys.exit('Error adding client {}({}): {}'.format(client_alias, client_url, e))

    def init_modules(self):
        ''' Initialise the switchboard modules according to the config file '''

        print("Initialising switchboard modules...")
        for module in self.config.get('modules'):
            try:
                self.upsert_switchboard_module(module)
            except Exception as e:
                sys.exit('Error adding module {}: {}'.format(module, e))

        self.running = self.config.get('running')


    def add_client(self, client_url, client_alias, log_prefix=''):
        print('{}Adding client {}({})'.format(log_prefix, client_alias, client_url))

        if client_alias in self.clients:
            raise EngineError('Client with alias "{}" already exists'.format(client_alias))

        for client in self.clients.values():
            if client.url == client_url:
                raise EngineError('Client with URL "{}" already exists with'
                        'alias {}'.format(client_url, client.alias))

        self._upsert_client(client_url, client_alias, log_prefix)


    def update_client(self, client_alias, log_prefix=''):
        if not client_url.startswith('http://'):
            client_url = 'http://' + client_url

        print('{}Updating client {}({})'.format(log_prefix, client_alias, client_url))

        if not client_alias in self.clients:
            raise EngineError('Unknown client alias "{}"'.format(client_alias))

        self._upsert_client(self.clients[client_alias].url, client_alias, log_prefix)


    def _upsert_client(self, client_url, client_alias, log_prefix):
        ''' Insert or update a Switchboard client. This method throws
            an exception if any issues are encountered and complies to
            the strong exception guarantee (i.e., if an error is raised
            SwitchboardEngine will keep running without changing state) '''

        # Get the info of all the devices
        info_url = client_url + '/devices_info'
        try:
             req = requests.get(info_url, timeout=1).json()
        except Exception as e:
            raise EngineError('Unable to connect to {}: {}'.format(info_url, e))


        # TODO check formatting for client_url + '/devices_value'
        client_devices = req['devices']
        print('{}Adding devices:'.format(log_prefix))

        new_devices = {}

        for device in client_devices:
            # Preprend the client name to the device name so that identical
            # devices on different clients have different names
            name = '{}.{}'.format(client_alias, device['name'])
            device['name'] = name

            # Check we don't have duplicate devices on this client
            if name in new_devices:
                raise EngineError('Device "{}" exists twice on client {}'.format(name, client_url))

            # Make sure we don't add a device that already exists on a
            # different client
            if name in self.devices and self.devices[name].client_url != client_url:
                clashing_client = self.devices[name].client_url
                msg = 'Device "{}" already exists for client {}'.format(name, clashing_client)
                raise EngineError(msg)

            new_devices[name] = RESTDevice(device, client_url, self.set_remote_device_value)
            print('{}\t{}'.format(log_prefix, name))

        # In case we are updating a client we need to delete all its
        # known 'old' devices and remove it from the input clients set
        if client_url in self.clients:
            for old_device in self.clients[client_url].devices:
                del self.devices[old_device]

        # TODO make sure that any deleted devices aren't used by modules

        # And now add all the 'new' client information
        self.devices.update(new_devices)
        self.clients[client_alias] = _Client(client_url, client_alias, new_devices)

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
                self._iodata.take_snapshot(self.clients, self.devices)
            except KeyboardInterrupt:
                break


    def set_remote_device_value(self, device, value):
        # Strip the client alias from the device name so that the remote
        # client recognises its local device
        local_device_name = device.name[device.name.find('.') + 1:]
        payload = json.dumps({'name': local_device_name, 'value': str(value)})
        try:
            r = requests.put(device.client_url + '/device_set', data=payload, timeout=1)
            response = r.json()
            if 'error' in response:
                print('Error: ' + response['error'])
        except Exception as e:
            print('Exception "{}" when setting the output value of {} to {}'.format(
                e, device.name, value))


    def _check_modules(self):
        for module in self.modules.values():
            module()


    def _update_devices_values(self):
        ''' Get updated values from all the input devices '''

        for client in self.clients.values():
            values_url = client.url + '/devices_value'

            try:
                values = requests.get(values_url, timeout=1)
                client.connected = True
            except:
                client.connected = False
                client.on_error('Unable to access client {}'.format(client.url))
                continue

            try:
                values_json = values.json()
            except:
                client.on_error('Invalid json formatting for client {}'.format(url))
                continue

            error = self._check_values_json_formatting(client.url, values_json)
            if error:
                client.on_error(error)
            else:
                client.on_no_error()
                for device_json in values_json['devices']:
                    self._update_device_value(client.alias, device_json)


    def _check_values_json_formatting(self, url, values_json):
        ''' Check that the request body is correctly formatted '''

        if 'error' in values_json:
            return 'Error for client {}: {}'.format(url, values_json['error'])

        if not 'devices' in values_json:
            return 'Error for client {}: no "devices" field'.format(url)

        for device_json in values_json['devices']:
            if not 'name' in device_json:
                return 'Error for client {}: found device with no name'.format(url)

            if not 'value' in device_json and not 'error' in device_json:
                return 'Error for client {}: device {} has no value or error field'.format(
                        url, device_json['name'])


    def _update_device_value(self, client_alias, device_json):
        ''' Given a correctly formatted json encoded device value,
            update the local device object '''

        global_dev_name = '{}.{}'.format(client_alias, device_json['name'])
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



class _Client:
    def __init__(self, url, alias, devices):
        self.url = url
        self.alias = alias
        self.connected = False
        self.error = None
        self.devices = devices


    def on_error(self, msg):
        if not self.error:
            print('Encountered error for client {}: {}'.format(self.url, msg))
            self.error = msg

            for device in self.devices.values():
                device.error = 'Client error "{}"'.format(msg)


    def on_no_error(self):
        if self.error:
            print('Client {} no longer in error state'.format(self.url))
            self.error = None

            for device in self.devices.values():
                device.error = None
