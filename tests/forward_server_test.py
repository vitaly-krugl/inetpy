"""Test for forward_server.ForwardServer class"""

import multiprocessing
import socket
import threading
import unittest

from internet_utils import forward_server



class ForwardServerTestCase(unittest.TestCase):

    def testForwardingContextManager(self):
        """Basic forwarding test that context manager makes socket information
        available
        """
        with forward_server.ForwardServer(("localhost", 9999)) as fwd:
            self.assertEqual(fwd.server_address_family, socket.AF_INET)
            self.assertIsInstance(fwd.server_address, tuple)

        self.assertIsNone(fwd._subproc)


    def testEchoContextManager(self):
        """Basic echo test that context manager makes socket information
        available
        """
        with forward_server.ForwardServer(None) as fwd:
            self.assertEqual(fwd.server_address_family, socket.AF_INET)
            self.assertIsInstance(fwd.server_address, tuple)

        self.assertIsNone(fwd._subproc)


    def testBasicForwarding(self):
        """Basic forwarding test"""

        remote_sock = socket.socket()
        remote_sock.bind(("localhost", 0))
        remote_sock.listen(1)


        def run_remote(listener):
            sock = listener.accept()[0]
            data = sock.recv(4)
            sock.sendall(data + "4")

        remote_server_process = multiprocessing.Process(target=run_remote,
                                                        args=(remote_sock,))
        remote_server_process.daemon = True
        remote_server_process.start()
        self.addCleanup(
            lambda: (remote_server_process.terminate() or
                     remote_server_process.join()))

        with forward_server.ForwardServer(remote_sock.getsockname()) as fwd:
            sock = socket.socket()
            self.addCleanup(sock.close)
            sock.connect(fwd.server_address)

            # NOTE: we expect the small message to fit into a single packet
            sock.sendall("abcd")
            data = sock.recv(10)
            self.assertEqual(data, "abcd4")


    def testBasicEcho(self):
        """Basic echo test"""
        with forward_server.ForwardServer(None) as fwd:
            sock = socket.socket()
            sock.connect(fwd.server_address)

            # NOTE: we expect the small message to fit into a single packet
            sock.sendall("abcd")
            self.assertEqual(sock.recv(4), "abcd")



if __name__ == '__main__':
    unittest.main()
