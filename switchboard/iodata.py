
import json
import sys
import time
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from threading import Thread, Lock

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


def _send(data, connections=[]):
    str_data = json.dumps(data)
    str_data = '####{:08}####{}\n'.format(len(str_data) + 1, str_data)
    byte_data = str.encode(str_data)

    for connection in list(connections):
        try:
            connection.sendall(byte_data)
        except:
            connections.remove(connection)


class IOData:
    ''' IOData receives the entire Switchboard IO state at every tick
        and converts the progression of the IO state into a list of diffs.

        All agents are notified every time there is an update. '''

    def __init__(self, config):
        self._config = config

        # The last known state of the Switchboard IOs
        self._current_state_table = []

        # List of IOData connections
        self._connections = []

        # Lock used to synchronise updates and the connection listener
        self._lock = Lock()

    def init_config(self):
        port = self._config.get('iodata_port')
        if not port:
            port = get_free_port()

        self._config.set('iodata_port', port)
        print('IOData server listening on port {}'.format(port))

        thread = Thread(target=self._server_listen)
        thread.daemon = True
        thread.start()

    def _server_listen(self):
        # All this thread does is listen for new connections and add them to the list
        s = socket(AF_INET, SOCK_STREAM)
        s.bind(('localhost', self._config.get('iodata_port')))
        s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        s.listen(10)

        while True:
            conn, addr = s.accept()
            with self._lock:
                self._connections.append(conn)
                self._send_table_reset([conn])

    def _determine_table_updates(self, devices):
        updates = []

        for client_entry in self._current_state_table:
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
        self._current_state_table = []

    def take_snapshot(self, clients, devices):
        ''' Takes a snapshot of the current IO state and notifies consumers
            of any updates '''
        with self._lock:
            if self._current_state_table:
                updates = self._determine_table_updates(devices)
                if updates:
                    self._send_updates(updates, self._connections)
            else:
                # The state table has been reset. Create a new one.
                self._current_state_table = _make_state_table(clients)
                self._send_table_reset(self._connections)

    def _send_updates(self, updates, connections):
        msg = { 'action': 'update',
                'state_table': self._current_state_table,
                'updates': updates }
        _send(msg, connections)

    def _send_table_reset(self, connections):
        msg = { 'action': 'reset',
                'state_table': self._current_state_table }
        _send(msg, connections)


class IODataClient:
    MAX_READ_SIZE = 1024

    def __init__(self, iodata_agent, **kwargs):
        if not isinstance(iodata_agent, AgentBase):
            print('Invalid IOData agent type: has to inherit from AgentBase')
            sys.exit(1)

        self.iodata_agent = iodata_agent
        super(IODataClient, self).__init__(**kwargs)

    def run_iodata(self, client, port, autokill):
        while True:
            try:
                s = socket(AF_INET, SOCK_STREAM)
                s.connect((client, port))
            except Exception as e:
                if autokill:
                    raise e
                time.sleep(5)
                continue

            self.iodata_agent.connected()

            while True:
                header = s.recv(16)

                if not header:
                    self.iodata_agent.disconnected()
                    break

                header = header.decode()
                if header[:4] == '####' and header[12:] == '####':
                    # We have what looks like a properly formatted header
                    bytes_remaining = int(header[4:12])
                    raw_data = bytearray()

                    while True:
                        read_length = min(IODataClient.MAX_READ_SIZE, bytes_remaining)
                        raw_data += s.recv(read_length)
                        bytes_remaining -= read_length
                        if bytes_remaining <= 0:
                            break

                    if bytes_remaining < 0:
                        print('Badly formatted packet! Flushing buffer')
                        continue

                    data = json.loads(raw_data.decode())
                    if data['action'] == 'reset':
                        self.iodata_agent.reset_io_data(data['state_table'])
                    elif data['action'] == 'update':
                        self.iodata_agent.update_io_data(data['state_table'], data['updates'])

                else:
                    # Header is not formatted correctly. Start search
                    # TODO write recovery logic
                    pass


class AgentBase:
    ''' Base class that every IOData agent should inherit from '''
    def connected(self):
        '''connected method which is called when the server connects'''
        raise NotImplementedError(self.connected.__doc__)

    def disconnected(self):
        '''disconnected method which is called when the server disconnects'''
        raise NotImplementedError(self.disconnected.__doc__)

    def update_io_data(self, state_table, updates):
        '''update_io_data method required to update device values'''
        raise NotImplementedError(self.update_io_data.__doc__)

    def reset_io_data(self, state_table):
        '''reset_io_data method required to indicate a possible state table format change'''
        raise NotImplementedError(self.reset_io_data.__doc__)
