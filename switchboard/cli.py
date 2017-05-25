''' Command Line Input module for Switchboard '''

import cmd
import sys

from switchboard.engine import EngineError
from switchboard.utils import colour_text

from apps.app_list import APP_LIST


def AutoComplete(text, line, options):
    ''' Generic auto-complete function to make it easier to write
        complete_ functions for cmd. text is the text of the current
        word, line is the input line as it currently is, and options
        are iterable objects (dicts if nested) that contain the entire
        search space of available options. '''
    parts = line.split()
    idx = len(parts) - 1
    if not text:
        idx = len(parts)

    try:
        for part in parts[1:idx]:
            options = options[part]
    except Exception:
        return []

    return [ opt_list for opt_list in options if opt_list.startswith(text) ]


class SwitchboardCli(cmd.Cmd, object):
    def lock_switchboard(f):
        ''' Decorator for functions that need to synchonrise with the
            Switchboard engine before executing '''
        def wrapper(self, line):
            with self._swb.lock:
                f(self, line)
        return wrapper

    def __init__(self, swb, config, iodata, app_manager):
        super(SwitchboardCli, self).__init__()
        self._swb = swb
        self._config = config
        self._iodata = iodata
        self._app_manager = app_manager

        # Pre-load the possible config variables for auto-completion
        self._config_vars = { }
        for key, opt in self._config.CONFIG_OPTS.items():
            if opt['type'] == str:
                self._config_vars[key] = opt

    def run(self):
        ''' Blocking cmd input loop '''
        self.update_prompt()
        self.cmdloop()

    def postcmd(self, stop, line):
        self.update_prompt()
        return stop

    def update_prompt(self):
        if self._swb.running:
            self.prompt = colour_text('(running) ', 'green')
        else:
            self.prompt = colour_text('(stopped) ', 'red')

    def help_addclient(self):
        print('Usage:')
        print('addclient [client] [alias]   add client and assign alias to it')

    @lock_switchboard
    def do_addclient(self, line):
        parts = line.split()
        if len(parts) != 2:
            print('"addclient" command expects two parameters')
            self.help_addclient()
            return

        (client_url, client_alias) = parts

        if not client_url.startswith('http://'):
            client_url = 'http://' + client_url

        try:
            self._swb.add_client(client_url, client_alias)
            self._config.add_client(client_url, client_alias)
        except EngineError as e:
            print('Could not add client "{}({})": {}'.format(client_alias, client_url, e))


    def help_updateclient(self):
        print('Usage:')
        print('updateclient [client alias]  update the given client')

    @lock_switchboard
    def do_updateclient(self, line):
        try:
            self._swb.update_client(line)
            self._config.add_client(line)
        except EngineError as e:
            print('Could not update client "{}": {}'.format(line, e))

    def complete_updateclient(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self._swb.clients)


    def help_launchapp(self):
        print('Usage:')
        print('launchapp [app]      launches app and connects to it if neccesary')

    @lock_switchboard
    def do_launchapp(self, line):
        self._app_manager.launch(line)

    def complete_launchapp(self, text, line, begidx, endidx):
        return AutoComplete(text, line, APP_LIST)


    def help_killapp(self):
        print('Usage:')
        print('killapp [app]        kill app that is already running')

    @lock_switchboard
    def do_killapp(self, line):
        self._app_manager.kill(line)

    def complete_killapp(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self._app_manager.apps_running.keys())


    def help_addmodule(self):
        print('Usage:')
        print('addmodule [module]   add and enable Switchboard module')

    @lock_switchboard
    def do_addmodule(self, line):
        try:
            self._swb.upsert_switchboard_module(line)
            self._config.add_module(line)
        except EngineError as e:
            print('Couldn not add module "{}": {}'.format(line, e))

    def complete_addmodule(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self._swb.modules)


    def help_enable(self):
        print('Usage:')
        print('enable [module]      enable Switchboard module')

    @lock_switchboard
    def do_enable(self, line):
        self._swb.enable_switchboard_module(line)

    def complete_enable(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self._swb.modules)


    def help_disable(self):
        print('Usage:')
        print('disable [module]     disable Switchboard module')

    @lock_switchboard
    def do_disable(self, line):
        self._swb.disable_switchboard_module(line)

    def complete_disable(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self._swb.modules)


    def help_list(self):
        print('Usage:')
        print('list clients         list all the clients')
        print('list devices         list all the devices')
        print('list values          list all the input device values')
        print('list apps            list all the running apps')

    @lock_switchboard
    def do_list(self, line):
        def iter_clients():
            if not self._swb.clients:
                print('No clients registered')
            else:
                print('Clients:')
                for name, client_obj in self._swb.clients.items():
                    yield name, client_obj

        def get_max_length_str(strings):
            max_length = 0
            for s in strings:
                max_length = max(max_length, len(s))
            return max_length

        def get_status(entity):
            if entity.error:
                return colour_text(entity.error, 'red')
            else:
                return colour_text('OK', 'green')

        clients = self._swb.clients.items()

        if not line:
            print('Empty list argument')
            self.help_list()

        elif line.lower() in 'clients':
            spacing = get_max_length_str(n for n, _ in clients)
            spacing += 4
            for name, client_obj in iter_clients():
                print('\t{client:{width}}{status}'.format(
                    client=name,
                    width=spacing,
                    status=get_status(client_obj)
                ))

        elif line.lower() in 'devices':
            device_names = self._swb.devices.keys()
            spacing = get_max_length_str(device_names)
            spacing += 4
            for name, client_obj in iter_clients():
                print('{}'.format(name))
                for name, device_obj in client_obj.devices.items():
                    print('\t{device:{width}}{status}'.format(
                        device=name,
                        width=spacing,
                        status=get_status(device_obj)))

        elif line.lower() in 'values':
            spacing = get_max_length_str(self._swb.devices.keys())
            spacing += 4
            for name, client_obj in iter_clients():
                print('{}'.format(name))
                for name, device_obj in client_obj.devices.items():
                    value = device_obj.value
                    if device_obj.error:
                        value = colour_text(device_obj.error, 'red')
                    print('\t{device:{width}}: {value}'.format(
                        device=name,
                        width=spacing,
                        value=value))

        elif line.lower() in 'apps':
            print('Apps running:')
            for app in self._app_manager.apps_running:
                print('\t{}'.format(app))

        else:
            print('Unkown list command "{}"'.format(line))
            self.help_list()

    def complete_list(self, text, line, begidx, endidx):
        options = [ 'clients', 'devices', 'values', 'apps' ]
        return AutoComplete(text, line, options)


    def help_get(self):
        print('Usage:')
        print('get [device]         show value of device')
        print('get [config]         show value of a config option')
        for key, opt in self._config_vars.items():
            print('get {:<17}{}'.format(key, opt['desc']))

    @lock_switchboard
    def do_get(self, line):
        parts = line.split()
        if len(parts) != 1:
            print('"get" command expects one parameter')
            self.help_get()
            return

        target = parts[0]

        if target in self._swb.devices:
            # Print the value for this device
            device = self._swb.devices[target]
            if not device.is_input:
                print('Error: device {} not readable'.format(device.name))
            else:
                print('{}: {}'.format(device.name, device.value))

        elif target.lower() in list(self._config_vars.keys()):
            print('{}: {}'.format(target, self._config.get(target.lower())))

        else:
            print('Invalid get target "{}"'.format(target))
            self.help_get()

    def complete_get(self, text, line, begidx, endidx):
        options = list(self._config_vars.keys())
        for name, device in self._swb.devices.items():
            if device.is_input:
                options.append(name)
        return AutoComplete(text, line, options)


    def help_set(self):
        print('Usage:')
        print('set [device] [value]    set device to given value')
        print('set [config] [value]    set config option to given value')
        for key, opt in self._config_vars.items():
            print('set {:<19} {}'.format(key + " [value]", opt['desc']))

    @lock_switchboard
    def do_set(self, line):
        parts = line.split()
        if len(parts) != 2:
            print('"set" command expects two parameters')
            self.help_set()
            return

        (target, value) = parts

        if target in self._swb.devices:
            self._swb.devices[target].output_signal.set_value(value)

        elif target.lower() in list(self._config_vars.keys()):
            err = self._config.set(target, value)
            if err != None:
                print('Error: {}'.format(err))

        else:
            print('Invalid set target "{}"'.format(target))
            self.help_get()

    def complete_set(self, text, line, begidx, endidx):
        options = list(self._config_vars.keys())
        for name, device in self._swb.devices.items():
            if device.is_output:
                options.append(name)
        return AutoComplete(text, line, options)


    def help_start(self):
        print('Usage:')
        print('start                starts switchboard (poll_period must be set)')

    @lock_switchboard
    def do_start(self, line):
        if not self._config.get('poll_period'):
            print('Unable to start switchboard as poll_period is not set')
            return

        if not self._swb.running:
            self._swb.running = True
            self._config.set('running', True)
        else:
            print('Switchboard server already running')


    def help_stop(self):
        print('Usage:')
        print('stop                 stops switchboard')

    @lock_switchboard
    def do_stop(self, line):
        if not self._swb.running:
            self._config.set('running', False)
            print('Switchboard server is not running')
        else:
            self._swb.running = False


    def do_exit(self, line):
        return True


    def do_EOF(self, line):
        return True

