
from switchboard.utils import get_input
from switchboard.agent_base import AgentBase

from bottle import Bottle, static_file
from bottle.ext.websocket import GeventWebSocketServer, websocket

from threading import Thread
import json

import os
module_path = os.path.dirname(os.path.realpath(__file__))


def send_updates(ws, updates):
    data = { 'command': 'update_fields', 'fields': updates }
    ws.send(json.dumps(data))


def send_state_table(ws, state_table):
    data = { 'command': 'update_table', 'table': state_table }
    ws.send(json.dumps(data))


class Dashboard(AgentBase):
    def __init__(self, configs):
        super(Dashboard, self).__init__(configs)
        self._app = Bottle()
        self._app.route('/', method='GET', callback=self._index)
        self._app.route('/websocket', method='GET', callback=self._websocket_connection, apply=[websocket])
        self._clients = set()
        self._io_state_table = []

        self._publish_thread = Thread(target=self._run)
        self._publish_thread.daemon = True
        self._publish_thread.start()

    def init_configs(self):
        while True:
            port_string = get_input('Please enter dashboard port: ')
            if port_string.isdigit():
                break
            print('Error: port must be a number between 0 and 65535')

        return { 'port': int(port_string) }

    def _run(self):
        self._app.run(host='127.0.0.1', port=self.configs['port'], debug=False, quiet=True, server=GeventWebSocketServer)

    def _index(self):
        return static_file('index.html', root=module_path + '/views/')

    def _websocket_connection(self, ws):
        self._clients.add(ws)
        send_state_table(ws, self._io_state_table)
        while True:
            msg = ws.receive()
            if msg is None:
                break
        self._clients.remove(ws)

    def update_io_data(self, state_table, updates):
        self._io_state_table = state_table
        for client in self._clients:
            send_updates(client, updates)

    def reset_io_data(self, state_table):
        self._io_state_table = state_table
        for client in self._clients:
            send_state_table(client, state_table)
