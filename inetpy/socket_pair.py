"""socket.socketpair substitute with support for Windows"""

import socket
import threading


def socket_pair(family=None, sock_type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_IP):
    """ socket.socketpair abstraction with support for Windows

    :param family: address family; e.g., socket.AF_UNIX, socket.AF_INET, etc.;
      defaults to socket.AF_UNIX if available, with fallback to socket.AF_INET.
    :param sock_type: socket type; defaults to socket.SOCK_STREAM
    :param proto: protocol; defaults to socket.IPPROTO_IP

    :returns: connected socket pair (sock1, sock2)

    :example:
        sock1, sock2 = socket_pair()

        # NOTE: we expect the small message to fit into a single packet

        sock1.sendall("abcd")
        assert sock2.recv(4) == "abcd"

        sock2.sendall("1234")
        assert sock1.recv(4) == "1234"
    """
    if family is None:
        try:
            family = socket.AF_UNIX
        except NameError:
            family = socket.AF_INET

    try:
        socket1, socket2 = socket.socketpair(family, sock_type, proto)
    except NameError:
        # Probably running on Windows where socket.socketpair isn't supported

        # Work around lack of socket.socketpair()

        socket1 = socket2 = None

        listener = socket(family, sock_type, proto)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        listener.bind(("localhost", 0))
        listener.listen(1)
        listener_port = listener.getsockname()[1]

        socket1 = socket(family, sock_type, proto)

        # Use thread to connect in background, while foreground issues the
        # blocking accept()
        conn_thread = threading.Thread(
            target=socket1.connect,
            args=(('localhost', listener_port),))
        conn_thread.setDaemon(1)
        conn_thread.start()

        try:
            socket2 = listener.accept()[0]
        finally:
            listener.close()

            # Join/reap background thread
            conn_thread.join(timeout=10)

    return (socket1, socket2)