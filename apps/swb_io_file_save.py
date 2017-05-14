''' IOFileSave is a dumb IOData Agent that saves raw IO updates to a file.
    This can be useful when debugging a Switchboard module. '''

from switchboard.utils import get_input
from switchboard.iodata import AgentBase
from switchboard.app import IODataApp

import json

class IOFileSave(AgentBase):
    def __init__(self):
        self.data_entries = []

    def set_configs(self, max_entries, file_name):
        if max_entries == 'infinite':
            self.max_entries = None
        else:
            self.max_entries = int(max_entries)
        self.file_name = file_name

    def _write_entry(self, line):
        self.data_entries.append(line)
        if self.max_entries:
            while len(self.data_entries) > self.max_entries:
                self.data_entries.pop(0)

        with open(self.file_name, 'w') as fp:
            for entry in self.data_entries:
                fp.write(json.dumps(entry) + '\n')

    def connected(self):
        pass

    def disconnected(self):
        pass

    def update_io_data(self, state_table, updates):
        self._write_entry(updates)

    def reset_io_data(self, state_table):
        self._write_entry(state_table)


def main():
    file_save = IOFileSave()
    app = IODataApp(iodata_agent=file_save, configs={
            'file name': {
                'args': ['--file_name', '-f'],
                'kwargs': { 'help': 'Name of the file we want to save the IOData to' }
            },
            'max entry count': {
                'args': ['--max_entries', '-m'],
                'kwargs': {
                    'help': 'Maximum number of entries to be stored in the file',
                    'default': 'infinite'
                }
            }
        })

    if not app.args.file_name:
        print('Cannot run IO File save: missing "--max_entries" or "--file_name" arguments')
        sys.exit(1)

    file_save.set_configs(app.args.max_entries, app.args.file_name)

    app.run()


if __name__ == '__main__':
    main()
