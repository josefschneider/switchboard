
import os
import time
import json
import signal
from subprocess import Popen, PIPE

from switchboard.utils import get_input, get_free_port
from switchboard.engine import EngineError
from apps.app_list import APP_LIST

def format_arg(arg_info, value):
    return ' {} {}'.format(arg_info['args'][0], value)

class AppManager:
    def __init__(self, configs, swb):
        self._configs = configs
        self._swb = swb
        self.apps_running = {}

    def init_config(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        for pid in self.apps_running.values():
            self._terminate(pid)

    def _terminate(self, pid):
        os.killpg(os.getpgid(pid), signal.SIGTERM)

    def launch(self, application):
        if not application in APP_LIST:
            print('Unkown app "{}"'.format(application))
            return

        # Get the required config options for this app
        p = Popen(application + ' --getconf', shell=True, stdout=PIPE, preexec_fn=os.setsid)
        time.sleep(0.1)

        if not p.poll() == None:
            self._terminate(p.pid)
            print('Error: application hangs when getting config options')
            return

        output, error = p.communicate()

        if error:
            print('Error: application encountered an error')
            return

        # If the app is a Switchboard client we connect to it automatically
        client_port = None
        app_configs = {}

        # Determine app args and populate them
        try:
            args = json.loads(output)
        except:
            print('Unable to parse application config definitions')
            return

        command = application
        for name, arg_info in args.items():
            # Pre-populate as many arguments as possible...
            if name == 'IOData port':
                command += format_arg(arg_info, self._configs.get('iodata_port'))
            elif name == 'IOData host':
                command += format_arg(arg_info, 'localhost')
            elif name == 'Client port':
                client_port = get_free_port()
                command += format_arg(arg_info, client_port)
            elif name == 'autokill':
                command += ' --autokill'
            else:
                # ...for every other argument prompt the user
                kwargs = arg_info['kwargs']
                help = kwargs['help']

                if 'action' in kwargs and kwargs['action'] in 'store_true':
                    while True:
                        value = get_input('{}? [y/n] '.format(help))
                        value = value.lower()
                        if not value in [ 'y', 'n' ]:
                            print('Invalid input')
                            continue
                        if value == 'y':
                            command += ' ' + arg_info['args'][0]
                        break
                else:
                    if 'default' in kwargs:
                        default = ' [{}]'.format(kwargs['default'])
                        value = get_input('Please enter a value for the {}{}: '.format(help, default))
                        if value:
                            command += format_arg(arg_info, value)
                    else:
                        value = get_input('Please enter a value for the {}: '.format(help))
                        command += format_arg(arg_info, value)

        # Launch the app and make sure it hasn't crashed on us
        p = Popen(command, shell=True, preexec_fn=os.setsid)
        time.sleep(0.1)
        if not p.poll() == None:
            print('App has terminated unexpectedly with command: {}'.format(command))
            return

        app_configs['command'] = command

        # If this is a client app we need to add the host
        if client_port:
            app_configs['client_port'] = client_port
            alias = get_input('Please enter a host alias for this client: ')
            app_configs['host_alias'] = alias
            try:
                url = 'http://localhost:' + str(client_port)
                self._swb.add_host(url, alias)
            except EngineError as e:
                print('Unable to connect to app host {}: {}'.format(url, e))

        self._configs.add_app({ application: app_configs })
        self.apps_running[application] = p.pid
