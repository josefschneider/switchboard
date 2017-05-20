"""
    InfluxDBSave is an IOData Agent that forwards device values to an
    InfluxDB instance. This can then be used to display beautiful graphs
    in Grafana
"""

import os
import sys
import json
import time

from copy import deepcopy
from datetime import datetime
from influxdb import InfluxDBClient
from threading import Thread

from switchboard.app import IODataApp, check_port_arg
from switchboard.iodata import AgentBase


class InfluxDBSave(AgentBase):
    # If a device doesn't get any updates we want to resend the previous
    # value on a periodic basis so that we know that a device value
    # was valid and avialable at the time, as opposed to some part of
    # the system not working
    RESEND_PERIOD = 30.0

    def init(self, args):
        self._client = InfluxDBClient(
                args.influx_host,
                args.influx_port,
                args.username,
                args.password,
                args.db_name)

        # Create database if it doesn't exist
        dbs = self._client.get_list_database()
        if not any(db['name'] == args.db_name for db in dbs):
            self._client.create_database(args.db_name)

        self.session = args.session
        self.run_no = args.run_no
        self._device_values = {}
        self._update_list = {}
        self._last_resend_time = None

        resend_thread = Thread(target=self._resend_thread)
        resend_thread.daemon = True
        resend_thread.start()

    def _resend_thread(self):
        while True:
            last_sent = self._last_resend_time
            if last_sent and time.time() - last_sent > self.RESEND_PERIOD:
                # Resend all the device values
                self._send_values(self._device_values)
                self._last_resend_time = time.time()
            time.sleep(0.1)

    def _update_device(self, device_info):
        self._add_device_value_update(device_info, 'value')
        self._add_device_value_update(device_info, 'last_set_value')

    def _add_device_value_update(self, device_info, value_name):
        # Check for null
        value = device_info[value_name]
        if value == None:
            return

        name = '{}.{}'.format(device_info['name'], value_name)
        self._update_list[name] = value
        self._device_values[name] = value

    def _send_values(self, values):
        # It would be possible to set the update time from the
        # last_update_time field in the device, but then all the updates
        # would have to be sent one-by-one
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        json_body = [
            {
                "measurement": self.session,
                "tags": { "run": self.run_no },
                "time": timestamp,
                "fields": values
            }
        ]

        # Write JSON to InfluxDB
        self._client.write_points(json_body)


    def connected(self):
        pass

    def disconnected(self):
        pass


    def update_io_data(self, state_table, updates):
        # If we're about to resend the entire table might as well do it now
        if time.time() - self._last_resend_time > self.RESEND_PERIOD - 2:
            self.reset_io_data(state_table)
            return

        self._update_list = {}
        for update in updates:
            update['name'] = update['device']
            self._update_device(update)

        self._send_values(self._update_list)


    def reset_io_data(self, state_table):
        self._device_values = {}
        for hosts in state_table:
            for device in hosts['devices']:
                self._update_device(device)

        self._send_values(self._device_values)
        self._last_resend_time = time.time()


def main():
    influxdb = InfluxDBSave()

    app = IODataApp(iodata_agent=influxdb, configs={
            'InfluxDB host': {
                'args': [ '--influx_host' ,'-ifh' ],
                'kwargs': { 'help': 'host IP of the InfluxDB server',
                            'default': 'localhost' }
            },
            'InfluxDB port': {
                'args': [ '--influx_port' ,'-ifp' ],
                'kwargs': { 'help': 'listening port of the InfluxDB server',
                            'default': '8086' }
            },
            'InfluxDB username': {
                'args': [ '--username' ,'-u' ],
                'kwargs': { 'help': 'username for the InfluxDB server',
                            'default': 'root' }
            },
            'InfluxDB password': {
                'args': [ '--password' ,'-pwd' ],
                'kwargs': { 'help': 'password for the InfluxDB server',
                            'default': 'root' }
            },
            'Database name': {
                'args': [ '--db_name' ,'-n' ],
                'kwargs': { 'help': 'name of InfluxDB database to write to',
                            'default': 'swb_iodata' }
            },
            'Session': {
                'args': [ '--session' ,'-s' ],
                'kwargs': { 'help': 'InfluxDB database session name',
                            'default': 'swb' }
            },
            'RunNo': {
                'args': [ '--run_no' ,'-r' ],
                'kwargs': { 'help': 'InfluxDB run number',
                            'default': datetime.now().strftime("%Y%m%d%H%M") }
            }
        })

    if not app.args.influx_host:
        print('Cannot run InfluxDBSave: missing "--influx_host" argument')
        sys.exit(1)

    if not check_port_arg(app.args, 'influx_port'):
        sys.exit(-1)

    influxdb.init(app.args)
    sys.exit(app.run())


if __name__ == '__main__':
    main()
