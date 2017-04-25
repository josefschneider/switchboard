
from bottle import Bottle, static_file
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket

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


class WebsocketServer(object):
    def __init__(self, port):
        self._port = port
        self._app = Bottle()
        self._app.route('/', method='GET', callback=self._index)
        self._app.route('/websocket', method='GET', callback=self._websocket_connection, apply=[websocket])
        self._clients = set()
        self._io_state_table = []

        self._publish_thread = Thread(target=self.run)
        self._publish_thread.daemon = True
        self._publish_thread.start()

    def run(self):
        self._app.run(host='127.0.0.1', port=self._port, debug=False, quiet=True, server=GeventWebSocketServer)

    def update_io_data(self, state_table, updates):
        self._io_state_table = state_table
        for client in self._clients:
            send_updates(client, updates)

    def reset_io_data(self, state_table):
        self._io_state_table = state_table
        for client in self._clients:
            send_state_table(client, state_table)

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
