''' Base class that every IOData agent should inherit from '''

class AgentBase:
    def get_configs(self):
        '''get_configs method required that returns the agent config in JSON format'''
        raise NotImplementedError(self.get_configs.__doc__)

    def update_io_data(self, state_table, updates):
        '''update_io_data method required to update device values'''
        raise NotImplementedError(self.update_io_data.__doc__)

    def reset_io_data(self, state_table):
        '''reset_io_data method required to indicate a possible state table format change'''
        raise NotImplementedError(self.reset_io_data.__doc__)
