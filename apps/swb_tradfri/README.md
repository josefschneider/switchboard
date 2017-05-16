
# IKEA Tradfri App

Arguments:
    --client_port   Switchboard client port serving the REST Api

## Requirements

In order for this app to run you need to install coap-client:

    sudo apt-get install libtool
    git clone --recursive https://github.com/obgm/libcoap.git
    cd libcoap
    git checkout dtls
    git submodule update --init --recursive
    ./autogen.sh
    ./configure --disable-documentation --disable-shared
    make
    sudo make install
