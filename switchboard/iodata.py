

def make_state_table(hosts, devices):
    ''' Convert hosts and devices into a brand new state table '''
    table = []
    for host in hosts.values():
        host_entry = { 'host_url': host.url, 'host_alias': host.alias , 'devices': [] }
        devices_entries = host_entry['devices']
        for device in host.devices:
            d_obj = devices[device]
            device_entry = { 'name': d_obj.name,
                    'value': d_obj.value,
                    'last_set_value': d_obj.last_set_value }
            devices_entries.append(device_entry)
        table.append(host_entry)
    return table


class IOData:
    ''' IOData receives the entire Switchboard IO state at every tick
        and converts the progression of the IO state into a list of diffs.

        Registered data consumers are notified every time there is an
        update. '''

    def __init__(self):
        self._current_state_table = []
        self._data_consumers = []

    def add_consumer(self, consumer):
        ''' Register a consumer for IOData updates '''
        self._data_consumers.append(consumer)

    def _determine_table_updates(self, devices):
        updates = []

        for host_entry in self._current_state_table:
            for device in host_entry['devices']:
                d_obj = devices[device['name']]
                if device['value'] != d_obj.value or device['last_set_value'] != d_obj.last_set_value:
                    update = {'device': d_obj.name,
                            'value': d_obj.value,
                            'last_set_value': d_obj.last_set_value }
                    updates.append(update)

                    # Update the current_state_table
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
                for consumer in self._data_consumers:
                    consumer.update_io_data(self._current_state_table, updates)
        else:
            # The state table has been reset. Create a new one.
            self._current_state_table = make_state_table(hosts, devices)
            for consumer in self._data_consumers:
                consumer.reset_io_data(self._current_state_table)
