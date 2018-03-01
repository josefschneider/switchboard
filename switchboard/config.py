
import os
import json
import logging

from switchboard.utils import get_input, is_float

logger = logging.getLogger(__name__)

# Different configuration options together with their attributes:
# * desc: optional description of the setting
# * test: a callable function that returns true if the option value
#       is acceptable, and false if not
# * limit: a human readable description of the acceptable option
#       value limits
# * type: the type of the option
CONFIG_OPTS = {
        'poll_period': {
            'desc': 'polling period in seconds',
            'test': lambda x: is_float(x) and float(x) > 0.1,
            'limit': 'a float > 0.1',
            'type': str
        },
        'clients': {
            'test': lambda x: isinstance(x, dict),
            'limit': 'a dict',
            'type': dict
        },
        'modules': {
            'test': lambda x: isinstance(x, dict),
            'limit': 'a dict',
            'type': dict
        },
        'ws_port': {
            'test': lambda x: x > 0 and x < 65536,
            'limit': 'an int > 0 and < 65536',
            'type': int
        },
        'apps': {
            'test': lambda x: isinstance(x, dict),
            'limit': 'a dict',
            'type': dict
        },
        'running': {
            'test': lambda x: isinstance(x, bool),
            'limit': 'a boolean',
            'type': bool
        },
        'logging': {
            'test': lambda x: isinstance(x, dict),
            'limit': 'a dict',
            'type': dict
        }
}


class SwitchboardConfig:
    def __init__(self):
        self._config_file = None

        # Create an empty config to be used if no config file is provided
        self.configs = {}
        for key, opt in CONFIG_OPTS.items():
            args = ()
            self.configs[key] = opt['type'](*args)

        # Sets default poll period. Without this value Switchboard can't start
        self.configs['poll_period'] = "1.0"

        # One handler may register itself to be updated whenever the
        # config changes
        self.config_update_handler = None

    def register_config_update_handler(self, handler):
        self.config_update_handler = handler


    def get(self, key):
        ''' Get a config option of name <key>. If no such option
            exists return None '''

        if key in self.configs:
            return self.configs[key]

        return None


    def set(self, key, value):
        ''' Set a config option of name <key> to <value>. The input
            value is checked to ensure it meets requirements. If
            successful this functions returns None, otherwise it returns
            an error message '''

        logger.info('Setting config value for "{}" to "{}"'.format(key, value))

        if key in self.configs:
            if not CONFIG_OPTS[key]['test'](value):
                err = 'Invalid value "{}" for config option "{}": must be {}'.format(
                        value, key, CONFIG_OPTS[key]['limit'])
                return err

            self.configs[key] = value
            self._save_config()
            return None

        return 'Invalid config option "{}"'.format(key)


    def add_client(self, url, alias, poll_period=None):
        self.configs['clients'][alias] = { 'url': url }
        if poll_period:
            self.configs['clients'][alias]['poll_period'] = poll_period
        self._save_config()

    def remove_client(self, alias):
        if alias in self.configs['clients']:
            del self.configs['clients'][alias]
            self._save_config()


    def add_module(self, module):
        self.configs['modules'][module] = 'enabled'
        self._save_config()

    def remove_module(self, module):
        if module in self.configs['modules']:
            del self.configs['modules'][module]
        self._save_config()

    def enable_module(self, module):
        self.configs['modules'][module] = 'enabled'
        self._save_config()

    def disable_module(self, module):
        self.configs['modules'][module] = 'disabled'
        self._save_config()


    def add_app(self, app, configs):
        if not isinstance(self.configs['apps'], dict):
            self.configs['apps'] = {}
        self.configs['apps'][app] = configs
        self._save_config()

    def remove_app(self, app):
        if app in self.configs['apps']:
            del self.configs['apps'][app]
            self._save_config()


    def load_config(self, file_name):
        ''' Load the json config file. If it doesn't exist creat one
            through an interactive prompt '''

        self._config_file = file_name

        # If the config file does not exist load up store an empty config
        if not os.path.isfile(self._config_file):
            self._save_config()
            return

        # Otherwise read the config file
        with open(self._config_file, 'r') as cfp:
            self.configs = json.load(cfp)

        # Loop through every parameter and check that it exists and is valid
        for key, opt in CONFIG_OPTS.items():
            if not key in self.configs:
                msg = 'Config parameter "{}" not in config file'.format(key)
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
        ''' Save the current config if a config file is specified. Call
            the config update handler'''

        if self._config_file != None:
            with open(self._config_file, 'w') as cfp:
                json.dump(self.configs, cfp, indent=4)

        if self.config_update_handler:
            self.config_update_handler()
