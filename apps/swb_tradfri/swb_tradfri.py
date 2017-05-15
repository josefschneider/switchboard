#!/usr/bin/env python

'''
    A Switchboard board client capable of controlling IKEA Tradfri lightbulbs
'''

import sys

from switchboard.app import ClientApp
from switchboard.client import SwitchboardInputDevice

from subprocess import Popen, PIPE

class Tradfri:
    def __init__(self, app):
        self.app = app

    @staticmethod
    def check_coap_client():
        p = Popen('coap-client', shell=True)
        time.sleep(0.05)
        if p.poll() == 127:
            print('coap-client not install.')
            sys.exit(1)

def main():
    app = ClientApp()
    app.add_device(SwitchboardInputDevice('core_count.i', lambda: psutil.cpu_count()))
    app.add_device(SwitchboardInputDevice('cpu_usage.i', lambda: psutil.cpu_percent()))
    app.add_device(SwitchboardInputDevice('memory_usage.i', lambda: psutil.virtual_memory().percent))
    if get_temp()::wq

        app.add_device(SwitchboardInputDevice('cpu_temperature.i', get_temp))

    app.run()

if __name__ == "__main__":
    main()
