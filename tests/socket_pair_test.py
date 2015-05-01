"""Test for socket_pair.socket_pair()"""

import socket
import unittest

from internet_utils.socket_pair import socket_pair



class SocketPairTestCase(unittest.TestCase):

    def testDefaultSocketPair(self):
        """Basic socket_pair() test with default args
        """
        sock1, sock2 = socket_pair()
        self.addCleanup(sock1.close)
        self.addCleanup(sock2.close)

        # Test sending from sock1 to sock2
        # NOTE: we expect the small message to fit into a single packet

        sock1.sendall("abcd")
        self.assertEqual(sock2.recv(4), "abcd")


        # Test sending from sock2 to sock1
        # NOTE: we expect the small message to fit into a single packet

        sock2.sendall("1234")
        self.assertEqual(sock1.recv(4), "1234")




if __name__ == '__main__':
    unittest.main()
