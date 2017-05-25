"""
    Contains code used to interface with the IKEA Tradfri wireless bulbs
"""

import sys
import time
import json

from subprocess import Popen, PIPE
from switchboard.client import SwitchboardOutputDevice, SwitchboardIODevice

class Tradfri:
    def __init__(self, app):
        self.app = app
        self.host = app.args.tradfri_ip
        self.security_code = app.args.security_code

        # Variables needed in case the user wants to query the bulb state
        self.bulb_ids = []
        self.bulb_values = {}

        # Autodetect all the groups and bulbs and add Switchboard callbacks
        groups = self.coap_get('15004')
        bidx = 0
        for gidx, group in enumerate(groups):
            group = str(group)
            self._add_swb_o_device('group_{}_power.o'.format(gidx), group, self.power_group)
            self._add_swb_o_device('group_{}_dim.o'.format(gidx), group, self.dim_group)

            # Get a list of bulb ids
            bulbs = self.coap_get('15004/{}'.format(group))['9018']['15002']['9003']

            for bulb in bulbs:
                if bulb < 65537:
                    # Bulbs ids start at 65537, so we skip this one
                    continue
                bulb = str(bulb)
                self.bulb_ids.append(bulb)
                self._get_bulb_value(bulb)
                self._add_bulb(bulb, gidx, bidx)
                bidx += 1

        # It seems like the Tradfri network gateway doesn't like being
        # polled, so we need to tell it explicitly that we want to
        # update the bulb vaules
        if self.app.args.create_inputs:
            self.app.add_device(SwitchboardOutputDevice('update_bulb_values.o', self.update_bulb_values))


    def _add_bulb(self, bulb, gidx, bidx):
        # Add the bulb devices. If we want to be able to read the state
        # of the bulb then create .io devices
        if self.app.args.create_inputs:
            self._add_swb_io_device('bulb_{}_{}_power.io'.format(gidx, bidx),
                    bulb, self.power_bulb, self.get_power)
            self._add_swb_io_device('bulb_{}_{}_dim.io'.format(gidx, bidx),
                    bulb, self.dim_bulb, self.get_dim)
        else:
            self._add_swb_o_device('bulb_{}_{}_power.o'.format(gidx, bidx), bulb, self.power_bulb)
            self._add_swb_o_device('bulb_{}_{}_dim.o'.format(gidx, bidx), bulb, self.dim_bulb)

        # Could also make this an .io device, but who would want to read colour?
        self._add_swb_o_device('bulb_{}_{}_colour.o'.format(gidx, bidx), bulb, self.colour_bulb)


    def _add_swb_o_device(self, name, id, function):
        self.app.add_device(SwitchboardOutputDevice(name, lambda v, id=id: function(id, v)))


    def _add_swb_io_device(self, name, id, wr_function, rd_function):
        self.app.add_device(SwitchboardIODevice(name,
            lambda id=id: rd_function(id),
            lambda v, id=id: wr_function(id, v)))


    def power_group(self, group, value):
        # Power on or off an entire group
        payload = { "5850": 1 } if int(value) != 0 else { "5850": 0 }
        self.coap_set('15004/' + group, payload)

    def dim_group(self, group, value):
        # Dim an entire group
        value = min(255, int(value))
        value = max(0, value)
        payload = { "5851": value }
        self.coap_set('15004/' + group, payload)


    def power_bulb(self, bulb, value):
        # Power an individual light bulb on or off
        value = 1 if int(value) != 0 else 0
        payload = { "3311": [{ "5850": value }]}
        self.coap_set('15001/' + bulb, payload)
        self.bulb_values[bulb]['power'] = value

    def dim_bulb(self, bulb, value):
        # Dim an individual light bulb
        value = min(255, int(value))
        value = max(0, value)
        payload = { "3311": [{ "5851": value }]}
        self.coap_set('15001/' + bulb, payload)
        self.bulb_values[bulb]['dim'] = value

    def colour_bulb(self, bulb, value):
        # Change the colour of an individual light bulb
        # TODO use temperature name, not number
        value = min(2, int(value))
        value = max(0, value)

        colours = [ [{ "5709": 24930, "5710": 24684 }],
                    [{ "5709": 30140, "5710": 26909 }],
                    [{ "5709": 33135, "5710": 27211 }] ]

        payload = { "3311": colours[value] }
        self.coap_set('15001/' + bulb, payload)


    def get_power(self, bulb):
        return self.bulb_values[bulb]['power']

    def get_dim(self, bulb):
        return self.bulb_values[bulb]['dim']

    def update_bulb_values(self, value):
        for bulb in self.bulb_ids:
            self._get_bulb_value(bulb)

    def _get_bulb_value(self, bulb):
        values = self.coap_get('15001/{}'.format(bulb))['3311'][0]
        self.bulb_values[bulb] = {
            'power': values['5850'],
            'dim': values['5851']
        }


    def coap_get(self, target):
        cmd = 'coap-client -m get -u "Client_identity"'
        cmd += ' -k "{}"'.format(self.security_code)
        cmd += ' "coaps://{}:5684/{}"'.format(self.host, target)

        p = Popen(cmd, stdout=PIPE, shell=True)
        output, error = p.communicate()
        output = output.splitlines()[3]

        # Check for error
        if '4.04 Not Found' in str(output):
            return None

        return json.loads(output)

    def coap_set(self, target, payload):
        cmd = 'coap-client -m put -u "Client_identity"'
        cmd += ' -k "{}"'.format(self.security_code)
        cmd += ' -e \'{}\''.format(json.dumps(payload))
        cmd += ' "coaps://{}:5684/{}"'.format(self.host, target)

        p = Popen(cmd, stdout=PIPE, shell=True)
        output, error = p.communicate()

        if len(output.splitlines()) == 3:
            return None

        return str(output.splitlines()[3])


    @staticmethod
    def check_coap_client():
        p = Popen('coap-client', stdout=PIPE, stderr=PIPE, shell=True)
        time.sleep(0.05)
        if p.poll() == 127:
            print('coap-client not install. Please follow instructions from the README file')
            sys.exit(1)
