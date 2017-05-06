
from switchboard.utils import load_attribute

# List of IOData agents that come Out Of The Box with the Switchboard installation
OOTB_AGENTS = {
    'Dashboard': 'switchboard.iodata_agents.dashboard.Dashboard',
    'IOFileSave': 'switchboard.iodata_agents.io_file_save.IOFileSave'
}

def make_state_table(hosts, devices):
    ''' Convert hosts and devices into a brand new state table '''
    table = []
    for host in hosts.values():
        host_entry = { 'host_url': host.url, 'host_alias': host.alias , 'devices': [] }
        devices_entries = host_entry['devices']
        for device in host.devices:
            d_obj = devices[device]
            device_entry = {
                    'last_update_time': str(d_obj.last_update_time),
                    'name': d_obj.name,
                    'value': d_obj.value,
                    'last_set_value': d_obj.last_set_value }
            devices_entries.append(device_entry)
        table.append(host_entry)
    return table


class IOData:
    ''' IOData receives the entire Switchboard IO state at every tick
        and converts the progression of the IO state into a list of diffs.

        All agents are notified every time there is an update. '''

    def __init__(self, config):
        self._config = config

        # The last known state of the Switchboard IOs
        self._current_state_table = []

        # Out Of The Box agents
        self.ootb_agents = OOTB_AGENTS

        # Dictionary of agent name -> agent instantiation
        self._agents = {}

    def init_config(self):
        for agent, configs in self._config.get('iodata_agents').items():
            print('Adding {} agent'.format(agent))
            self.add_agent(agent, configs)

    def add_agent(self, agent, agent_configs={}):
        if agent in self.ootb_agents:
            agent = self.ootb_agents[agent]

        agent_obj = load_attribute(agent)(agent_configs)
        self._agents[agent] = agent_obj
        agent_obj.reset_io_data(self._current_state_table)
        return agent_obj.get_configs()

    def _determine_table_updates(self, devices):
        updates = []

        for host_entry in self._current_state_table:
            for device in host_entry['devices']:
                d_obj = devices[device['name']]
                if device['value'] != d_obj.value or device['last_set_value'] != d_obj.last_set_value:
                    update = {
                            'last_update_time': str(d_obj.last_update_time),
                            'device': d_obj.name,
                            'value': d_obj.value,
                            'last_set_value': d_obj.last_set_value }
                    updates.append(update)

                    # Update the current_state_table
                    device['last_update_time'] = str(d_obj.last_update_time),
                    device['value'] = d_obj.value
                    device['last_set_value'] = d_obj.last_set_value

        return updates

    def reset_table(self):
        ''' This function is called if the table structure should be updated.
            This happens when hosts or devices are added or removed. '''
        self._current_state_table = []

    def take_snapshot(self, hosts, devices):
        ''' Takes a snapshot of the current IO state and notifies consumers
            of any updates '''
        if self._current_state_table:
            updates = self._determine_table_updates(devices)
            if updates:
                for agent in self._agents.values():
                    agent.update_io_data(self._current_state_table, updates)
        else:
            # The state table has been reset. Create a new one.
            self._current_state_table = make_state_table(hosts, devices)
            for agent in self._agents.values():
                agent.reset_io_data(self._current_state_table)
