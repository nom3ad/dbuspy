"""
This module implements DBus authentication mechanisms

"""

import binascii
import getpass
import hashlib
import os
import os.path
import time
import logging
import six

from .error import DBusAuthenticationFailed

logger = logging.getLogger(__name__)


AUTH_DELIMITER = b'\r\n'
MAX_AUTH_LENGTH = 16384

class ClientAuthenticator (object):
    """
    Implements the client-side portion of the DBus authentication protocol.

    @ivar preference: List of authentication mechanisms to try in the preferred
        order
    @type preference: List of C{string}
    """

    preference = [b'EXTERNAL', b'DBUS_COOKIE_SHA1', b'ANONYMOUS']

    def authenticate(self, client):
        self._authenticated = False
        self.client = client
        self.unix_fd_support = self._uses_unix_socket_transport(self.client)
        self.guid = None
        self.cookie_dir = None  # used for testing only

        self.authOrder = self.preference[:]
        self.authOrder.reverse()

        self.auth_try_next_method()

    def _uses_unix_socket_transport(self, protocol):
        return True
        return (
            getattr(protocol, 'transport', None) and
            interfaces.IUNIXTransport.providedBy(protocol.transport)
        )

    def await_reply(self):
        while True:
            data = self.client.read()
            if not data:
                raise DBusAuthenticationFailed("ConnectionClosed")
            lines = (self.client._buffer + data).split(AUTH_DELIMITER)
            self.client._buffer  = lines.pop(-1)
            for line in lines:
                # if False: #self.sock.disconnecting:
                #     # this is necessary because the transport may be
                #     # told to lose the connection by a line within a
                #     # larger packet, and it is important to disregard
                #     # all the lines in that packet following the one
                #     # that told it to close.
                #     return
                if len(line) > MAX_AUTH_LENGTH:
                    self.client.loseConnection()
                    raise DBusAuthenticationFailed(
                        "AuthMessageLengthExceeded by %d" % len(line))
                else:
                    try:
                        self.handle_auth_message(line)
                        if self._authenticated:
                            self.guid = self.get_guid()
                            self._authenticated
                            self.client.on_connection_authenticated()
                            # if self._buffer:
                            #     self.on_data_received(b'')
                            return
                    except DBusAuthenticationFailed as e:
                        self.client.loseConnection()
                        raise e


    def handle_auth_message(self, line):
        if b' ' not in line:
            cmd = line
            args = b''
        else:
            cmd, args = line.split(b' ', 1)
        m = getattr(self, '_auth_' + cmd.decode(), None)
        if m:
            m(args)
        else:
            raise DBusAuthenticationFailed(
                'Invalid DBus authentication protocol message: ' +
                line.decode("ascii", "replace")
            )

    def get_guid(self):
        return self.guid

    # -------------------------------------------------

    def send_message(self, msg):
        self.client.write(msg + AUTH_DELIMITER)

    def auth_try_next_method(self):
        """
        Tries the next authentication method or raises a failure if all
        mechanisms have been tried.
        """
        if not self.authOrder:
            raise DBusAuthenticationFailed()

        self.authMech = self.authOrder.pop()
        
        # print "Trying authMech:", self.authMech

        if self.authMech == b'DBUS_COOKIE_SHA1':
            self.send_message(
                b'AUTH ' +
                self.authMech +
                b' ' +
                binascii.hexlify(getpass.getuser().encode('ascii'))
            )
        elif self.authMech == b'ANONYMOUS':
            self.send_message(
                b'AUTH ' +
                self.authMech +
                b' ' +
                binascii.hexlify(b'txdbus')
            )
        else:
            self.send_message(b'AUTH ' + self.authMech)

        self.await_reply()

    def _auth_REJECTED(self, line):
        self.auth_try_next_method()

    def _auth_OK(self, line):
        line = line.strip()

        if not line:
            raise DBusAuthenticationFailed('Missing guid in OK message')

        try:
            self.guid = binascii.unhexlify(line)
        except BaseException:
            raise DBusAuthenticationFailed('Invalid guid in OK message')
        else:
            if self.unix_fd_support:
                self.send_message(b'NEGOTIATE_UNIX_FD')
            else:
                self.send_message(b'BEGIN')
                self._authenticated = True

    def _auth_AGREE_UNIX_FD(self, line):
        if self.unix_fd_support:
            self.send_message(b'BEGIN')
            self._authenticated = True
        else:
            raise DBusAuthenticationFailed(
                'AGREE_UNIX_FD with no NEGOTIATE_UNIX_FD',
            )

    def _auth_DATA(self, line):

        if self.authMech == b'EXTERNAL':
            self.send_message(b'DATA')

        elif self.authMech == b'DBUS_COOKIE_SHA1':
            try:
                data = binascii.unhexlify(line.strip())

                cookie_context, cookie_id, server_challenge = data.split()

                server_cookie = self._auth_get_dbus_cookie(
                    cookie_context,
                    cookie_id,
                )

                client_challenge = binascii.hexlify(
                    hashlib.sha1(os.urandom(8)).digest()
                )

                response = b':'.join([
                    server_challenge,
                    client_challenge,
                    server_cookie
                ])

                response = binascii.hexlify(hashlib.sha1(response).digest())

                reply = client_challenge + b' ' + response

                self.send_message(b'DATA ' + binascii.hexlify(reply))
            except Exception as e:
                logger.error('DBUS Cookie authentication failed: ' + repr(e))
                self.send_message(
                    b'ERROR ' + str(e).encode('unicode-escape'))

    def _auth_ERROR(self, line):
        logger.error(
            'Authentication mechanism failed: ' +
            line.decode("ascii", "replace")
        )
        self.auth_try_next_method()

    # -------------------------------------------------

    def _auth_get_dbus_cookie(self, cookie_context, cookie_id):
        """
        Reads the requested cookie_id from the cookie_context file
        """
        # XXX   Ensure we obtain the correct directory for the
        #       authenticating user and that that user actually
        #       owns the keyrings directory

        if self.cookie_dir is None:
            cookie_dir = os.path.expanduser('~/.dbus-keyrings')
        else:
            cookie_dir = self.cookie_dir

        dstat = os.stat(cookie_dir)

        if dstat.st_mode & 0o066:
            raise Exception(
                'User keyrings directory is writeable by other users. '
                'Aborting authentication',
            )

        import pwd
        if dstat.st_uid != pwd.getpwuid(os.geteuid()).pw_uid:
            raise Exception(
                'Keyrings directory is not owned by the current user. '
                'Aborting authentication!',
            )

        path = os.path.join(cookie_dir, cookie_context.decode('ascii'))
        with open(path, 'rb') as f:
            for line in f:
                try:
                    k_id, k_time, k_cookie_hex = line.split()
                    if k_id == cookie_id:
                        return k_cookie_hex
                except BaseException:
                    pass
