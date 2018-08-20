


class DBusObjectHandler(object):

    def __init__(self, client):
        self.client = client


    def get_remote_object_proxy(self, busname, object_path, interfaces):
        return RemoteObjectProxy(self, busname, object_path)




class RemoteObjectProxy(object):
    pass