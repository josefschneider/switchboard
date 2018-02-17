
import json

from switchboard.engine import EngineError

class Status:
    FINISHED, CONTINUE, WAITING_FOR_INPUT = range(3)


class CommandDecoder:
    def __init__(self, config, engine, app_manager):
        self._config = config
        self._engine = engine
        self._app_manager = app_manager
        self._unfinished_command = None
        self._ws = None

    def decode_ctrl_command(self, ws, msg_data):
        self._ws = ws
        command_state = Status.CONTINUE

        try:
            msg = json.loads(msg_data)
        except Exception as e:
            self.response_error('Internal error: invalid JSON input "{}"'.format(msg_data))
            return

        if self._unfinished_command and not msg['command'] == 'user_input':
            # We are part way through a multi-step command but we are
            # interrupted by a new, unrelated command
            # TODO: log error
            pass

        elif not self._unfinished_command and msg['command'] == 'user_input':
            # We receive user input for a multi-step command but there is
            # no related command function being executed
            self.response_error('Internal error: unkown destination for user input "{}"'.format(msg['value']))
            return

        while command_state == Status.CONTINUE:
            if self._unfinished_command:
                # We are part way through a multi-step command and have
                # received user input (as expected)
                if msg['command'] == 'user_input':
                    command_state = self._unfinished_command.send(msg['text'])
                else:
                    command_state = next(self._unfinished_command)

            elif hasattr(self, msg['command']):
                # Get the iterator for a new command
                f = getattr(self, msg['command'])
                self._unfinished_command = f(msg['args'])
                command_state = next(self._unfinished_command)

            else:
                self.response_error('Unkown command: {}'.format(msg['command']))
                return

        # Execute the command
        if command_state == Status.FINISHED:
            self._unfinished_command = None


    # Implementations of the commands supported
    def addclient(self, args):
        (client_url, client_alias) = args
        try:
            self._engine.add_client(client_url, client_alias)
            self._config.add_client(client_url, client_alias)
            yield self.response_text('Successfully added client "{}({})"'.format(client_alias, client_url), finished=True)
        except EngineError as e:
            yield self.response_error('Could not add client "{}({})": {}'.format(client_alias, client_url, e))

    def updateclient(self, args):
        (client_alias, poll_period) = args
        client_info = self._config['clients'][client_alias]

        try:
            self._swb.update_client(client_alias, poll_period)
            self._config.add_client(client_info['url'], client_alias, poll_period)
            yield self.response_text('Successfully updated client "{}"'.format(client_alias), finished=True)
        except EngineError as e:
            yield self.response_error('Could not update client "{}": {}'.format(client_alias, e))

    def launchapp(self, args):
        return self._app_manager.launch(args[0], self)

    def killapp(self, args):
        return self._app_manager.kill(args[0], self)

    def addmodule(self, args):
        module_name = args[0]
        try:
            self._engine.upsert_switchboard_module(module_name)
            self._config.add_module(module_name)
            yield self.response_text('Added module "{}"'.format(module_name))
        except EngineError as e:
            yield self.response_error('Could not add module "{}": {}'.format(line, e))

    def remove(self, args):
        if args[0] in self._config['modules']:
            module = args[0]
            try:
                self._engine.remove_module(module)
                self._config.remove_module(module)
                yield self.response_text('Sucessfully removed module "{}"'.format(module), finished=True)
            except EngineError as e:
                yield self.response_error('Could not remove module "{}": {}'.format(module, e))

        elif args[0] in self._config['clients'].keys():
            client = args[0]
            try:
                modules = self._engine.get_modules_using_client(client)

                if len(modules) > 0:
                    p = yield self.response_warning(
                            'Warning: modules {} depend on client {} and will '
                            'also be removed. Would you like to proceed? [y/N] '
                            ''.format(modules, client), prompt=True)

                    if p.strip().lower() != 'y':
                        yield self.response_text('Client not removed', finished=True)

                    for module in modules:
                        self._engine.remove_module(module)
                        self._config.remove_module(module)

                self._engine.remove_client(client)
                self._config.remove_client(client)
                yield self.response_text('Removed client "{}"'.format(client), finished=True)

            except EngineError as e:
                yield self.response_error('Could not remove client "{}": {}'.format(args[0], e))

        else:
            yield self.response_error('Unkown module or client "{}"'.format(args[0]))

    def enable(self, args):
        self._engine.enable_switchboard_module(args[0])
        yield self.response_text('Enabled switchboard module "{}"'.format(args[0]), finished=True)

    def disable(self, args):
        self._engine.disable_switchboard_module(args[0])
        yield self.response_text('Disable switchboard module "{}"'.format(args[0]), finished=True)

    def set(self, args):
        (target, value) = args

        if target in self.swb_client.devices:
            self.swb_client.devices[target].output_signal.set_value(value)

        elif target.lower() in list(self._config_vars.keys()):
            err = self._config.set(target, value)
            if err != None:
                print('Error: {}'.format(err))

        else:
            print('Invalid set target "{}"'.format(target))
            self.help_get()

    def start(self, args):
        self._engine.running = True
        self._config.set('running', True)
        yield self.response_text('Switchboard started', finished=True)

    def stop(self, args):
        self._engine.running = False
        self._config.set('running', False)
        yield self.response_text('Switchboard stopped', finished=True)


    # CMD line response functions for the remote client
    def response_text(self, text, prompt=False, finished=False, additional_fields={}):
        assert not (prompt and finished), 'Can only prompt or finish, but not both'

        command_fields = { 'command': 'response', 'display_text': text, 'command_finished': finished, 'get_input': prompt }
        command_fields.update(additional_fields)

        self._ws.send(json.dumps(command_fields))

        if finished:
            return Status.FINISHED
        elif prompt:
            return Status.WAITING_FOR_INPUT
        else:
            return Status.CONTINUE

    def response_error(self, text):
        return self.response_text(text, prompt=False, finished=True, additional_fields={ 'command_status': 'ERROR' })

    def response_warning(self, text, prompt=False, finished=False):
        return self.response_text(text, prompt=prompt, finished=finished, additional_fields={ 'command_status': 'WARNING' })

