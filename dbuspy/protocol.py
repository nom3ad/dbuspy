# import gevent.socket as socket
import os.path
import struct
from gevent.event import Event, AsyncResult

from .authentication import ClientAuthenticator
import six

_is_linux = False

if os.path.exists('/proc/version'):
    with open('/proc/version') as f:
        if f.read().startswith('Linux'):
            _is_linux = True
            
from .error import DBusAuthenticationFailed, RemoteError
from . import message


MSG_HDR_LEN = 16  # including 4-byte padding for array of structure

class ClientBase(object):
    _buffer = b''
    _receivedFDs = []
    _toBeSentFDs = []

    _nextMsgLen = 0
    _endian = '<'
    
    _firstByte = True
    _unix_creds = None  # (pid, uid, gid) from UnixSocket credential passing
    authenticator = None  # Class to handle DBus authentication
    MAX_MSG_LENGTH = 2**27

    guid = None  # Filled in with the GUID of the server (for client protocol)
    # or the username of the authenticated client (for server protocol)


    def __init__(self, transport):
        self.rx_ev = Event()
        self.ret_val = None
        self._transport = transport

    def connect(self, target=None):
        # self._transport.connect(target)
        # DBus specification requires that clients send a null byte upon
        # connection to the bus
        self._transport.send(b'\0')
        # do auth
        # print "authenticating"
        ClientAuthenticator().authenticate(self)
        return self
        
    def write(self, data):
        # print msg.rawMessage
        # self._transport.send(b"GET / HTTP/1.0\r\n'")
        # print ">>> %r" % data
        self._transport.send(data)

    def read(self):
        # print msg.rawMessage
        # self._transport.send(b"GET / HTTP/1.0\r\n'")
        data =  self._transport.recv(1024)
        # print "<<< %r" % data
        return data

    def await_result(self):
        try:
            if self.rx_ev.is_set():
                raise RuntimeError("already pending result")

            while not self.rx_ev.is_set():
                data = self.read()
                if not data:
                    raise Exception("ConnectionClosed")
                # print data
                self.on_data_received(data)

            return self.ret_val
        finally:
            self.rx_ev.clear()
                
    def on_data_received(self, data):
        self._buffer = self._buffer + data
        buffer_len = len(self._buffer)

        if self._nextMsgLen == 0 and buffer_len >= 16:
            # There would be multiple clients using different endians.
            # Reset endian every time.
            if self._buffer[:1] != b'l':
                self._endian = '>'
            else:
                self._endian = '<'

            body_len = struct.unpack(
                self._endian + 'I', self._buffer[4:8])[0]
            harr_len = struct.unpack(
                self._endian + 'I', self._buffer[12:16])[0]

            hlen = MSG_HDR_LEN + harr_len

            padlen = hlen % 8 and (8 - hlen % 8) or 0

            self._nextMsgLen = (
                MSG_HDR_LEN +
                harr_len +
                padlen +
                body_len
            )

        if self._nextMsgLen != 0 and buffer_len >= self._nextMsgLen:
            raw_msg = self._buffer[:self._nextMsgLen]
            self._buffer = self._buffer[self._nextMsgLen:]

            self._nextMsgLen = 0

            self.process_raw_dbus_message(raw_msg)

            if self._buffer:
                # Recursively process any other complete messages
                self.on_data_received(b'')
        

    def process_raw_dbus_message(self, rawMsg):
        """
        Called when the raw bytes for a complete DBus message are received

        @param rawMsg: Byte-string containing the complete message
        @type rawMsg: C{str}
        """
        m = message.parse_message(rawMsg, self._receivedFDs)
        mt = m._messageType

        self._receivedFDs = []

        if mt == 1:
            self.on_method_call_received(m)
        elif mt == 2:
            self.on_method_return_received(m)
        elif mt == 3:
            self.on_error_received(m)
        elif mt == 4:
            self.on_signal_received(m)
            

    def teardown(self):
        self._transport.close()

    def on_method_call_received(self, mcall):
        """
        Called when a DBus METHOD_CALL message is received
        """
        raise NotImplementedError


    def on_method_return_received(self, mret):
        """
        Called when a DBus METHOD_RETURN message is received
        """
        self.rx_ev.set()
        self.ret_val = mret

    def on_error_received(self, merr):
        """
        Called when a DBus ERROR message is received
        """
        e = RemoteError(merr.error_name)
        e.message = ''
        e.values = []
        if merr.body:
            if isinstance(merr.body[0], six.string_types):
                e.message = merr.body[0]
            e.values = merr.body
        raise e

    def on_signal_received(self, msig):
        """
        Called when a DBus METHOD_CALL message is received
        """
        # raise NotImplementedError
        print "signal", msig


    def on_connection_authenticated(self):
        print "authenticated!!"