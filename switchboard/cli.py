
import cmd
import copy

from threading import Thread

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
    except:
        return []

    return [ opt_list for opt_list in options if opt_list.startswith(text) ]


class SwitchboardCli(cmd.Cmd, object):
    def lock_switchboard(f):
        def wrapper(self, line):
            with self._swb.lock:
                f(self, line)
        return wrapper

    def __init__(self, swb, config):
        super(SwitchboardCli, self).__init__()
        self._catch_except = True
        self._swb = swb
        self._config = config
        self._swb_thread = None

        # Pre-load the possible config variables for auto-completion
        self._config_vars = { }
        for key, opt in self._config.CONFIG_OPTS.items():
            if opt['type'] == str:
                self._config_vars[key] = opt

    def run(self):
        ''' Blocking cmd input loop '''
        self.cmdloop()

    def _stop_switchboard(self):
        if self._swb_thread:
            self._swb.terminate = True
            self._swb_thread.join()


    def help_addhost(self):
        print('Usage:')
        print('addhost [host]       add or update the given host')

    @lock_switchboard
    def do_addhost(self, line):
        if not self._catch_except:
            self._swb.upsert_host(line)
            self._config.add_host(line)
        else:
            try:
                self._swb.upsert_host(line)
                self._config.add_host(line)
            except Exception as e:
                print('Could not add host "{}": {}'.format(line, e))

    def complete_addhost(self, text, line, begidx, endidx):
        return AutoComplete(text, line, self._swb.hosts)


    def help_addmodule(self):
        print('Usage:')
        print('addmodule [module]   add and enable Switchboard module')

    @lock_switchboard
    def do_addmodule(self, line):
        self._swb.upsert_switchboard_module(line)

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
                for host, devices in self._swb.hosts.items():
                    yield host, devices

        if not line:
            print('Empty list argument')
            self.help_list()

        elif line.lower() in 'hosts':
            for host, _ in iter_hosts():
                print('\t{}'.format(host))

        elif line.lower() in 'devices':
            for host, devices in iter_hosts():
                print('{}'.format(host))
                for device in devices:
                    print('\t{}'.format(device.name))

        elif line.lower() in 'values':
            for host, devices in iter_hosts():
                print('{}'.format(host))
                input_devices = filter(lambda d: d.is_input, devices)
                if input_devices:
                    for device in input_devices:
                        print('\t{}: {}'.format(device.name, device.value))
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
        print('set [device] [value]    set given device to given value')
        for key, opt in self._config_vars.items():
            print('get {:<19} {}'.format(key + " [value]", opt['desc']))

    @lock_switchboard
    def do_set(self, line):
        parts = line.split()
        if len(parts) != 2:
            print('"set" command expects two parameters')
            self.help_set()
            return

        (target, value) = parts

        if target in self._swb.devices:
            self._swb.devices[target].set_value(value)

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

        if self._swb_thread == None:
            self._swb.running = True
            self._swb_thread = Thread(target=self._swb.run)
            self._swb_thread.start()
        elif not self._swb.running:
            self._swb.running = True
        else:
            print('Switchboard server already running')


    def help_stop(self):
        print('Usage:')
        print('stop                 stops switchboard')

    @lock_switchboard
    def do_stop(self, line):
        if not self._swb.running:
            print('Switchboard server is not running')
        else:
            self._swb.running = False


    def help_catch(self):
        print('Usage:')
        print('catch on             catch exceptions throw - normal usage')
        print('catch off            do not catch exceptions, for debugging')

    def do_catch(self, line):
        if line.lower() in 'on':
            self._catch_except = True
        elif line.lower() in 'off':
            self._catch_except = False
        else:
            print('Unkown argument {}'.format(line))

    def complete_catch(self, text, line, begidx, endidx):
        options = [ 'on', 'off' ]
        return AutoComplete(text, line, options)


    def do_exit(self, line):
        self._stop_switchboard()
        return True


    def do_EOF(self, line):
        self._stop_switchboard()
        return True

