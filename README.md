Internet utilities in the Python programming language
=====================================================


## TCP/IP Connection forwarding example
```
import sys

import pika

# Forward local connection to default rabbitmq addr
from inetpy.forward_server import ForwardServer

with ForwardServer(("localhost", 5672)) as fwd:
    # Connect to rabbit via forwarder
    params = pika.ConnectionParameters(host=fwd.server_address[0],
                                       port=fwd.server_address[1])
    conn = pika.BlockingConnection(params)
    print >> sys.stderr, "Connected!"

# Once outside the context, the forwarder is disconnected

# Let's see what happens in pika with a disconnected server
channel = conn.channel()
```

## Echo server example
```
import socket
import threading
import time

from inetpy.forward_server import ForwardServer

def produce(sock):
    sock.sendall("12345")
    sock.shutdown(socket.SHUT_WR)

with ForwardServer(None) as fwd:
    sock = socket.socket()
    sock.connect(fwd.server_address)

    worker = threading.Thread(target=produce,
                              args=[sock])
    worker.start()

    data = sock.makefile().read()
    assert data == "12345", data

worker.join()
```

## Socket Pair example

socket.socketpair abstraction with support for Windows

```
from inetpy.socket_pair import socket_pair

sock1, sock2 = socket_pair()

# NOTE: we expect the small message to fit into a single packet

sock1.sendall("abcd")
assert sock2.recv(4) == "abcd"

sock2.sendall("1234")
assert sock1.recv(4) == "1234"
