
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
                self._unfinished_command = f(msg['params'])
                command_state = next(self._unfinished_command)

            else:
                self.response_error('Unkown command: {}'.format(msg['command']))
                return

        # Execute the command
        if command_state == Status.FINISHED:
            self._unfinished_command = None


    def addclient(self, params):
        (client_url, client_alias) = params
        try:
            self._engine.add_client(client_url, client_alias)
            self._config.add_client(client_url, client_alias)
            self.response_text('Successfully added client "{}({})"'.format(client_alias, client_url), finished=True)
        except EngineError as e:
            self.response_error('Could not add client "{}({})": {}'.format(client_alias, client_url, e))

        yield Status.FINISHED

    def updateclient(self, params):
        (client_alias, poll_period) = params
        client_info = self._config['clients'][client_alias]

        try:
            self._swb.update_client(client_alias, poll_period)
            self._config.add_client(client_info['url'], client_alias, poll_period)
            self.response_text('Successfully updated client "{}"'.format(client_alias), finished=True)
        except EngineError as e:
            self.response_error('Could not update client "{}": {}'.format(client_alias, e))

        yield Status.FINISHED

    def launchapp(self, params):
        return self._app_manager.launch(params[0], self)


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

