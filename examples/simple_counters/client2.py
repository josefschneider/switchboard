#!/usr/bin/env python

from switchboard_client.client import SwitchboardClient, SwitchboardOutputDevice

class OutputClient(SwitchboardOutputDevice):
    NAME = 'output.o'

    def __init__(self):
        super(OutputClient, self).__init__(self.NAME, self.set_value)

    def set_value(self, value):
        print('Received value {}'.format(value))


client = SwitchboardClient('0.0.0.0', 4001, quiet=False)
client.add_device(OutputClient())
client.run()
