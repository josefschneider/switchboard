
import json

from switchboard.engine import EngineError

class Status:
    FINISHED = True
    WAITING_FOR_INPUT = False


class CommandDecoder:
    def __init__(self, config, engine):
        self._config = config
        self._engine = engine
        self._unfinished_command = None
        self._ws = None

    def decode_ctrl_command(self, ws, msg_data):
        self._ws = ws

        try:
            msg = json.loads(msg_data)
        except Exception as e:
            self.response_error('Internal error: invalid JSON input "{}"'.format(msg_data))
            return

        if self._unfinished_command and not msg['command'] is 'user_input':
            # We are part way through a multi-step command but we are
            # interrupted by a new, unrelated command
            # TODO: log error
            pass

        elif not self._unfinished_command and msg['command'] is 'user_input':
            # We receive user input for a multi-step command but there is
            # no related command function being executed
            self.response_error('Internal error: unkown destination for user input "{}"'.format(msg['value']))
            return


        if self._unfinished_command and msg['command'] is 'user_input':
            # We are part way through a multi-step command and have
            # received user input (as expected)
            pass

        elif hasattr(self, msg['command']):
            # Get the iterator for a new command
            f = getattr(self, msg['command'])
            self._unfinished_command = f(msg['params'])

        else:
            self.response_error('Unkown command: {}'.format(msg['command']))
            return

        # Execute the command
        if next(self._unfinished_command) == Status.FINISHED:
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

    def response_text(self, text, prompt=False, finished=False):
        assert prompt ^ finished, 'Can only prompt or finish, but not both'
        self._ws.send(json.dumps({ 'command': 'response', 'display_text': text, 'command_finished': finished, 'get_input': prompt }))

    def response_error(self, text):
        self._ws.send(json.dumps({ 'command': 'response', 'display_text': text, 'command_finished': True, 'command_status': 'ERROR' }))

    def response_warning(self, text, prompt=False, finished=False):
        assert prompt ^ finished, 'Can only prompt or finish, but not both'
        self._ws.send(json.dumps({ 'command': 'response', 'display_text': text, 'command_finished': finished, 'get_input': prompt, 'command_status': 'WARNING' }))
