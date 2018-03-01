
import os
import sys
import time
import json
import signal
import requests
import logging
from subprocess import Popen, PIPE

from switchboard.utils import get_input, get_free_port
from switchboard.engine import EngineError
from apps.app_list import APP_LIST

logger = logging.getLogger(__name__)


def format_arg(arg_info, value):
    return ' {} {}'.format(arg_info['args'][0], value)

class AppManager:
    def __init__(self, configs, swb):
        self._configs = configs
        self._swb = swb
        self.apps_running = {}

    def init_config(self):
        for app, app_configs in self._configs.get('apps').items():
            logger.info('Starting ' + app)
            exec_error = self._execute_app(app, app_configs)
            if exec_error:
                logger.error('Unable to start app {}: "{}". Please resolve issue and restart'.format(exec_error))
                sys.exit(1)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        for pid in self.apps_running.values():
            self._terminate(pid)

    def _terminate(self, pid):
        os.killpg(os.getpgid(pid), signal.SIGTERM)

    def kill(self, app, ui):
        if not app in self.apps_running:
            yield ui.response_error('Cannot kill {} app as it was not launched by Switchboard'.format(app))

        # If the app has a client alias it means we are dealing with a Switchboard
        # device client and that we need to remove it
        if 'client_alias' in self._configs.get('apps')[app]:
            alias = self._configs.get('apps')[app]['client_alias']
            yield ui.response_text('Removing client "{}"'.format(alias))
            self._swb.remove_client(alias)

        yield ui.response_text('Killing app')
        self._configs.remove_app(app)
        self._terminate(self.apps_running[app])
        del self.apps_running[app]
        yield ui.response_text('App "{}" successfully killed'.format(app), finished=True)

    def launch(self, app, ui):
        # Get the required config options for this app
        p = Popen(app + ' --getconf', shell=True, stdout=PIPE, preexec_fn=os.setsid)

        # With the --getconf argument the app should quit immediately
        time.sleep(0.1)

        if not p.poll() == None:
            self._terminate(p.pid)
            yield ui.response_error('Error: app hangs when getting config options')

        output, error = p.communicate()

        if error:
            yield ui.response_error('Error: app encountered an error')

        # If the app is a Switchboard client we connect to it automatically
        client_port = None
        app_configs = {}

        # Determine app args and populate them
        try:
            args = json.loads(output)
        except:
            yield ui.response_error('Unable to parse app config definitions')

        command = app
        for name, arg_info in args.items():
            # Pre-populate as many arguments as possible
            if name == 'WSIOData port':
                command += format_arg(arg_info, self._configs.get('ws_port'))
            elif name == 'WSIOData host':
                command += format_arg(arg_info, 'localhost')
            elif name == 'Client port':
                client_port = get_free_port()
                command += format_arg(arg_info, client_port)
            elif name == 'autokill':
                # Because this app is being launched by Switchboard we want it to die when Switchboard dies
                command += ' --autokill'
            else:
                # For every other argument prompt the user
                kwargs = arg_info['kwargs']
                help = kwargs['help']

                if 'action' in kwargs and kwargs['action'] in 'store_true':
                    while True:
                        value = yield ui.response_text('{}? [y/n] '.format(help), prompt=True)
                        value = value.lower()

                        if not value in [ 'y', 'n' ]:
                            yield ui.response_text('Invalid input')
                            continue

                        if value == 'y':
                            command += ' ' + arg_info['args'][0]
                        break
                else:
                    if 'default' in kwargs:
                        default = ' [{}]'.format(kwargs['default'])
                        value = yield ui.response_text('Please enter a value for the {}{}: '.format(help, default), prompt=True)
                        if value:
                            command += format_arg(arg_info, value)
                    else:
                        value = yield ui.response_text('Please enter a value for the {}: '.format(help), prompt=True)
                        command += format_arg(arg_info, value)

        app_configs['command'] = command

        # If this is a client app get the client alias
        if client_port:
            app_configs['client_port'] = client_port
            alias = yield ui.response_text('Please enter a client alias: ', prompt=True)
            app_configs['client_alias'] = alias

        exec_error = self._execute_app(app, app_configs, ui.response_text)
        if exec_error:
            yield ui.response_error(exec_error)
        else:
            self._configs.add_app(app, app_configs)
            yield ui.response_text('App launched successfully', finished=True)

    def _execute_app(self, app, app_configs, print_func=print):
        # Launch the app and make sure it hasn't crashed on us
        p = Popen(app_configs['command'], shell=True, preexec_fn=os.setsid)
        time.sleep(1)
        if not p.poll() == None:
            return 'App has terminated unexpectedly with command: "{}"'.format(app_configs['command'])

        self.apps_running[app] = p.pid

        # If this is a Switchboard device client we need to add it
        if 'client_port' in app_configs or 'client_alias' in app_configs:
            if 'client_port' in app_configs and 'client_alias' in app_configs:
                remaining_attempts = 5
                error = ''
                url = 'http://localhost:' + str(app_configs['client_port'])

                # First check if the server has started up and if it has add the client
                while remaining_attempts:
                    try:
                        requests.get(url + '/devices_info')
                        break
                    except Exception as e:
                        error = e
                        remaining_attempts -= 1
                        time.sleep(1)

                if remaining_attempts == 0:
                    return 'Unable to connect to app client {}: {}'.format(url, error)

                self._swb.add_client(url, app_configs['client_alias'], log_prefix='\t', print_func=print_func)

            else:
                # This error should only really happen if the config file is corrupted
                return 'Cannot add client: client_port or client_alias not defined'
