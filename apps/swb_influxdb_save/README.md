
# InfluxDB writer App

Arguments:
    --iodata_port   IOData server port to connect to
    --iodata_host   IOData server host to connect to

    --influx_host   host IP of the InfluxDB server
    --influx_port   listening port of the InfluxDB server (default 8086)
    --username      username for the InfluxDB server (default 'root')
    --password      password for the InfluxDB server (default 'root')
    --db_name       name of InfluxDB database to write to (default 'swb_iodata')
    --session       InfluxDB database session name (default 'swb')
    --run_no        InfluxDB run number (default startup time and date)

## Requirements

For the app to run the only requirement is that the python InfluxDB libraries be installed:

    pip install influxdb

## Getting started with InfluxDB and Grafana

There are many different ways of doing this (direct install, apt-get install, docker...) so this is a rough outline. Assuming that default configs are used and that all applications run on the same machine:
* Go to https://portal.influxdata.com/downloads and download and install for your platform and start the application (details depend on your platform)
* Go to http://docs.grafana.org/installation/ and download and install for your platform and start the application (again, platform dependent)
* Launch the app from Switchboard
    launchapp swb_influxdb_save
* All the default configs should work here
* On the Grafana page (point your browser to localhost:3000) log in as user=admin, password=admin and add the database as your Data Source:
  * Type=InfluxDB
  * Under InfluxDB Details the Database=swb_iodata and User and Password=root
  * Save and Test and you're ready to go!
* Create a Dashboard. This part is very flexible and beyond the scope of this readme but I would recommend experimenting around for a while to get a feel of what Grafana is capable of.
