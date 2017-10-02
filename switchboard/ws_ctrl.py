
import json
import sys
import copy
import time
from threading import Thread, Lock

from bottle import Bottle, static_file
from bottle.ext.websocket import GeventWebSocketServer, websocket

import websocket as ws_client

import os
module_path = os.path.dirname(os.path.realpath(__file__))

from switchboard.utils import get_free_port


def _make_state_table(clients):
    ''' Convert clients and devices into a brand new state table '''
    table = []
    for _, client in sorted(clients.items()):
        client_entry = { 'client_url': client.url, 'client_alias': client.alias, 'devices': [] }
        devices_entries = client_entry['devices']
        for _, d_obj in sorted(client.devices.items()):
            device_entry = {
                'last_update_time': str(d_obj.last_update_time),
                'name': d_obj.name,
                'value': d_obj.value,
                'last_set_value': d_obj.last_set_value }
            devices_entries.append(device_entry)
        table.append(client_entry)
    return table


class WSCtrlServer:
    ''' WSCtrlServer receives the entire Switchboard IO state at every tick
        and converts the progression of the IO state into a list of diffs.

        All agents are notified every time there is an update. '''

    def __init__(self, config):
        self._config = config
        self._config.register_config_update_handler(
                lambda self=self: self.send_current_config(self._ctrl_clients))

        # The last known state of the Switchboard IOs
        self.current_state_table = []

        # Lock used to synchronise updates and the connection listener
        self._lock = Lock()

        self._iodata_clients = set()
        self._ctrl_clients = set()

    def init_config(self):
        self.port = self._config.get('ws_port')
        if not self.port:
            self.port = get_free_port()

        self._config.set('ws_port', self.port)
        print('WSCtrlServer server listening on port {}'.format(self.port))

        self._app = Bottle()
        self._app.route('/', method='GET', callback=self._index)
        self._app.route('/ws_iodata', method='GET', callback=self._ws_iodata_connection, apply=[websocket])
        self._app.route('/ws_ctrl', method='GET', callback=self._ws_ctrl_connection, apply=[websocket])

        thread = Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def run(self):
        self._app.run(host='localhost', port=self.port, debug=False, quiet=True, server=GeventWebSocketServer)

    def _index(self):
        return static_file('index.html', root=module_path + '/views/')

    def _ws_iodata_connection(self, ws):
        ''' A client receives IOData and can send a limited amount of commands '''
        with self._lock:
            self._iodata_clients.add(ws)
            self.send_state_table([ws])

        while True:
            msg = ws.receive()
            if msg is None:
                break

        with self._lock:
            self._iodata_clients.remove(ws)

    def _ws_ctrl_connection(self, ws):
        ''' A ctrl connection receives IOData, status etc. and has full control over Switchboard '''
        with self._lock:
            self._ctrl_clients.add(ws)
            self._iodata_clients.add(ws)
            self.send_state_table([ws])
            self.send_current_config([ws])

        while True:
            msg = ws.receive()
            if msg is None:
                break

        with self._lock:
            self._iodata_clients.remove(ws)
            self._ctrl_clients.remove(ws)

    def _determine_table_updates(self, devices):
        updates = []

        for client_entry in self.current_state_table:
            for device in client_entry['devices']:
                d_obj = devices[device['name']]
                last_update_time = str(d_obj.last_update_time)
                if device['value'] != d_obj.value or \
                        device['last_set_value'] != d_obj.last_set_value or \
                        device['last_update_time'] != last_update_time:

                    update = {'last_update_time': last_update_time,
                            'device': d_obj.name,
                            'value': d_obj.value,
                            'last_set_value': d_obj.last_set_value }
                    updates.append(update)

                    # Update the current_state_table
                    device['last_update_time'] = last_update_time
                    device['value'] = d_obj.value
                    device['last_set_value'] = d_obj.last_set_value

        return updates

    def reset_table(self):
        ''' This function is called if the table structure should be updated.
            This happens when clients or devices are added or removed. '''
        self.current_state_table = []

    def take_snapshot(self, clients, devices):
        ''' Takes a snapshot of the current IO state and notifies consumers
            of any updates '''
        with self._lock:
            if self.current_state_table:
                updates = self._determine_table_updates(devices)
                if updates:
                    self.send_updates(updates)
            else:
                # The state table has been reset. Create a new one.
                self.current_state_table = _make_state_table(clients)
                self.send_state_table(self._iodata_clients)

    def send_updates(self, updates):
        data = { 'command': 'update_fields', 'fields': updates }
        for ws in self._iodata_clients:
            ws.send(json.dumps(data))

    def send_state_table(self, wss):
        data = { 'command': 'update_table', 'table': self.current_state_table }
        for ws in wss:
            ws.send(json.dumps(data))

    def send_current_config(self, wss):
        data = { 'command': 'update_config', 'config': self._config.configs }
        for ws in wss:
            ws.send(json.dumps(data))


class WSIODataClient(object):
    def __init__(self, ws_handler, **kwargs):
        if not isinstance(ws_handler, WSIODataHandlerBase):
            print('Invalid handler type: has to inherit from WSIODataHandlerBase')
            sys.exit(1)

        # The last known state of the Switchboard IOs
        self.current_state_table = []

        # Map pointing to client info entries for faster client access when updating
        self.swb_clients = {}

        # Map pointing to device info entries for faster device access when updating
        self.devices = {}

        # Lock used to synchronise access to the data made available by this client
        self.lock = Lock()

        self.ws_handler = ws_handler
        super(WSIODataClient, self).__init__(**kwargs)

    def _create_current_state_table(self, table):
        with self.lock:
            self.current_state_table = copy.deepcopy(table)

        self.current_state_table.sort(key=lambda x: x['client_alias'])

        self.swb_clients = {}
        self.devices = {}

        for client_entry in self.current_state_table:
            self.swb_clients[client_entry['client_alias']] = client_entry
            client_entry['devices'].sort(key=lambda x: x['name'])
            for device in client_entry['devices']:
                self.devices[device['name']] = device

    def _update_current_state_table(self, updates):
        with self.lock:
            for update in updates:
                device = self.devices[update['device']]
                device['last_update_time'] = update['last_update_time']
                device['value'] = update['value']
                device['last_set_value'] = update['last_set_value']

    def on_iodata_message(self, ws, message):
        msg_data = json.loads(message)
        if msg_data['command'] == 'update_table':
            self._create_current_state_table(msg_data['table'])
            self.ws_handler.reset_io_data(self.current_state_table)

        elif msg_data['command'] == 'update_fields':
            updates = msg_data['fields']
            self._update_current_state_table(updates)
            self.ws_handler.update_io_data(self.current_state_table, updates)

    def on_error(self, ws, error):
        print('Error: "{}" for {}'.format(error, ws.url))
        self.ws_handler.disconnected(ws)

    def run_ws_client(self, host, port, autokill):
        while True:
            ws = ws_client.WebSocketApp('ws://{}:{}/ws_iodata'.format(host, port),
                    on_message=self.on_iodata_message,
                    on_error=self.on_error,
                    on_close=self.ws_handler.disconnected,
                    on_open=self.ws_handler.connected)

            ws.run_forever()
            if autokill:
                break

            self.current_state_table = []
            self.devices = {}
            time.sleep(1)


class WSCtrlClient(WSIODataClient):
    def __init__(self, ws_handler, **kwargs):
        if not isinstance(ws_handler, WSCtrlHandlerBase):
            print('Invalid handler type: has to inherit from WSCtrlHandlerBase')
            sys.exit(1)

        # Stores the last known state of the Switchboard config
        self.swb_config = {}

        self.ws_handler = ws_handler
        super(WSCtrlClient, self).__init__(ws_handler=ws_handler, **kwargs)

    def on_ctrl_message(self, ws, message):
        msg_data = json.loads(message)
        if msg_data['command'] == 'update_config':
            with self.lock:
                self.swb_config = copy.deepcopy(msg_data['config'])
            self.ws_handler.update_current_config(self.swb_config)

    def run_ws_client(self, **kwargs):
        thread = Thread(target=self._run_ws_client, kwargs=kwargs)
        thread.daemon = True
        thread.start()

        super(WSCtrlClient, self).run_ws_client(**kwargs)

    def _run_ws_client(self, host, port, autokill):
        while True:
            ws = ws_client.WebSocketApp('ws://{}:{}/ws_ctrl'.format(host, port),
                    on_message=self.on_ctrl_message,
                    on_error=self.on_error,
                    on_close=self.ws_handler.disconnected,
                    on_open=self.ws_handler.connected)

            ws.run_forever()
            if autokill:
                break

            self.swb_config = {}
            time.sleep(1)


class WSIODataHandlerBase:
    ''' Base class that every WSIODataClient should inherit from '''
    def connected(self, ws):
        '''connected method which is called when the server connects'''
        raise NotImplementedError(self.connected.__doc__)

    def disconnected(self, ws):
        '''disconnected method which is called when the server disconnects'''
        raise NotImplementedError(self.disconnected.__doc__)

    def update_io_data(self, state_table, updates):
        '''update_io_data method required to update device values'''
        raise NotImplementedError(self.update_io_data.__doc__)

    def reset_io_data(self, state_table):
        '''reset_io_data method required to indicate a possible state table format change'''
        raise NotImplementedError(self.reset_io_data.__doc__)


class WSCtrlHandlerBase(WSIODataHandlerBase):
    ''' Base class that every WSCtrlClient should inherit from '''
    def update_current_config(self, config):
        '''update_current_config method required to update the current Switchboard config'''
        raise NotImplementedError(self.update_current_config.__doc__)
