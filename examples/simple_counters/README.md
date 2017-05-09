# Description

This simple counter example shows the bare minimum required to get a Switchboard setup running. client1.py is a standalone Switchboard client that provides an integer that increments every time the client is polled. client2.py is an output Switchboard device that simply prints the value it receives. the test_module.py is the module logic that takes the input from client1, multiplies it by 2 and sets that value to the output of client2. The settings.json file is pre-configured to connect to the clients and load the module.

# How to run

(Make sure to have switchboard and all its dependencies installed!)

1. Open three windows and cd to the switchboard/examples/simple_counters directory
2. In one terminal run: `python client1.py --port 51000`
3. In another run: `python client2.py --port 51001`
4. In a third terminal launch Switchboard pointing it to the config file: `switchboard -c settings.json`
5. Now you should be in the switchboard command line interface. To get the module executing type `start`
6. You should see client1 receiving get requests and printing incrementing numbers, and client2 receiving put and get requests and printing numbers twice the value of client1

# How to manually configure Switchboard

The previous guide used a ready-made settings file. Here are the steps on how the settings file can be created during configuration:

1. Do all the steps up to step 4. and execute Switchboard with a different settings file name `switchboard -c settings2.json`
2. You will be prompted for the polling period which determines how frequently Switchboard refreshes its input values and executes Switchboard modules. A value of 1 will do here.
3. Add the client1 host and assign the 'client1' alias to it with `addhost localhost:51000 client1`
4. Same for client2: `addhost localhost:51001 client2`
5. Add the Switchboard module `addmodule test_module.module`
6. Enter `start` and make sure the output is correct
