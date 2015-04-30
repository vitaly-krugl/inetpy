Forward/Echo Server in Python for testing

## TCP/IP Connection forwarding example

1. Forward local connection to default rabbitmq addr
2. Connect to rabbit via forwarder
3. Then disconnect forwarder
4. Then attempt another rabbitmq operation to see what happens in the client

```
import sys

import pika

from forward_server import ForwardServer

with ForwardServer(("localhost", 5672)) as fwd:
    params = pika.ConnectionParameters(host="localhost",
                                       port=fwd.listening_port)
    conn = pika.BlockingConnection(params)
    print >> sys.stderr, "Connected!"

# Once outside the context, the forwarder is disconnected

# Let's see what happens in pika with a disconnected server
channel = conn.channel()
```
