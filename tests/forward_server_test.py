"""Test for forward_server.ForwardServer class

TODO multi-connection tests
"""

# Supress pylint messages concerning missing class docstring
# pylint: disable=C0111

import errno
import multiprocessing
import socket
import unittest

from inetpy import forward_server



class ForwardServerTestCase(unittest.TestCase):

    def test_forwarding_context_manager(self):
        """Basic forwarding test that context manager makes socket information
        available
        """
        with forward_server.ForwardServer(("localhost", 9999)) as fwd:
            self.assertTrue(fwd.running)
            self.assertEqual(fwd.server_address_family, socket.AF_INET)
            self.assertIsInstance(fwd.server_address, tuple)
            self.assertEqual(len(fwd.server_address), 2)

        self.assertFalse(fwd.running)


    def test_echo_context_manager(self):
        """Basic echo test that context manager makes socket information
        available
        """
        with forward_server.ForwardServer(None) as fwd:
            self.assertTrue(fwd.running)
            self.assertEqual(fwd.server_address_family, socket.AF_INET)
            self.assertIsInstance(fwd.server_address, tuple)
            self.assertEqual(len(fwd.server_address), 2)

        self.assertFalse(fwd.running)


    def test_basic_forwarding(self):
        """Basic forwarding test"""

        # Set up listening socket that represents the remote server
        remote_listener_sock = socket.socket()
        remote_listener_sock.bind(("localhost", 0))
        remote_listener_sock.listen(1)

        # NOTE: we expect the small message to fit into a single packet

        # Start the remote server
        def run_remote(listener):
            sock = listener.accept()[0]

            data = sock.recv(10)
            sock.sendall(data + str(len(data)))

            sock.shutdown(socket.SHUT_WR)

            assert sock.recv(10) == "12345"

            # We now expect client to SHUT_WR
            assert sock.recv(10) == ""



        remote_server_process = multiprocessing.Process(
            target=run_remote,
            args=(remote_listener_sock,))
        remote_server_process.daemon = True
        remote_server_process.start()
        self.addCleanup(
            lambda: ((remote_server_process.terminate() or
                      remote_server_process.join())
                     if remote_server_process.exitcode is None else None))

        with forward_server.ForwardServer(
                remote_listener_sock.getsockname()) as fwd:
            self.assertTrue(fwd.running)
            # Connect to forwarding server
            sock = socket.socket()
            self.addCleanup(sock.close)
            sock.connect(fwd.server_address)

            # Test send/receive via forwarding server
            sock.sendall("abcd")
            self.assertEqual(sock.recv(10), "abcd4")

            # After this, run_remote performs SHUT_WR on its end
            self.assertEqual(sock.recv(10), "")

            # Send one more message to remote server and verify response
            sock.sendall("12345")

            # Shut down the local socket's WR stream and check remote server's
            # termination code
            sock.shutdown(socket.SHUT_WR)
            remote_server_process.join(timeout=10)
            self.assertFalse(remote_server_process.is_alive())
            self.assertEqual(remote_server_process.exitcode, 0)

        self.assertFalse(fwd.running)


    def test_large_forwarding(self):
        """Forward large data block"""
        # Set up listening socket that represents the remote server
        remote_listener_sock = socket.socket()
        remote_listener_sock.bind(("localhost", 0))
        remote_listener_sock.listen(1)

        tx_data = "abc" * 1000000

        # Start the remote server
        def run_remote(listener):
            sock = listener.accept()[0]
            sock.settimeout(10)

            data = sock.makefile().read()

            sock.sendall(data + str(len(data)))
            sock.shutdown(socket.SHUT_WR)



        remote_server_process = multiprocessing.Process(
            target=run_remote,
            args=(remote_listener_sock,))
        remote_server_process.daemon = True
        remote_server_process.start()
        self.addCleanup(
            lambda: ((remote_server_process.terminate() or
                      remote_server_process.join())
                     if remote_server_process.exitcode is None else None))

        with forward_server.ForwardServer(
                remote_listener_sock.getsockname()) as fwd:
            self.assertTrue(fwd.running)

            # Connect to forwarding server
            sock = socket.socket()
            self.addCleanup(sock.close)

            sock.connect(fwd.server_address)
            sock.settimeout(10)

            # Send the large data block to remote server
            sock.sendall(tx_data)
            sock.shutdown(socket.SHUT_WR)


            # Receive a copy of the large data block from the server
            rx_data = sock.makefile().read()
            self.assertEqual(len(rx_data), len(tx_data) + len(str(len(tx_data))))
            self.assertEqual(rx_data[:len(tx_data)], tx_data)
            self.assertEqual(rx_data[len(tx_data):], str(len(tx_data)))

            # Wait for remote server process to shut down and check exit code
            remote_server_process.join(timeout=10)
            self.assertFalse(remote_server_process.is_alive())
            self.assertEqual(remote_server_process.exitcode, 0)

        self.assertFalse(fwd.running)


    def test_echo_so_linger_zero_sec_resets_connection_on_termination(self):  # pylint: disable=C0103
        """Test echo with SO_LINGER set to linger for 0 seconds resets
        connection upon forwarder termination
        """

        with forward_server.ForwardServer(remote_addr=None,
                                          local_linger_args=(1, 0)) as fwd:
            self.assertTrue(fwd.running)

            sock = socket.socket()
            sock.connect(fwd.server_address)

            # Test send/receive via echo server
            # NOTE: we expect the small message to fit into a single packet
            sock.sendall("abcd")
            self.assertEqual(sock.recv(10), "abcd")

        with self.assertRaises(socket.error) as exc_ctx:
            sock.send("efg")

        self.assertEqual(exc_ctx.exception.errno, errno.EPIPE)


    def test_basic_echo(self):
        """Basic echo test"""
        with forward_server.ForwardServer(remote_addr=None) as fwd:
            self.assertTrue(fwd.running)

            sock = socket.socket()
            sock.connect(fwd.server_address)

            # Test send/receive via echo server
            # NOTE: we expect the small message to fit into a single packet
            sock.sendall("abcd")
            self.assertEqual(sock.recv(10), "abcd")

            # Expect incoming to shutdown after we SHUT_WR
            sock.shutdown(socket.SHUT_WR)
            self.assertEqual(sock.recv(10), "")


    def test_large_echo(self):
        """Echo large data block"""
        with forward_server.ForwardServer(remote_addr=None) as fwd:
            self.assertTrue(fwd.running)

            sock = socket.socket()
            sock.connect(fwd.server_address)

            sock.settimeout(10)

            tx_data = "abc" * 1000000

            # Start the producer
            def produce_and_shut(sock, data):
                sock.sendall(data)
                sock.shutdown(socket.SHUT_WR)

            producer_process = multiprocessing.Process(
                target=produce_and_shut,
                args=(sock, tx_data,))

            producer_process.daemon = True
            producer_process.start()
            self.addCleanup(
                lambda: ((producer_process.terminate() or
                          producer_process.join())
                         if producer_process.exitcode is None else None))

            # Consume the data
            rx_data = sock.makefile().read()
            self.assertEqual(len(rx_data), len(tx_data))
            self.assertEqual(rx_data, tx_data)

            # Make sure the producer
            producer_process.join(timeout=10)
            self.assertFalse(producer_process.is_alive())
            self.assertEqual(producer_process.exitcode, 0)

if __name__ == '__main__':
    unittest.main()
