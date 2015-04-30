"""TCP/IP forwarding/echo service for testing."""

import errno
import multiprocessing
import socket
import SocketServer
import sys
import threading



class ForwardServer(object):
    """ Implement a TCP/IP forwarding/echo service for testing. Listens for
    an incoming TCP/IP connection, accepts it, then connects to the given
    remote address and forwards data back and forth between the two
    endpoints.

    This is similar to the subset of `netcat` functionality, but without
    dependency on any specific flavor of netcat
    """
    def __init__(self, remote_addr):
        """
        :param tuple remote_addr: pair (host-or-ip-addr, port-number). Pass
          None to have ForwardServer behave as echo server
        """
        self._remote_addr = remote_addr
        self._listening_port = None

        self._subproc = None


    def start(self):
        """ Starts the server

        :returns: self
        """
        server = ThreadedTCPServer(self._remote_addr)
        self._listening_port = server.server_address[1]

        self._subproc = multiprocessing.Process(target=_run_server,
                                                args=(server,),
                                                kwargs={})
        self._subproc.daemon = True
        self._subproc.start()

        return self


    def __enter__(self):
        """ Context manager entry. Starts the forwarding server

        Once inside the context, our `listening_port` attribute getter
        becomes defined

        :returns: self
        """
        return self.start()


    def __exit__(self, *args):
        """ Context manager exit; stops the forwarding server
        """
        self._subproc.terminate()
        self._subproc.join(timeout=10)
        self._subproc = None


    @property
    def listening_port(self):
        """ Property: Get listening port
        """
        assert self._listening_port is not None, "Not in context"

        return self._listening_port



def _run_server(server):
    """ Run the server

    :param ThreadedTCPServer server:
    """
    server.serve_forever()



class ThreadedTCPServer(SocketServer.ThreadingMixIn,
                        SocketServer.TCPServer,
                        object):
    allow_reuse_address = True


    def __init__(self, remote_addr):
        self.remote_addr = remote_addr

        super(ThreadedTCPServer, self).__init__(("127.0.0.1", 0),
                                                TCPHandler)


class TCPHandler(SocketServer.StreamRequestHandler):

    _SOCK_RX_BUF_SIZE = 16 * 1024

    def handle(self):
        def forward(src_sock, dest_sock):
            try:
                rx_buf = bytearray(b" " * self._SOCK_RX_BUF_SIZE)

                while True:
                    try:
                        nbytes = src_sock.recv_into(rx_buf)
                    except socket.error as e:
                        if e.errno == errno.EINTR:
                            continue
                        else:
                            raise

                    if not nbytes:
                        # Source input EOF
                        break

                    try:
                        dest_sock.sendall(buffer(rx_buf, 0, nbytes))
                    except socket.error as e:
                        if e.errno == errno.EPIPE:
                            # Dest peer closed its end of the connection
                            break
                        else:
                            raise
            finally:
                try:
                    # Let source peer know we're done receiving
                    _safe_shutdown_socket(src_sock, socket.SHUT_RD)
                finally:
                    # Let destination peer know we're done sending
                    _safe_shutdown_socket(dest_sock, socket.SHUT_WR)

        local_sock = self.connection

        if self.server.remote_addr is not None:
            remote_dest_sock = remote_src_sock = socket.socket()
            remote_dest_sock.connect(self.server.remote_addr)
        else:
            # Echo mode
            remote_dest_sock, remote_src_sock = socket_pair()

        try:
            local_forwarder = threading.Thread(
                target=forward,
                args=(local_sock, remote_dest_sock,))
            local_forwarder.setDaemon(True)
            local_forwarder.start()

            try:
                forward(remote_src_sock, local_sock)
            finally:
                # Wait for local forwarder thread to exit
                local_forwarder.join()
        finally:
            try:
                try:
                    _safe_shutdown_socket(remote_dest_sock,
                                          socket.SHUT_RDWR)
                finally:
                    if remote_src_sock is not remote_dest_sock:
                        _safe_shutdown_socket(remote_src_sock,
                                              socket.SHUT_RDWR)
            finally:
                remote_dest_sock.close()
                if remote_src_sock is not remote_dest_sock:
                    remote_src_sock.close()



def socket_pair(family=None, sock_type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_IP):
    """ socket.socketpair abstraction with support for Windows
    """
    if family is None:
        try:
            family = socket.AF_UNIX
        except NameError:
            family = socket.AF_INET

    try:
        sock1, sock2 = socket.socketpair(family, sock_type, proto)
    except NameError:
        # Work around lack of socket.socketpair()

        lsock = socket(family, sock_type, proto)
        lsock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)

        lsock.bind(("localhost", 0))
        ephport = lsock.getsockname()[1]
        lsock.listen(1)

        sock1 = socket(family, sock_type, proto)

        # Use thread to connect in background, while foreground issues the
        # blocking accept() call
        conn_thread = threading.Thread(
            target=sock1.connect,
            args=(('localhost', lsock.getsockname()[1]),))
        conn_thread.setDaemon(1)
        conn_thread.start()

        try:
            sock2 = lsock.accept()[0]
        finally:
            lsock.close()
            conn_thread.join(timeout=10)

    return (sock1, sock2)



def echo(port=0):
    """ This function implements a simple echo server for testing the
    Forwarder class.

    :param int port: port number on which to listen

    We run this function and it prints out the listening socket binding.
    Then, we run Forwarder and point it at this echo "server".
    Then, we run telnet and point it at forwarder and see if whatever we
    type gets echoed back to us.

    This function exits when the remote end connects, then closes connection
    """
    lsock = socket.socket()
    lsock.bind(("", port))
    lsock.listen(1)
    print >> sys.stderr, "Listening on sockname:", lsock.getsockname()

    sock, remote_addr = lsock.accept()
    try:
        print >> sys.stderr, "Connection from peer:", remote_addr
        while True:
            try:
                data = sock.recv(4 * 1024)
            except socket.error as e:
                if e.errno == errno.EINTR:
                    continue
                else:
                    raise

            if not data:
                break

            sock.sendall(data)
    finally:
        try:
            _safe_shutdown_socket(sock, socket.SHUT_RDWR)
        finally:
            sock.close()



def _safe_shutdown_socket(sock, how):
    """ Shutdown a socket, suppressing ENOTCONN
    """
    try:
        sock.shutdown(how)
    except socket.error as e:
        if e.errno != errno.ENOTCONN:
            raise
