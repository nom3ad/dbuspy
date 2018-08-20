import os
from .client import Client
import socket


__all__ = ['session_bus']

def session_bus():
    return get_client('session')

def system_bus():
    return get_client('system')





DEFULAT_SYSTEM_BUS_ADDRESS = "unix:path=/var/run/dbus/system_bus_socket"

def get_client(bus_adress):
    """
    'session', 'system', or a valid bus address as defined
    by the DBus specification. If 'session' (the default) or 'system' is
    supplied, the contents of the DBUS_SESSION_BUS_ADDRESS or
    DBUS_SYSTEM_BUS_ADDRESS environment variables will be used for the bus
    address, respectively. If DBUS_SYSTEM_BUS_ADDRESS is not set, the
    well-known address unix:path=/var/run/dbus/system_bus_socket will be
    used.
    """

    if bus_adress == 'session':
        addr = os.environ.get('DBUS_SESSION_BUS_ADDRESS', None)
        if addr is None:
            raise Exception('DBus Session environment variable not set')

    elif bus_adress == 'system':
        addr = os.environ.get(
            'DBUS_SYSTEM_BUS_ADDRESS',
            DEFULAT_SYSTEM_BUS_ADDRESS
        )

    else:
        addr = bus_adress

    # TODO: bus adress may be ';' seperated  values
    # single address format
    #  <kind>:<key1>=<value1>,<key2>=<value2>
    # eg: unix:path=/var/run/dbus/system_bus_socket

    d = {}
    kind = None
    transport = None

    for c in addr.split(','):
        if c.startswith('unix:'):
                kind = 'unix'
                c = c[5:]
        else:
            raise NotImplementedError(c)
        
        if '=' in c:
            k, v = c.split('=')
            d[k] = v

    
    if kind == 'unix':
        transport = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        transport.connect(d['path'])

    return Client(transport)



    
