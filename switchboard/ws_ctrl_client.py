
import json
import sys
import copy
import time
from threading import Thread, Lock

try:
    from Queue import Queue
except:
    from queue import Queue

import websocket

from switchboard.utils import colour_text, get_input, is_set


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
            ws = websocket.WebSocketApp('ws://{}:{}/ws_iodata'.format(host, port),
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

        # Websocket app used to communicate with the ws_ctrl server
        self.ws = None

        self.response_queue = Queue()

        self.ws_handler = ws_handler
        super(WSCtrlClient, self).__init__(ws_handler=ws_handler, **kwargs)

    def on_ctrl_message(self, ws, message):
        msg_data = json.loads(message)

        if msg_data['command'] == 'update_config':
            with self.lock:
                self.swb_config = copy.deepcopy(msg_data['config'])
            self.ws_handler.update_current_config(self.swb_config)

        elif msg_data['command'] == 'response':
            self.response_queue.put(msg_data)

        else:
            assert False, 'Unkown command "{}"'.format(msg_data['command'])

    def run_ws_client(self, **kwargs):
        thread = Thread(target=self._run_ws_client, kwargs=kwargs)
        thread.daemon = True
        thread.start()

        super(WSCtrlClient, self).run_ws_client(**kwargs)

    def _run_ws_client(self, host, port, autokill):
        while True:
            self.ws = websocket.WebSocketApp('ws://{}:{}/ws_ctrl'.format(host, port),
                    on_message=self.on_ctrl_message,
                    on_error=self.on_error,
                    on_close=self.ws_handler.disconnected,
                    on_open=self.ws_handler.connected)

            self.ws.run_forever()
            if autokill:
                break

            self.swb_config = {}
            time.sleep(1)

    def send(self, command, params=[]):
        # There should be nothing in the response queue, but just in case there is...
        while not self.response_queue.empty():
            self.response_queue.get()

        self.ws.send(json.dumps({'command': command, 'params': params}))

        while True:
            time.sleep(0.01)
            if not self.response_queue.empty():
                if self.handle_response(self.response_queue.get()):
                    return

    def handle_response(self, msg_data):
        if 'display_text' in msg_data:
            text = msg_data['display_text']

            if 'command_status' in msg_data:
                if msg_data['command_status'] == 'ERROR':
                    text = colour_text(text, 'red')
                elif msg_data['command_status'] == 'WARNING':
                    text = colour_text(text, 'yellow')

            sys.stdout.write(text)

        if is_set(msg_data, 'get_input'):
            assert 'display_text' in msg_data, 'Internal error: can only get input if display_text is set'
            assert not is_set(msg_data, 'command_finished'), 'Internal error: can no finish command if requesting input'

            user_input = get_input()
            self.ws.send(json.dumps({'command': 'user_input', 'text': user_input}))
        else:
            print('')

        return is_set(msg_data, 'command_finished')


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
