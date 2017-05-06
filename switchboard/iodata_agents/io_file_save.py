''' IOFileSave is a dumb IOData Agent that saves raw IO updates to a file.
    This can be useful when debugging a Switchboard module. '''

from switchboard.utils import get_input
from switchboard.agent_base import AgentBase

import json

class IOFileSave(AgentBase):
    def __init__(self, configs):
        super(IOFileSave, self).__init__(configs)
        self.data_entries = []

    def init_configs(self):
        configs = {}
        while True:
            file_name = get_input('Please enter the file name: ')
            try:
                fp = open(file_name, 'w')
                fp.close()
                configs['file_name'] = file_name
                break
            except OSError:
                print('Error: invalid filename')

        while True:
            max_update_count = get_input('Please enter the maximum update count to be stored [None]: ')
            if not max_update_count:
                configs['max_update_count'] = None
                break
            if max_update_count.isdigit():
                configs['max_update_count'] = int(max_update_count)
                break
            print('Error: maximum line count must be a number or empty for infinite maximum update count')

        return configs

    def _write_entry(self, line):
        self.data_entries.append(line)
        if self.configs['max_update_count']:
            while len(self.data_entries) > self.configs['max_update_count']:
                self.data_entries.pop(0)

        with open(self.configs['file_name'], 'w') as fp:
            for entry in self.data_entries:
                fp.write(json.dumps(entry) + '\n')

    def update_io_data(self, state_table, updates):
        self._write_entry(updates)

    def reset_io_data(self, state_table):
        self._write_entry(state_table)

