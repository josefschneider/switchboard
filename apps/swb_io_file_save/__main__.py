''' IOFileSave is a dumb WSIOData app that saves raw IO updates to a file.
    This can be useful when debugging a Switchboard module. '''

from switchboard.utils import get_input
from switchboard.ws_ctrl import WSIODataHandlerBase
from switchboard.app import WSIODataApp

import json

class IOFileSave(WSIODataHandlerBase):
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

    def connected(self, ws):
        pass

    def disconnected(self, ws):
        pass

    def update_io_data(self, state_table, updates):
        self._write_entry(updates)

    def reset_io_data(self, state_table):
        self._write_entry(state_table)


def main():
    file_save = IOFileSave()
    app = WSIODataApp(ws_handler=file_save, configs={
            'file name': {
                'args': ['--file_name', '-f'],
                'kwargs': { 'help': 'name of the file we want to save the Switchboard data to' }
            },
            'max entry count': {
                'args': ['--max_entries', '-m'],
                'kwargs': {
                    'help': 'maximum number of entries to be stored in the file',
                    'default': 'infinite'
                }
            }
        })

    if not app.args.file_name:
        print('Cannot run IO File save: missing "--file_name" argument')
        sys.exit(1)

    file_save.set_configs(app.args.max_entries, app.args.file_name)

    app.run()


if __name__ == '__main__':
    main()
