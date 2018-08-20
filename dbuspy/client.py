
import gevent.timeout as gtimeout

from .message import MethodCallMessage
from .protocol import ClientBase
from .objects import  DBusObjectHandler

class Client(ClientBase):
    # def __init__(self):
    busname = None
    obj_handler = None

    def __del__(self):
        self.teardown()
    
    def __repr__(self):
        "<DBusClient(%s)>" % self.busname
    
    def on_connection_authenticated(self):
        # print "on_connection_authenticated!!!!"
        busname = self.call_remote(
            '/Hello',
            'Hello',
            interface='org.freedesktop.DBus',
            destination='org.freedesktop.DBus',
        )
        self.busname=busname
        self.obj_handler = DBusObjectHandler(self)

    def _convert_reply(self, msg):
        if msg is None:
                return None

        # if returnSignature != _NO_CHECK_RETURN:
        #     if not returnSignature:
        #         if msg.signature:
        #             raise error.RemoteError(
        #                 'Unexpected return value signature')
        #     else:
        #         if not msg.signature or msg.signature != returnSignature:
        #             msg = 'Expected "%s". Received "%s"' % (
        #                 str(returnSignature), str(msg.signature))
        #             raise error.RemoteError(
        #                 'Unexpected return value signature: %s' %
        #                 (msg,))

        if msg.body is None or len(msg.body) == 0:
            return None

        # if not (
        #     isinstance(msg.body[0], six.string_types) and
        #     msg.body[0].startswith('<!D')
        # ):
        #     print('RET SIG', msg.signature, 'BODY:', msg.body)
        if len(msg.body) == 1 and not msg.signature[0] == '(':
            return msg.body[0]
        else:
            return msg.body
            
    def call_remote(self, object_path, method,
                   interface=None,
                   destination=None,
                   signature=None,
                   args=None,
                   expectReply=True,
                   autoStart=True,
                   timeout=None,
                #    returnSignature=_NO_CHECK_RETURN
                   ):
    # def getRemoteObject(self, bus_name, object_path):
        
        mcall_msg = MethodCallMessage(
                object_path,
                method,
                interface=interface,
                destination=destination,
                signature=signature,
                body=args,
                expectReply=expectReply,
                autoStart=autoStart,
                oobFDs=self._toBeSentFDs,
            )
        if expectReply:
            with gtimeout.Timeout(timeout):
                self.write(mcall_msg.raw_message)
                return self._convert_reply(self.await_result())
        else:
            self.write(mcall_msg.raw_message)
            return None


    def get_object(self, busname, object_path, interface=None):
        return self.obj_handler.get_remote_object_proxy(busname, object_path, interface)

    # def on_method_call_received(self, mcall):
    #     """
    #     Called when a method call message is received
    #     """
    #     self.objHandler.handleMethodCallMessage(mcall)

   