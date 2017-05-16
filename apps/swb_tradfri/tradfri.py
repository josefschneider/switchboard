"""
    Contains code used to interface with the IKEA Tradfri wireless bulbs
"""

import sys
import time
import json

from subprocess import Popen, PIPE
from switchboard.client import SwitchboardOutputDevice

class Tradfri:
    def __init__(self, app):
        self.app = app
        self.host = app.args.tradfri_ip
        self.security_code = app.args.security_code

        # Autodetect all the groups and bulbs and add Switchboard callbacks
        groups = self.coap_get('15004')
        for gidx, group in enumerate(groups):
            self._add_swb_device('group_{}_power.o'.format(gidx), group, self.power_group)
            self._add_swb_device('group_{}_dim.o'.format(gidx), group, self.dim_group)

            bulbs = self.coap_get('15004/{}'.format(group))['9018']['15002']['9003']

            for bidx, bulb in enumerate(bulbs):
                if bulb < 65537:
                    continue
                self._add_swb_device('bulb_{}_{}_power.o'.format(gidx, bidx), bulb, self.power_bulb)
                self._add_swb_device('bulb_{}_{}_dim.o'.format(gidx, bidx), bulb, self.dim_bulb)
                self._add_swb_device('bulb_{}_{}_colour.o'.format(gidx, bidx), bulb, self.colour_bulb)


    def _add_swb_device(self, name, id, function):
        self.app.add_device(SwitchboardOutputDevice(name, lambda v, id=id: function(str(id), v)))

    def power_group(self, group, value):
        payload = { "5850": 1 } if int(value) != 0 else { "5850": 0 }
        self.coap_set('15004/' + group, payload)

    def dim_group(self, group, value):
        value = min(255, int(value))
        value = max(0, value)
        payload = { "5851": value }
        self.coap_set('15004/' + group, payload)

    def power_bulb(self, bulb, value):
        value = 1 if int(value) != 0 else 0
        payload = { "3311": [{ "5850": value }]}
        self.coap_set('15001/' + bulb, payload)

    def dim_bulb(self, bulb, value):
        value = min(255, int(value))
        value = max(0, value)
        payload = { "3311": [{ "5851": value }]}
        self.coap_set('15001/' + bulb, payload)

    def colour_bulb(self, bulb, value):
        value = min(2, int(value))
        value = max(0, value)

        colours = [ [{ "5709": 24930, "5710": 24684 }],
                    [{ "5709": 30140, "5710": 26909 }],
                    [{ "5709": 33135, "5710": 27211 }] ]

        payload = { "3311": colours[value] }
        self.coap_set('15001/' + bulb, payload)

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
