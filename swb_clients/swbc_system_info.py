#!/usr/bin/env python

'''
    A Switchboard board client that provides system info
'''

import psutil

from switchboard_client.client import ClientApp, SwitchboardInputDevice

from subprocess import Popen, PIPE

def get_temp():
    p = Popen(['cat', '/sys/class/thermal/thermal_zone0/temp'], stdout = PIPE)
    output, error = p.communicate()
    if error:
        return None
    return float(output) / 1000.0

def main():
    app = ClientApp()
    app.add_device(SwitchboardInputDevice('core_count.i', lambda: psutil.cpu_count()))
    app.add_device(SwitchboardInputDevice('cpu_usage.i', lambda: psutil.cpu_percent()))
    app.add_device(SwitchboardInputDevice('memory_usage.i', lambda: psutil.virtual_memory().percent))
    if get_temp():
        app.add_device(SwitchboardInputDevice('cpu_temperature.i', get_temp))

    app.run()

if __name__ == "__main__":
    main()
