from gevent_dbus import session_bus, system_bus
import logging

logging.basicConfig(level=logging.DEBUG)

# c = session_bus()
# c.connect()
# print c.call_remote( '/org/freedesktop/Notifications', 'GetMachineId',
#                               interface   = 'org.freedesktop.DBus.Peer',
#                               destination = 'org.freedesktop.Notifications' )


# print c.call_remote( '/org/freedesktop/Notifications', 'Notify',
#                                     signature='susssasa{sv}i',
#                                     args = (
#                                         'Example Application',
#                                         0,
#                                         '',
#                                         'Tx DBus Example',
#                                         'Hello World!',
#                                         [], dict(),
#                                         3000,
#                                     ),
#                               interface   = 'org.freedesktop.Notifications',
#                               destination = 'org.freedesktop.Notifications' )



c = system_bus().connect()
print c.call_remote( '/org/freedesktop/systemd1/unit/snapd_2eservice', 'GetProcesses',
                              interface   = 'org.freedesktop.systemd1.Service',
                              destination = 'org.freedesktop.systemd1' )

                              