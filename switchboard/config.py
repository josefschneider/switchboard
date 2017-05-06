
import os
import json
from email.utils import parseaddr

from switchboard.utils import get_input

def is_float(string):
    try:
        float(string)
        return True
    except:
        return False


class SwitchboardConfig:
    # Different configuration options together with their attributes:
    # * desc: only available for string options that can be entered by
    #       the user, this field provides a description of the option
    # * test: a callable function that returns true if the option value
    #       is acceptable, and false if not
    # * limit: a human readable description of the acceptable option
    #       value limits
    # * type: the type of the option
    # * default: the arguments assigned to the option instance when it
    #       is constructed
    CONFIG_OPTS = {
            'poll_period': {
                'desc': 'polling period in seconds',
                'test': lambda x: is_float(x) and float(x) > 0.1,
                'limit': 'a float > 0.1',
                'type': str,
                'default': ('1')
            },
            'hosts': {
                'test': lambda x: isinstance(x, list),
                'limit': 'a list',
                'type': list
            },
            'modules': {
                'test': lambda x: isinstance(x, list),
                'limit': 'a list',
                'type': list
            },
            'iodata_agents': {
                'test': lambda x: isinstance(x, dict),
                'limit': 'a dictionary',
                'type': dict
            }
    }


    def __init__(self):
        self._config_file = None

        # Create an empty config to be used if no config file is provided
        self.configs = {}
        for key, opt in self.CONFIG_OPTS.items():
            args = ()
            if 'default' in opt:
                args = (opt['default'])
            self.configs[key] = opt['type'](*args)


    def get(self, key):
        ''' Get a string config option of name <key>. If no such option
            exists return None '''

        if key in self.configs:
            return self.configs[key]

        return None


    def set(self, key, value):
        ''' Set a string config option of name <key> to <value>. The
            input value is checked to ensure it meets requirements. If
            successful this functions returns None, otherwise it returns
            an error message '''

        if key in self.configs and isinstance(self.configs[key], str):
            if not self.CONFIG_OPTS[key]['test'](value):
                err = 'Invalid value "{}" for config option "{}": must be {}'.format(
                        value, key, self.CONFIG_OPTS[key]['limit'])
                return err

            self.configs[key] = value
            self._save_config()
            return None

        return 'Invalid config option "{}"'.format(key)


    def add_host(self, host, alias):
        self.configs['hosts'].append([ host, alias ])
        self._save_config()


    def add_module(self, module):
        self.configs['modules'].append(module)
        self._save_config()


    def add_agent(self, agent, configs):
        self.configs['iodata_agents'][agent] = configs
        self._save_config()


    def load_config(self, file_name):
        ''' Load the json config file. If it doesn't exist creat one
            through an interactive prompt '''

        print("Loading config...")
        self._config_file = file_name

        # If the config file does not exist start up the interactive
        # cmd line init function
        if not os.path.isfile(self._config_file):
            self._initial_setup()
            return

        # Otherwise read the config file
        with open(self._config_file, 'r') as cfp:
            self.configs = json.load(cfp)

        # Loop through every parameter and check that it exists and is valid
        for key, opt in self.CONFIG_OPTS.items():
            if not key in self.configs:
                msg = 'Config parameter {} not in config file'.format(key)
                raise Exception(msg)

            if not isinstance(self.configs[key], opt['type']):
                msg = 'Invalid config type "{}" for parameter "{}". It must be "{}".'.format(
                        type(self.configs[key]),
                        key,
                        opt['type'])
                raise Exception(msg)

            if not opt['test'](self.configs[key]):
                msg = 'Invalid config value "{}" for parameter "{}". It must be {}.'.format(
                        self.configs[key],
                        key,
                        opt['limit'])
                raise Exception(msg)


    def _save_config(self):
        ''' Save the current config if a config file is specified '''

        if self._config_file != None:
            with open(self._config_file, 'w') as cfp:
                json.dump(self.configs, cfp, indent=4)


    def _initial_setup(self):
        ''' Perform the initial interactive Switchboard setup for the
            user-visible string config options and save to config file '''

        for key, opt in self.CONFIG_OPTS.items():
            if 'desc' in opt:
                self._get_input(key, opt)

        self._save_config()


    def _get_input(self, key, opt):
        ''' Reusable function to get config value, test it and store it '''

        while True:
            value = get_input('Please enter {}: '.format(opt['desc']))

            if opt['test'](value):
                self.configs[key] = value
                return

            print('Input value must be {}'.format(opt['limit']))

