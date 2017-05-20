#!/usr/bin/env python

'''
    A Switchboard board client capable of controlling IKEA Tradfri lightbulbs
'''

import sys

from switchboard.app import ClientApp

from apps.swb_tradfri.tradfri import Tradfri

def main():
    Tradfri.check_coap_client()

    configs = {
        'Tradfri IP address': {
            'args': [ '--tradfri_ip', '-ti' ],
            'kwargs': { 'help': 'Tradfri gateway IP address' }
        },
        'Tradfri security code': {
            'args': [ '--security_code', '-sc' ],
            'kwargs': { 'help': 'Tradfri security code (as printed on the network gateway)'}
        },
        'Create inputs': {
            'args': [ '--create_inputs', '-ci' ],
            'kwargs': {
                'help': 'Create inputs so that current light-bulb state can be read (warning: a little unreliable)',
                'action': 'store_true'
            }
        }
    }

    app = ClientApp(configs)

    if not app.args.tradfri_ip:
        print('Error: argument "--tradfri_ip" not specified')
        sys.exit(1)
    elif not app.args.security_code:
        print('Error: argument "--security_code" not specified')
        sys.exit(1)

    tradfri = Tradfri(app)
    app.run()

if __name__ == '__main__':
    main()
