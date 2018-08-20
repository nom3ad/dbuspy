from gevent.monkey import patch_all;patch_all()
from systemd_dbus import SystemdManager

m = SystemdManager()

# print m.get_unit_props('snapd.service')
# print m.subscribe('snapd.service')

from gevent import sleep,spawn


print m.subscribe('snapd.service')

def await_client():
    for i in range(1,100001):
        print "loop start", i
        print m._system_bus.await_result()
        # m._get_unit('snapd.service')
        print "loop next",i
        sleep(1)
        

spawn(await_client)

sleep(100)