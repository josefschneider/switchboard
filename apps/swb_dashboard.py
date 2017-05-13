''' Dashboard is an IOData Agent that displays the devices values
    and keeps them updated using websockets '''

from switchboard.utils import get_input
from switchboard.app import IODataApp, check_port_arg
from switchboard.iodata import AgentBase

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
    def __init__(self):
        self._app = Bottle()
        self._app.route('/', method='GET', callback=self._index)
        self._app.route('/websocket', method='GET', callback=self._websocket_connection, apply=[websocket])
        self._clients = set()
        self._io_state_table = []

    def run(self, port):
        self._app.run(host='localhost', port=port, debug=False, quiet=True, server=GeventWebSocketServer)

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

    def connected(self):
        pass

    def disconnected(self):
        # TODO display some notification that Switchboard can no longer be reached
        pass

    def update_io_data(self, state_table, updates):
        self._io_state_table = state_table
        for client in self._clients:
            send_updates(client, updates)

    def reset_io_data(self, state_table):
        self._io_state_table = state_table
        for client in self._clients:
            send_state_table(client, state_table)


def main():
    dashboard = Dashboard()

    app = IODataApp(iodata_agent=dashboard, configs={
            'Dashboard port': {
                'long': '--dashboard_port',
                'short': '-dp',
                'desc': 'listening port of the Dashboard HTML server'
            }
        })

    if not app.args.dashboard_port:
        print('Cannot run Dashboard: missing "--dashboard_port" argument')
        sys.exit(1)

    if check_port_arg(app.args, 'dashboard_port'):
        port = int(app.args.dashboard_port)
        publish_thread = Thread(target=lambda port=port: dashboard.run(port))
        publish_thread.daemon = True
        publish_thread.start()

        app.run()
    else:
        print('Invalid port value: must be an integer > 0 and < 65536')
        sys.exit(-1)


if __name__ == '__main__':
    main()
