
import sys
import time
import json
import importlib
import requests
import logging

from threading import Lock, Thread

from switchboard.device import RESTDevice
from switchboard.module import SwitchboardModule
from switchboard.utils import load_attribute


logging.getLogger('requests').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def prints(fs, val):
    logger.info(val)
    fs(val)


class EngineError(Exception):
    def __init__(self, msg=''):
        self.msg = msg
        logger.warning(msg)

    def __str__(self):
        return self.msg



class SwitchboardEngine(object):
    def __init__(self, config, ws_ctrl):
        # Determines if the SwitchboardEngine logic is running or not
        self.running = False

        # Set to true if SwitchboardEngine should terminate
        self.terminate = False

        # The switchboard config object
        self.config = config

        # Object used to encode and disseminate the consecutive IO state
        self._ws_ctrl = ws_ctrl

        # Map of client alias -> _Client object
        self.clients = {}

        # Map of module name -> _Module object
        self.modules = {}

        # Map of all the Switchboard devices (name -> device instance)
        self.devices = {}

        # Lock used to synchronise switchboard with its settings
        self.lock = Lock()

        # Let the engine know how long since the last cycle
        self.prev_cycle_time = 0.0

    def init_clients(self):
        ''' Initialise the switchboard clients according to the config file '''

        if not self.config.get('clients'):
            return

        logger.info("Initialising switchboard clients...")
        for alias, client_info in self.config.get('clients').items():
            try:
                poll_period = client_info['poll_period'] if 'poll_period' in client_info else None
                self.add_client(client_info['url'], alias, poll_period)
            except Exception as e:
                prints(sys.exit, 'Error adding client {}({}): {}'.format(client_alias, client_url, e))

    def init_modules(self):
        ''' Initialise the switchboard modules according to the config file '''
        if self.config.get('modules'):
            logger.info("Initialising switchboard modules...")
            for module, state in self.config.get('modules').items():
                try:
                    self.upsert_switchboard_module(module, state=='enabled')
                except Exception as e:
                    prints(sys.exit, 'Error adding module {}: {}'.format(module, e))

        self.running = self.config.get('running')


    def add_client(self, client_url, client_alias, poll_period=None, log_prefix='', print_func=lambda s: None):
        polling = ' poll period={}'.format(poll_period) if poll_period else ''

        prints(print_func, '{}Adding client {}({}){}'.format(log_prefix, client_alias, client_url, polling))

        if client_alias in self.clients:
            raise EngineError('Client with alias "{}" already exists'.format(client_alias))

        for client in self.clients.values():
            if client.url == client_url:
                raise EngineError('Client with URL "{}" already exists with'
                        ' alias {}'.format(client_url, client.alias))

        self._upsert_client(client_url, client_alias, poll_period, log_prefix, print_func=print_func)


    def update_client(self, client_alias, poll_period=None, log_prefix='', print_func=lambda s: None):
        if not client_alias in self.clients:
            raise EngineError('Unkown client alias "{}"'.format(client_alias))

        client_url = self.clients[client_alias].url

        prints(print_func, '{}Updating client {}({})'.format(log_prefix, client_alias, client_url))

        self._upsert_client(client_url, client_alias, poll_period, log_prefix)


    def _upsert_client(self, client_url, client_alias, poll_period, log_prefix, print_func):
        ''' Insert or update a Switchboard client. This method throws
            an exception if any issues are encountered and complies to
            the strong exception guarantee (i.e., if an error is raised
            SwitchboardEngine will keep running without changing state) '''

        # Get the info of all the devices
        info_url = client_url + '/devices_info'
        try:
             req = requests.get(info_url, timeout=3).json()
        except Exception as e:
            raise EngineError('Unable to connect to {}: {}'.format(info_url, e))


        # TODO check formatting for client_url + '/devices_value'
        client_devices = req['devices']

        prints(print_func, '{}Adding devices:'.format(log_prefix))

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
                raise EngineError('Device "{}" already exists for client {}'.format(name, clashing_client))

            new_devices[name] = RESTDevice(device, client_url, self.set_remote_device_value)
            prints(print_func, '{}\t{}'.format(log_prefix, name))

        # In case we are updating a client we need to delete all its
        # known 'old' devices and remove it from the clients dict
        if client_alias in self.clients:
            # TODO cornercase: make sure that devices that no longer
            # exist aren't used by modules
            self.remove_client(client_alias)

        # And now add all the new/updated client information
        self.devices.update(new_devices)
        self.clients[client_alias] = _Client(client_url, client_alias, new_devices, poll_period)

        # Load the initial values
        self._update_devices_values()

        # Let ws_ctrl now we may have a new table structure
        self._ws_ctrl.reset_table()


    def get_modules_using_client(self, client_alias):
        ''' Returns a list of the modules using the given client '''

        client_obj = self.clients[client_alias]

        # Figure out which modules are using the IOs from this client
        modules_using_client = set()
        for mod_name, mod_obj in self.modules.items():
            ios = set(mod_obj.module_class.inputs) | set(mod_obj.module_class.outputs)
            for device in client_obj.devices:
                if device in ios:
                    modules_using_client.add(mod_name)
                    break

        return modules_using_client


    def remove_client(self, client_alias):
        ''' Remove the given client from the list of polled clients and
            delete the devices associated with this client '''

        for old_device in self.clients[client_alias].devices:
            del self.devices[old_device]
        del self.clients[client_alias]

        # Let ws_ctrl now we may have a new table structure
        self._ws_ctrl.reset_table()


    def upsert_switchboard_module(self, module_name, enabled=False):
        # Instantiate the module and update data structures
        logger.info('Adding module {}'.format(module_name))
        swbmodule = load_attribute(module_name)
        swbmodule.module_class.enabled = enabled
        self.modules[module_name] = swbmodule

        # Make sure all the inputs and outputs line up correctly
        swbmodule.module_class.create_argument_list(self.devices)


    def remove_module(self, module_name):
        del self.modules[module_name]
        logger.info('Removed module {}'.format(module_name))


    def enable_switchboard_module(self, module_name):
        if not module_name in self.modules:
            raise EngineError('Unknown module {}'.format(module_name))

        module_class = self.modules[module_name].module_class

        if module_class.error:
            logger.warning('Module {} enabled but will not run due to error: {}'.format(
                module_name, module_class.error))

        module_class.enabled = True


    def disable_switchboard_module(self, module_name):
        if not module_name in self.modules:
            raise EngineError('Unknown module {}'.format(module_name))

        self.modules[module_name].module_class.enabled = False


    def start(self):
        ''' Startup the Switchboard thread '''
        self._swb_thread = Thread(target=self.run)
        self._swb_thread.daemon = True
        self._swb_thread.start()


    def run(self):
        while not self.terminate:
            try:
                self.switchboard_loop()
            except KeyboardInterrupt:
                logger.info('Terminating due to keyboard interrupt')
                break


    def switchboard_loop(self):
        ''' Execute one loop/tick/clk of the Switchboard engine '''

        # Wait to complete the poll period
        poll_period = float(self.config.configs['poll_period'])
        time_diff = time.time() - self.prev_cycle_time
        sleep_time = max(0.0, poll_period - time_diff)
        time.sleep(sleep_time)
        self.prev_cycle_time = time.time()

        # Lock so that cli actions don't interfere
        with self.lock:
            # Get all the latest values
            self._update_devices_values()

            # Evaluate the modules if we're running
            if self.running:
                for module in self.modules.values():
                    module()

        # Update ws_ctrl agents
        self._ws_ctrl.take_snapshot(self.clients, self.devices)


    def set_remote_device_value(self, device, value):
        # Strip the client alias from the device name so that the remote
        # client recognises its local device
        local_device_name = device.name[device.name.find('.') + 1:]
        payload = json.dumps({'name': local_device_name, 'value': str(value)})
        try:
            r = requests.put(device.client_url + '/device_set', data=payload, timeout=1)
            response = r.json()
            if 'error' in response:
                logger.warning(response['error'])
        except Exception as e:
            logger.error('Exception "{}" when setting the output value of {} to {}'.format(
                e, device.name, value))


    def _update_devices_values(self):
        ''' Get updated values from the devices '''

        for client in self.clients.values():
            if not client.do_update():
                continue

            values_url = client.url + '/devices_value'

            try:
                values = requests.get(values_url, timeout=5)
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
                logger.warning('Device {} has reported an error: {}'.format(
                    global_dev_name, device_json['error']))
            device.error = device_json['error']

        elif 'value' in device_json:
            if device.error:
                logger.warning('Device {} no longer reporting error'.format(
                    global_dev_name))
                device.error = None
            device.update_value(device_json['value'])



class _Client:
    def __init__(self, url, alias, devices, poll_period):
        self.url = url
        self.alias = alias
        self.connected = False
        self.error = None
        self.devices = devices
        self.poll_period = poll_period  # Poll every iteration if None
        self.last_polled = 0.0
        logger = logging.getLogger(__name__)

    def do_update(self):
        ''' Determines if we should update this client or not '''
        if self.poll_period == None:
            return True

        if time.time() - self.last_polled > float(self.poll_period):
            self.last_polled = time.time()
            return True

        return False

    def on_error(self, msg):
        ''' Sets the error state of the client and all its associated devices '''
        if self.error != msg:
            logger.warning('Encountered error for client {}: {}'.format(self.url, msg))
            self.error = msg

            for device in self.devices.values():
                device.error = 'Client error "{}"'.format(msg)

    def on_no_error(self):
        if self.error:
            logger.info('Client {} no longer in error state'.format(self.url))
            self.error = None

            for device in self.devices.values():
                device.error = None
