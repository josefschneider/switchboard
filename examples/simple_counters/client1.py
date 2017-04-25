#!/usr/bin/env python

from switchboard_client.client import SwitchboardClient, SwitchboardInputDevice

class InputClient(SwitchboardInputDevice):
    NAME = 'input.i'

    def __init__(self):
        self.counter = 0
        super(InputClient, self).__init__(self.NAME, self.get_value)

    def get_value(self):
        # Increment every time this client is polled
        self.counter += 1
        print('Sending value {}'.format(self.counter))
        return self.counter


client = SwitchboardClient('0.0.0.0', 4000, quiet=False)
client.add_device(InputClient())
client.run()
