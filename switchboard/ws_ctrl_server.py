
import json
import sys
from threading import Thread, Lock

from bottle import Bottle, static_file
from bottle.ext.websocket import GeventWebSocketServer, websocket

import os
module_path = os.path.dirname(os.path.realpath(__file__))

from switchboard.utils import get_free_port
from switchboard.command_decoder import CommandDecoder


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
        self._decoder = None

        # Register the callback to be executed whenever the config is updated
        self._config.register_config_update_handler(
                lambda self=self: self.send_current_config(self._ctrl_clients))

        # The last known state of the Switchboard IOs
        self.current_state_table = []

        # Lock used to synchronise updates and the connection listener
        self._lock = Lock()

        self._iodata_clients = set()
        self._ctrl_clients = set()

    def set_dependencies(self, engine, app_manager):
        assert not self._decoder
        self._decoder = CommandDecoder(self._config, engine, app_manager)

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
            self.send_current_config([ws])

        while True:
            msg = ws.receive()
            if msg is None:
                break
            self._decoder.decode_ctrl_command(ws, msg)

        with self._lock:
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
