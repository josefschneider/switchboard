# Description

This simple counter example shows the bare minimum required to get a Switchboard setup running. client1.py is a standalone Switchboard client that provides an integer that increments every time the client is polled. client2.py is an output Switchboard device that simply prints the value it receives. the test_module.py is the module logic that takes the input from client1, multiplies it by 2 and sets that value to the output of client2. The settings.json file is pre-configured to connect to the clients and load the module.

# How to run

(Make sure to have switchboard installed!)

* Open three windows and cd to the switchboard/examples/simple_counters directory
* In one terminal run: `./client1.py`
* In another run: `./client2.py`
* In a third terminal launch Switchboard pointing it to the config file: `switchboard -c settings.json`
* Now you should be in the switchboard command line interface. To get the module executing type `start`
* You should see client1 receiving get requests and printing incrementing numbers, and client2 receiving put and get requests and printing numbers twice the value of client1
