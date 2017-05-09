#!/usr/bin/env python

from switchboard_client.client import ClientApp, SwitchboardInputDevice

def get_value():
    get_value.counter += 1
    print('Sending value {}'.format(get_value.counter))
    return get_value.counter

get_value.counter = 0

app = ClientApp()
app.add_device(SwitchboardInputDevice('input.i', get_value))
app.run()
