"""
Module to represent DBus Messages

@author: Tom Cocagne
"""
from . import error, marshal


_headerFormat = 'yyyyuua(yv)'


class DBusMessage (object):
    """
    Abstract base class for DBus messages

    @ivar _messageType: C{int} DBus message type
    @ivar expectReply: True if a method return message is expected
    @ivar autoStart: True if a service should be auto started by this message
    @ivar signature: C{str} DBus signature describing the body content
    @ivar endian: C{int} containing endian code: Little endian = ord('l'). Big
                  endian is ord('B'). Defaults to little-endian
    @ivar bodyLength: Length of the body in bytes
    @ivar serial: C{int} message serial number
    @ivar rawMessage: Raw binary message data
    @ivar rawHeader: Raw binary message header
    @ivar rawBody: Raw binary message body
    @ivar interface: C{str} DBus interface name
    @ivar path: C{str} DBus object path
    @ivar sender: C{str} DBus bus name for sending connection
    @ivar destination: C{str} DBus bus name for destination connection

    """
    _max_msg_len = 2**27
    _next_serial = 1
    _protocol_version = 1

    # Overriden by subclasses
    _message_type = 0
    _header_attrs = None  # [(attr_name, code, is_required), ...]

    # Set prior to marshal or during/after unmarshalling
    expect_reply = True
    auto_start = True
    signature = None
    body = None

    # Set during marshalling/unmarshalling
    endian = ord('l')
    body_length = 0
    serial = None
    headers = None
    raw_message = None

    # Required/Optional
    interface = None
    path = None

    # optional
    sender = None
    destination = None


#    def printSelf(self):
#        mtype = { 1 : 'MethodCall',
#                  2 : 'MethodReturn',
#                  3 : 'Error',
#                  4 : 'Signal' }
#        print mtype[self._messageType]
#        keys = self.__dict__.keys()
#        keys.sort()
#        for a in keys:
#            if not a.startswith('raw'):
#                print '    %s = %s' % (a.ljust(15), str(getattr(self,a)))

    def _marshal(self, newSerial=True, oobFDs=None):
        """
        Encodes the message into binary format. The resulting binary message is
        stored in C{self.rawMessage}
        """
        flags = 0

        if not self.expect_reply:
            flags |= 0x1

        if not self.auto_start:
            flags |= 0x2

        # may be overriden below, depending on oobFDs
        _headerAttrs = self._header_attrs

        # marshal body before headers to know if the 'unix_fd' header is needed
        if self.signature:
            bin_body = b''.join(
                marshal.marshal(
                    self.signature,
                    self.body,
                    oobFDs=oobFDs
                )[1]
            )
            if oobFDs:
                # copy class based _headerAttrs to add a unix_fds header this
                # time
                _headerAttrs = list(self._header_attrs)
                _headerAttrs.append(('unix_fds', 9, False))
                self.unix_fds = len(oobFDs)
        else:
            bin_body = b''

        self.headers = []

        for attr_name, code, is_required in _headerAttrs:
            hval = getattr(self, attr_name, None)

            if hval is not None:
                if attr_name == 'path':
                    hval = marshal.ObjectPath(hval)
                elif attr_name == 'signature':
                    hval = marshal.Signature(hval)
                elif attr_name == 'unix_fds':
                    hval = marshal.UInt32(hval)

                self.headers.append([code, hval])

        self.body_length = len(bin_body)

        if newSerial:
            self.serial = DBusMessage._next_serial

            DBusMessage._next_serial += 1

        binHeader = b''.join(marshal.marshal(
            _headerFormat,
            [
                self.endian,
                self._message_type,
                flags,
                self._protocol_version,
                self.body_length,
                self.serial,
                self.headers
            ],
            lendian=self.endian == ord('l')
        )[1])

        header_padding = marshal.pad['header'](len(binHeader))

        self.rawHeader = binHeader
        self.raw_padding = header_padding
        self.raw_body = bin_body

        self.raw_message = b''.join([binHeader, header_padding, bin_body])

        if len(self.raw_message) > self._max_msg_len:
            raise error.MarshallingError(
                'Marshalled message exceeds maximum message size of %d' %
                (self._max_msg_len,),
            )


class MethodCallMessage (DBusMessage):
    """
    A DBus Method Call Message
    """
    _message_type = 1
    _header_attrs = [
        ('path', 1, True),
        ('interface', 2, False),
        ('member', 3, True),
        ('destination', 6, False),
        ('sender', 7, False),
        ('signature', 8, False)
    ]

    def __init__(self, path, member, interface=None, destination=None,
                 signature=None, body=None,
                 expectReply=True, autoStart=True, oobFDs=None):
        """
        @param path: C{str} DBus object path
        @param member: C{str} Member name
        @param interface: C{str} DBus interface name or None
        @param destination: C{str} DBus bus name for message destination or
                            None
        @param signature: C{str} DBus signature string for encoding
                          C{self.body}
        @param body: C{list} of python objects to encode. Objects must match
                     the C{self.signature}
        @param expectReply: True if a Method Return message should be sent
                            in reply to this message
        @param autoStart: True if the Bus should auto-start a service to handle
                          this message if the service is not already running.
        """

        marshal.validate_member_name(member)

        if interface:
            marshal.validate_interface_name(interface)

        if destination:
            marshal.validate_bus_name(destination)

        if path == '/org/freedesktop/DBus/Local':
            raise error.MarshallingError(
                '/org/freedesktop/DBus/Local is a reserved path')

        self.path = path
        self.member = member
        self.interface = interface
        self.destination = destination
        self.signature = signature
        self.body = body
        self.expectReply = expectReply
        self.autoStart = autoStart

        self._marshal(oobFDs=oobFDs)


class MethodReturnMessage (DBusMessage):
    """
    A DBus Method Return Message
    """
    _messageType = 2
    _headerAttrs = [
        ('reply_serial', 5, True),
        ('destination', 6, False),
        ('sender', 7, False),
        ('signature', 8, False),
    ]

    def __init__(self, reply_serial, body=None, destination=None,
                 signature=None):
        """
        @param reply_serial: C{int} serial number this message is a reply to
        @param destination: C{str} DBus bus name for message destination or
                            None
        @param signature: C{str} DBus signature string for encoding
                          C{self.body}
        @param body: C{list} of python objects to encode. Objects must match
                     the C{self.signature}
        """
        if destination:
            marshal.validate_bus_name(destination)

        self.reply_serial = marshal.UInt32(reply_serial)
        self.destination = destination
        self.signature = signature
        self.body = body

        self._marshal()


class ErrorMessage (DBusMessage):
    """
    A DBus Error Message
    """
    _messageType = 3
    _headerAttrs = [
        ('error_name', 4, True),
        ('reply_serial', 5, True),
        ('destination', 6, False),
        ('sender', 7, False),
        ('signature', 8, False),
    ]

    def __init__(self, error_name, reply_serial, destination=None,
                 signature=None, body=None, sender=None):
        """
        @param error_name: C{str} DBus error name
        @param reply_serial: C{int} serial number this message is a reply to
        @param destination: C{str} DBus bus name for message destination or
                            None
        @param signature: C{str} DBus signature string for encoding
                          C{self.body}
        @param body: C{list} of python objects to encode. Objects must match
                     the C{self.signature}
        @param sender: C{str} name of the originating Bus connection
        """
        if destination:
            marshal.validate_bus_name(destination)

        marshal.validate_interface_name(error_name)

        self.error_name = error_name
        self.reply_serial = marshal.UInt32(reply_serial)
        self.destination = destination
        self.signature = signature
        self.body = body
        self.sender = sender

        self._marshal()


class SignalMessage (DBusMessage):
    """
    A DBus Signal Message
    """
    _messageType = 4
    _headerAttrs = [
        ('path', 1, True),
        ('interface', 2, True),
        ('member', 3, True),
        ('destination', 6, False),
        ('sender', 7, False),
        ('signature', 8, False),
    ]

    def __init__(self, path, member, interface, destination=None,
                 signature=None, body=None):
        """
        @param path: C{str} DBus object path of the object sending the signal
        @param member: C{str} Member name
        @param interface: C{str} DBus interface name or None
        @param destination: C{str} DBus bus name for message destination or
                            None
        @param signature: C{str} DBus signature string for encoding
                          C{self.body}
        @param body: C{list} of python objects to encode. Objects must match
                     the C{self.signature}
        """
        marshal.validate_member_name(member)
        marshal.validate_interface_name(interface)

        if destination:
            marshal.validate_bus_name(destination)

        self.path = path
        self.member = member
        self.interface = interface
        self.destination = destination
        self.signature = signature
        self.body = body

        self._marshal()

    def __repr__(self):
        return "<Signal: path=%s, member=%s, interface=%s, dest=%s, body=%s" % (
            self.path,self.member,self.interface,self.destination,self.body
        )

_mtype = {
    1: MethodCallMessage,
    2: MethodReturnMessage,
    3: ErrorMessage,
    4: SignalMessage,
}

_hcode = {
    1: 'path',
    2: 'interface',
    3: 'member',
    4: 'error_name',
    5: 'reply_serial',
    6: 'destination',
    7: 'sender',
    8: 'signature',
    9: 'unix_fds',
}


def parse_message(rawMessage, oobFDs):
    """
    Parses the raw binary message and returns a L{DBusMessage} subclass.
    Unmarshalling DBUS 'h' (UNIX_FD) gets the FDs from the oobFDs list.

    @type rawMessage: C{str}
    @param rawMessage: Raw binary message to parse

    @rtype: L{DBusMessage} subclass
    @returns: The L{DBusMessage} subclass corresponding to the contained
              message
    """

    lendian = rawMessage[0] == b'l'[0]

    nheader, hval = marshal.unmarshal(
        _headerFormat,
        rawMessage,
        0,
        lendian,
        oobFDs,
    )

    messageType = hval[1]

    if messageType not in _mtype:
        raise error.MarshallingError(
            'Unknown Message Type: ' + str(messageType)
        )

    m = object.__new__(_mtype[messageType])

    m.rawHeader = rawMessage[:nheader]

    npad = nheader % 8 and (8 - nheader % 8) or 0

    m.rawPadding = rawMessage[nheader: nheader + npad]

    m.rawBody = rawMessage[nheader + npad:]

    m.serial = hval[5]

    for code, v in hval[6]:
        try:
            setattr(m, _hcode[code], v)
        except KeyError:
            pass

    if m.signature:
        nbytes, m.body = marshal.unmarshal(
            m.signature,
            m.rawBody,
            lendian=lendian,
            oobFDs=oobFDs,
        )

    return m
