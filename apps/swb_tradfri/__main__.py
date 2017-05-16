#!/usr/bin/env python

'''
    A Switchboard board client capable of controlling IKEA Tradfri lightbulbs
'''

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
        }
    }

    app = ClientApp(configs)
    tradfri = Tradfri(app)
    app.run()

if __name__ == '__main__':
    main()
