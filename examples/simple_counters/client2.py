#!/usr/bin/env python

from switchboard.client import SwitchboardOutputDevice
from switchboard.app import ClientApp

def set_value(value):
    print('Received value {}'.format(value))

app = ClientApp()
app.add_device(SwitchboardOutputDevice('output.o', set_value))
app.run()
