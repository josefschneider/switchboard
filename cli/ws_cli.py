''' Command Line Input module for Switchboard '''

import cmd
import sys
import time

from threading import Thread
from switchboard.ws_ctrl_client import WSCtrlHandlerBase
from switchboard.utils import colour_text, get_input, is_float

from switchboard.config import CONFIG_OPTS
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


class SwitchboardWSCli(cmd.Cmd, WSCtrlHandlerBase):
    def lock_switchboard(f):
        ''' Decorator for functions that need to synchonrise with the
            Switchboard engine before executing '''
        def wrapper(self, *args, **kwargs):
            with self.ws_client.lock:
                f(self, *args, **kwargs)
        return wrapper

    def check_argument_count(argument_count_min, argument_count_max=None):
        ''' Decorator for "do_" commands to be called from the cmd module.
            It takes the input, splits it up and makes sure that the
            desired number of arguments are given '''

        if argument_count_max == None:
            argument_count_max = argument_count_min

        def argument_wrapper(f):
            def wrapper(self, line):
                parts = line.split()

                if len(parts) < argument_count_min or len(parts) > argument_count_max:
                    command = f.__name__[len('do_'):]

                    if argument_count_min != argument_count_max:
                        print('"{}" command expects between {} and {} arguments'.format(command, argument_count_min, argument_count_max))
                    else:
                        print('"{}" command expects {} argument{}'.format(command, argument_count_min, 's' if argument_count_min == 1 else ''))

                    if hasattr(self, 'help_' + command):
                         getattr(self, 'help_' + command)()

                else:
                    f(self, parts)
            return wrapper
        return argument_wrapper


    def __init__(self, stdin=sys.stdin, stdout=sys.stdout):
        super(SwitchboardWSCli, self).__init__(stdin=stdin, stdout=stdout)
        self.config_received = False

        # Pre-load the possible config variables for auto-completion
        self._config_vars = { }
        for key, opt in CONFIG_OPTS.items():
            if opt['type'] == str:
                self._config_vars[key] = opt

    def connected(self, ws):
        pass

    def disconnected(self, ws):
        pass

    def update_io_data(self, state_table, updates):
        pass

    def reset_io_data(self, state_table):
        pass

    def update_current_config(self, config):
        self.config_received = True

    def run(self, host, port):
        sys.stdout.write('Establishing connection')
        ''' Run the websocket client in a separate thread '''
        thread = Thread(target=self.ws_client.run_ws_client,
                kwargs={'host':host, 'port':port, 'autokill':True})
        thread.daemon = True
        thread.start()

        while not self.config_received:
            time.sleep(0.1)
            sys.stdout.write('.')

        print('\nConnection established!')

        ''' Execute the blocking cmd input loop '''
        self.update_prompt()
        self.cmdloop()

    def postcmd(self, stop, line):
        self.update_prompt()
        return stop

    def update_prompt(self):
        if self.ws_client.swb_config['running']:
            self.prompt = colour_text('(running) ', 'green')
        else:
            self.prompt = colour_text('(stopped) ', 'red')

    def emptyline(self):
        ''' Hitting 'Enter' does nothing '''
        pass

    def help_addclient(self):
        print('Usage:')
        print('addclient [client] [alias]   add client and assign alias to it')
        print('addclient [client] [alias] [poll period]')
        print('                             add client and give it a specific')
        print('                             poll period in seconds')

    @check_argument_count(2, 3)
    def do_addclient(self, args):
        client_url = args[0]

        if not client_url.startswith('http://'):
            client_url = 'http://' + client_url

        self.ws_client.send('addclient', [client_url] + args[1:])


    def help_updateclient(self):
        print('Usage:')
        print('updateclient [alias]         update client devices')
        print('updateclient [alias] [poll period]')
        print('                             update client and give it a specific poll')
        print('                             period or "None" to poll at every loop')

    @check_argument_count(1, 2)
    def do_updateclient(self, args):
        client_alias = args[0]
        if not client_alias in self.ws_client.swb_config['clients']:
            print('Error: Unkown client alias "{}"'.format(client_alias))
            return

        client_info = self.ws_client.swb_config['clients'][client_alias]
        poll_period = client_info['poll_period'] if 'poll_period' in client_info else None

        if len(args) == 2:
            if args[1].lower() == 'none':
                poll_period = None
            else:
                if not is_float(args[1]):
                    print('Invalid input: poll period needs to be a float or "None"')
                    return
                poll_period = args[1]
            print('Updating time to {}'.format(poll_period))

        self.ws_client.send('updateclient', [client_alias, poll_period])

    @lock_switchboard
    def complete_updateclient(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self.ws_client.swb_config['clients'].keys())


    def help_launchapp(self):
        print('Usage:')
        print('launchapp [app]      launches app and connects to it if neccesary')

    @check_argument_count(1)
    def do_launchapp(self, args):
        self.ws_client.send('launchapp', args)

    def complete_launchapp(self, text, line, begidx, endidx):
        return AutoComplete(text, line, APP_LIST)


    def help_killapp(self):
        print('Usage:')
        print('killapp [app]        kill app that is already running')

    @check_argument_count(1)
    def do_killapp(self, args):
        self.ws_client.send('killapp', args)

    def complete_killapp(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self.ws_client.swb_config['apps'].keys())


    def help_addmodule(self):
        print('Usage:')
        print('addmodule [module]   add and enable Switchboard module')

    @check_argument_count(1)
    def do_addmodule(self, args):
        print('Adding module')
#        try:
#            self._swb.upsert_switchboard_module(line)
#            self._config.add_module(line)
#        except EngineError as e:
#            print('Could not add module "{}": {}'.format(line, e))

    @lock_switchboard
    def complete_addmodule(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self.ws_client.swb_config['modules'])


    def help_remove(self):
        print('Usage:')
        print('remove [module]      remove existing Switchboard module')
        print('remove [client]      remove existing Switchboard client. Note: cannot remove\n' +
              '                     clients that were added using the "launchapp" command.\n' +
              '                     Use "killapp" to remove such clients.')

    @check_argument_count(1)
    def do_remove(self, args):
        if args[0] in self.ws_client.swb_config['modules']:
            print('Removing module')
#            try:
#                self._swb.remove_module(line)
#                self._config.remove_module(line)
#            except EngineError as e:
#                print('Could not remove module "{}": {}'.format(line, e))
        elif args[0] in self.ws_client.swb_config['clients'].keys():
            try:
                client = args[0]
#                modules = self._swb.get_modules_using_client(client)
#
#                if len(modules) > 0:
#                    p = get_input('Warning, modules {} depend on client {} and will '
#                                  'also be removed. Would you like to proceed? [y/n] '
#                                  ''.format(modules, client))
#                    if p.lower() != 'y':
#                        print('Client not removed')
#                        return
#                    for module in modules:
#                        self._swb.remove_module(module)
#                        self._config.remove_module(module)
#
#                self._swb.remove_client(client)
#                self._config.remove_client(client)
                print('Removed client "{}"'.format(client))

            except EngineError as e:
                print('Could not remove client "{}": {}'.format(args[0], e))
        elif not args[0]:
            print('Incorrect usa of the remove command')
            self.help_remove()
        else:
            print('Unkown module or client "{}"'.format(args[0]))
            self.help_remove()

    @lock_switchboard
    def complete_remove(self, text, line, begidx, endidx):
        return AutoComplete(text, line,
                list(self.ws_client.swb_config['modules']) +
                list(self.ws_client.swb_config['clients'].keys()))


    def help_enable(self):
        print('Usage:')
        print('enable [module]      enable Switchboard module')

    @lock_switchboard
    def do_enable(self, line):
        print('Enable switchboard module')
#        self._swb.enable_switchboard_module(line)

    def complete_enable(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self.ws_client.swb_config['modules'])


    def help_disable(self):
        print('Usage:')
        print('disable [module]     disable Switchboard module')

    @lock_switchboard
    def do_disable(self, line):
        print('Disable switchboard module')
#        self._swb.disable_switchboard_module(line)

    def complete_disable(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self.ws_client.swb_config['modules'])


    def help_list(self):
        print('Usage:')
        print('list clients         list all the clients')
        print('list devices         list all the devices')
        print('list values          list all the input device values')
        print('list apps            list all the running apps')
        print('list modules         list all the loaded modules')

    @lock_switchboard
    def do_list(self, line):
        def iter_clients():
            if not self.ws_client.swb_clients:
                print('No clients registered')
            else:
                print('Clients:')
                for name, client_obj in self.ws_client.swb_clients.items():
                    yield name, client_obj

        def get_max_length_str(strings):
            max_length = 0
            for s in strings:
                max_length = max(max_length, len(s))
            return max_length

        def get_status(entity):
            if 'error' in entity:
                return colour_text(entity['error'], 'red')
            else:
                return colour_text('OK', 'green')

        clients = self.ws_client.swb_clients

        if not line:
            print('Empty list argument')
            self.help_list()

        elif line.lower() in 'clients':
            spacing = get_max_length_str(clients.keys()) + 4
            for name, client_obj in iter_clients():
                if 'poll_period' in client_obj:
                    poll_frequency = client_obj['poll_period'] + 's'
                else:
                    poll_frequency = 'cycle'

                print('\t{client:{width}}{poll:22}{status}'.format(
                    client=name,
                    width=spacing,
                    poll='polled every {}'.format(poll_frequency),
                    status=get_status(client_obj)
                ))

        elif line.lower() in 'devices':
            spacing = get_max_length_str(self.ws_client.devices.keys()) + 4
            for name, client_obj in iter_clients():
                print('{}'.format(name))
                for device_obj in client_obj['devices']:
                    print('\t{device:{width}}{status}'.format(
                        device=device_obj['name'],
                        width=spacing,
                        status=get_status(device_obj)))

        elif line.lower() in 'values':
            spacing = get_max_length_str(self.ws_client.devices.keys()) + 4
            for name, client_obj in iter_clients():
                print('{}'.format(name))
                for device_obj in client_obj['devices']:
                    value = device_obj['value']
                    if 'error' in device_obj:
                        value = colour_text(device_obj['error'], 'red')
                    print('\t{device:{width}}: {value}'.format(
                        device=device_obj['name'],
                        width=spacing,
                        value=value))

        elif line.lower() in 'apps':
            print('Apps running:')
            for app in self.ws_client.swb_config['apps']:
                print('\t{}'.format(app))

        elif line.lower() in 'modules':
            modules = self.ws_client.swb_config['modules']
            spacing = get_max_length_str(modules) + 4
            if len(modules) == 0:
                print('No modules loaded')
            else:
                print('Modules loaded:')
                for m, s in modules.items():
                    if s == 'enabled':
                        status = colour_text('Enabled', 'green')
                    else:
                        status = colour_text('Disabled', 'blue')

                    print('\t{mod:{width}}{status}'.format(
                        mod=m,
                        width=spacing,
                        status=status))

        else:
            print('Unkown list command "{}"'.format(line))
            self.help_list()

    def complete_list(self, text, line, begidx, endidx):
        options = [ 'clients', 'devices', 'values', 'apps', 'modules' ]
        return AutoComplete(text, line, options)


#    def help_get(self):
#        print('Usage:')
#        print('get [device]         show value of device')
#        print('get [config]         show value of a config option')
#        for key, opt in self._config_vars.items():
#            print('get {:<17}{}'.format(key, opt['desc']))
#
#    @lock_switchboard
#    def do_get(self, line):
#        parts = line.split()
#        if len(args) != 1:
#            print('"get" command expects one parameter')
#            self.help_get()
#            return
#
#        target = args[0]
#
#        if target in self.ws_client.devices:
#            # Print the value for this device
#            device = self.ws_client.devices[target]
#            if not device.is_input:
#                print('Error: device {} not readable'.format(device.name))
#            else:
#                print('{}: {}'.format(device.name, device.value))
#
#        elif target.lower() in list(self._config_vars.keys()):
#            print('{}: {}'.format(target, self._config.get(target.lower())))
#
#        else:
#            print('Invalid get target "{}"'.format(target))
#            self.help_get()
#
#    def complete_get(self, text, line, begidx, endidx):
#        options = list(self._config_vars.keys())
#        for name, device in self._swb.devices.items():
#            if device.is_input:
#                options.append(name)
#        return AutoComplete(text, line, options)
#
#
#    def help_set(self):
#        print('Usage:')
#        print('set [device] [value]    set device to given value')
#        print('set [config] [value]    set config option to given value')
#        for key, opt in self._config_vars.items():
#            print('set {:<19} {}'.format(key + " [value]", opt['desc']))
#
#    @lock_switchboard
#    def do_set(self, line):
#        args = line.split()
#        if len(args) != 2:
#            print('"set" command expects two parameters')
#            self.help_set()
#            return
#
#        (target, value) = args
#
#        if target in self._swb.devices:
#            self._swb.devices[target].output_signal.set_value(value)
#
#        elif target.lower() in list(self._config_vars.keys()):
#            err = self._config.set(target, value)
#            if err != None:
#                print('Error: {}'.format(err))
#
#        else:
#            print('Invalid set target "{}"'.format(target))
#            self.help_get()
#
#    def complete_set(self, text, line, begidx, endidx):
#        options = list(self._config_vars.keys())
#        for name, device in self._swb.devices.items():
#            if device.is_output:
#                options.append(name)
#        return AutoComplete(text, line, options)


    def help_start(self):
        print('Usage:')
        print('start                starts switchboard (poll_period must be set)')

    @lock_switchboard
    def do_start(self, line):
        if not self.ws_client.swb_config['running']:
            print('Starting Switchboard')
#            self._swb.running = True
#            self._config.set('running', True)
        else:
            print('Switchboard server already running')


    def help_stop(self):
        print('Usage:')
        print('stop                 stops switchboard')

    @lock_switchboard
    def do_stop(self, line):
        if self.ws_client.swb_config['running']:
            print('Stopping Switchboard')
#            self._config.set('running', False)
#            self._swb.running = False
        else:
            print('Switchboard server already stopped')


    def do_exit(self, line):
        return True


    def do_EOF(self, line):
        return True

