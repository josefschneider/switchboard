#!/usr/bin/env python

from switchboard_client.client import ClientApp, SwitchboardOutputDevice

def set_value(value):
    print('Received value {}'.format(value))

app = ClientApp()
app.add_device(SwitchboardOutputDevice('output.o', set_value))
app.run()
