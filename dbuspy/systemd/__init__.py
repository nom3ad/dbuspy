from gevent_dbus import system_bus

"""

object: "/org/freedesktop/systemd1"
        interfaces {
            org.freedesktop.Dbus.Introspectable
            org.freedesktop.Dbus.Peer
            org.freedesktop.Dbus.Properties
            org.freedesktop.systemd1.Manager
                methods: {
                    ....
                }
        }
           
"""

BUS_NAME = "org.freedesktop.systemd1"

OBJECT_PATH = "/org/freedesktop/systemd1"

MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"

UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
SERVICE_UNIT_INTERFACE = "org.freedesktop.systemd1.Service"


class SystemdManager(object):

    def __init__(self):
        self._system_bus = system_bus().connect()

    def start_unit(self, unit_name, mode="replace"):
        return self._system_bus.call_remote(OBJECT_PATH, 'StartUnit',
                                            signature="ss",
                                            args=(unit_name, mode),
                                            interface=MANAGER_INTERFACE,
                                            destination=BUS_NAME)

    def stop_unit(self, unit_name, mode="replace"):
        return self._system_bus.call_remote(OBJECT_PATH, 'StopUnit',
                                            signature="ss",
                                            args=(unit_name, mode),
                                            interface=MANAGER_INTERFACE,
                                            destination=BUS_NAME)

    def enable_unit(self, unit_name):
        return self._system_bus.call_remote(OBJECT_PATH, 'EnableUnitFiles',
                                            signature="asbb",
                                            args=([unit_name], False, True),
                                            interface=MANAGER_INTERFACE,
                                            destination=BUS_NAME)

    def disable_unit(self, unit_name):
        return self._system_bus.call_remote(OBJECT_PATH, 'DisableUnitFiles',
                                            signature="asb",
                                            args=([unit_name], False),
                                            interface=MANAGER_INTERFACE,
                                            destination=BUS_NAME)

    def _get_unit(self, unit_name):
        return self._system_bus.call_remote(OBJECT_PATH, 'GetUnit',
                                            signature="s",
                                            args=(unit_name,),
                                            interface=MANAGER_INTERFACE,
                                            destination=BUS_NAME)

    def get_unit_props(self, unit_name):
        unit_path = self._get_unit(unit_name)
        """
        <method name="GetAll">
        <arg name="interface" direction="in" type="s"/>
        <arg name="properties" direction="out" type="a{sv}"/>
        </method>
        """
        return self._system_bus.call_remote(unit_path, 'GetAll',
                                            signature="s",
                                            args=('org.freedesktop.systemd1.Unit',),
                                            interface="org.freedesktop.DBus.Properties",
                                            destination=BUS_NAME)

    def subscribe(self, callback=None):
        return self._system_bus.call_remote(OBJECT_PATH, 'Subscribe',
                                            interface=MANAGER_INTERFACE,
                                            destination=BUS_NAME)
    