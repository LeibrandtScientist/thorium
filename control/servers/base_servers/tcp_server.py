import socket

from labrad.server import LabradServer, inlineCallbacks
from twisted.internet.defer import returnValue


class TCPServer(LabradServer):
    """Base server for controlling a device with network communication.

    Servers that communicate with devices with TCP should inherit from this class.
    The device needs to be connected to the same network as the computer that runs the server.

    Attributes `regKey` and `port` must be defined in inherited classes.

    Attribute `socket` is the socket instance that communicates with the device.

    Attributes:
        regKey: str, it points to the device IP address in LabRAD registry - Ports.
        port: int, device TCP port number.
        timeout: float, communication timeout in seconds. See `socket.socket.settimeout()`.
            Default 1.
    """

    regKey = None
    port = None
    timeout = 1.0

    @inlineCallbacks
    def initServer(self):
        address = yield self.get_address(self.regKey)
        self.socket = socket.socket()
        self.socket.connect((address, self.port))
        self.socket.settimeout(self.timeout)

    @inlineCallbacks
    def get_address(self, key):
        """Finds the device IP address given the key.

        It looks up the key in LabRAD registry - Ports.
        The value of the key should be a str of the IP address.

        Args:
            key: str, key in the "Ports" directory that stores the device address.

        Returns:
            str, IP address.
        """
        reg = self.client.registry
        # Remembers the previous directory in the registry.
        current_directory = yield reg.cd()
        # There must be a "Ports" directory at the root of the registry folder
        try:
            yield reg.cd(["", "Ports"])
        except Exception:
            raise Exception("Cannot find 'Ports' directory in registry.")
        keys = yield reg.dir()
        if key in keys[1]:
            address = yield reg.get(key)
        else:
            reg.cd(current_directory)
            raise Exception(f"Cannot find key '{key}' in 'Ports' directory.")
        # Goes back to the previous directory in the registry.
        reg.cd(current_directory)
        returnValue(address)

    def send(self, str_to_send):
        """Sends a string to the device.

        Args:
            str_to_send: str, string to send to the device.
        """
        self.socket.sendall(str_to_send.encode())

    def readline(self, termination="\n"):
        """Tries to read a line.

        It is not guarenteed to read a line if there are more content in the read buffer after
        the termination character(s).

        Args:
            termination: str, termination character(s) for a line.

        Returns:
            str, data read from the socket.
        """
        str_to_return = ""
        READ_SIZE = 4096
        while termination not in str_to_return:
            str_to_return += self.socket.recv(READ_SIZE).decode()
        return str_to_return

    def readall(self):
        """Reads all from the socket read buffer.

        This function is useful to clear the read buffer when the server starts.
        It stops after the first timeout.

        Returns:
            str, data read from the socket.
        """
        READ_SIZE = 4096  # a typical socket read size.
        str_to_return = ""
        try:
            str_to_return += self.socket.recv(READ_SIZE).decode()
        except (socket.timeout, TimeoutError):
            # socket.timeout is changed to TimeoutError in Python 3.10.
            return str_to_return
