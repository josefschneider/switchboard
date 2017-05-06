''' Base class that every IOData agent should inherit from '''

class AgentBase:
    def __init__(self, configs):
        self.configs = configs
        if not self.configs:
            self.configs = self.init_configs()

    def get_configs(self):
        return self.configs

    def init_configs(self):
        '''init_configs method required to interactively configure the agent'''
        raise NotImplementedError(self.init_configs.__doc__)

    def update_io_data(self, state_table, updates):
        '''update_io_data method required to update device values'''
        raise NotImplementedError(self.update_io_data.__doc__)

    def reset_io_data(self, state_table):
        '''reset_io_data method required to indicate a possible state table format change'''
        raise NotImplementedError(self.reset_io_data.__doc__)
