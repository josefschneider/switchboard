''' Command Line Input module for Switchboard '''

import cmd
import sys

from termcolor import colored

from switchboard.engine import EngineError

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
        if 'win' in sys.platform:
            if self._swb.running:
                self.prompt = '(running) '
            else:
                self.prompt = '(stopped) '
        else:
            if self._swb.running:
                self.prompt = colored('(running) ', 'green')
            else:
                self.prompt = colored('(stopped) ', 'red')

    def help_addhost(self):
        print('Usage:')
        print('addhost [host] [alias]   add host and assign alias to it')

    @lock_switchboard
    def do_addhost(self, line):
        parts = line.split()
        if len(parts) != 2:
            print('"addhost" command expects two parameters')
            self.help_addhost()
            return

        (host_url, host_alias) = parts

        if not host_url.startswith('http://'):
            host_url = 'http://' + host_url

        try:
            self._swb.add_host(host_url, host_alias)
            self._config.add_host(host_url, host_alias)
        except EngineError as e:
            print('Could not add host "{}({})": {}'.format(host_alias, host_url, e))


    def help_updatehost(self):
        print('Usage:')
        print('updatehost [host alias]  update the given host')

    @lock_switchboard
    def do_updatehost(self, line):
        try:
            self._swb.update_host(line)
            self._config.add_host(line)
        except EngineError as e:
            print('Could not update host "{}": {}'.format(line, e))

    def complete_updatehost(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self._swb.hosts)


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
        print('list hosts           list all the hosts')
        print('list devices         list all the devices')
        print('list values          list all the input device values')

    @lock_switchboard
    def do_list(self, line):
        def iter_hosts():
            if not self._swb.hosts:
                print('No hosts registered')
            else:
                print('Hosts:')
                for host, host_obj in self._swb.hosts.items():
                    yield host, host_obj.devices

        if not line:
            print('Empty list argument')
            self.help_list()

        elif line.lower() in 'hosts':
            for host, _ in iter_hosts():
                print('\t{}'.format(host))

        elif line.lower() in 'devices':
            for name, devices in iter_hosts():
                print('{}'.format(name))
                for device in devices:
                    print('\t{}'.format(device))

        elif line.lower() in 'values':
            for name, devices_names in iter_hosts():
                print('{}'.format(name))
                devices = [ self._swb.devices[d] for d in devices_names ]
                input_devices = filter(lambda d: d.is_input, devices)
                if input_devices:
                    for device_obj in input_devices:
                        print('\t{}: {}'.format(device_obj.name, device_obj.value))
                else:
                    print('\tNo input devices')

        else:
            print('Unkown list command "{}"'.format(line))
            self.help_list()

    def complete_list(self, text, line, begidx, endidx):
        options = [ 'hosts', 'devices', 'values' ]
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

