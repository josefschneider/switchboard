# switchboard
Switchboard Automation Framework

## Description

IoT automation is conceptually simple: when (a) happens do (b) and wait 3 seconds before also do (c). But what if (a) comes from a Raspberry Pi, (b) is a desktop computer and (c) an ESP8266 WiFi module? Who should be in charge of controlling this functionality? What should we do if WiFi becomes temporarily unavailable?

These are a few of the many hard questions I had to ask myself when deciding how to connect my devices together in a meaningful way. To this end I've been slowly piecing together a Python framework called Switchboard which takes care of device connectivity, availability, is easy to write logic for and is dynamically configurable through a command line interface.

## Switchboard functionality and features:

* the Switchboard framework runs on a base station (x86 computer or Raspberry Pi)
* polls Switchboard clients via a simple HTTP REST Api
* input and output devices can be directly read from and written to by a Switchboard module, which is effectively a function with a decorator
* writing a Switchboard module is DEAD EASY: 1) specify a decorator with the desired inputs and outputs, 2) specify arguments to match the inputs and the outputs and 3) write your logic, knowing that all the connectivity is taken care of
* Python and C++ ESP8266 Switchboard client libraries (maybe also Arduino with an Ethershield if I get round to it)
* resilient to network outage
* easy to use command line prompt for dynamic Switchboard configuration: adding, updating or removing a piece of functionality is performed without affecting unrelated devices and modules

## Getting started

1. Download repository
2. Run `pip setup.py install`
3. To execute, run `switchboard -c <settings file>`. `-c` can be used to specify a settings file and is optional.
