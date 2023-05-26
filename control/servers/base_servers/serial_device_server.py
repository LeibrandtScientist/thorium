from labrad.server import LabradServer, setting
from labrad.types import Error
from twisted.internet.defer import inlineCallbacks, returnValue

__all__ = [
    "setting",
    "inlineCallbacks",
    "returnValue",
    "SerialDeviceError",
    "SerialConnectionError",
    "PortRegError",
    "SerialDeviceServer",
]


class SerialDeviceError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class SerialConnectionError(Exception):
    errorDict = {
        0: "Could not find serial server in list",
        1: "Serial server not connected",
        2: "Attempting to use serial connection when not connected",
    }

    def __init__(self, code):
        self.code = code

    def __str__(self):
        return self.errorDict[self.code]


class PortRegError(SerialConnectionError):
    errorDict = {
        0: "Registry not properly configured",
        1: "Key not found in registry",
        2: "No keys in registry",
    }


NAME = "SerialDevice"


class SerialDeviceServer(LabradServer):
    """Base class for serial device servers.

    Contains a number of methods useful for using labrad's serial server.

    Functionality comes from ser attribute, which represents a connection
    that performs reading and writing to a serial port.

    Subclasses should assign some or all of the following attributes.

    Attributes:
        name: Something short but descriptive.
        port: Name of serial port (Better to look this up in the registry
            using regKey and getPortFromReg()).
        regKey: Short string used to find port name in registry.
        serNode: Name of node running desired serial server. Used to identify correct serial server.
        timeOut: Time to wait for response before giving up.
    """

    name = NAME
    port = None
    regKey = None
    serNode = None
    timeout = None

    ser = None

    class SerialConnection:
        """Wrapper for our server's client connection to the serial server.

        @raise labrad.types.Error: Error in opening serial connection.
        """

        def __init__(self, ser, port, **kwargs):
            timeout = kwargs.get("timeout")
            baudrate = kwargs.get("baudrate")
            ser.open(port)
            if timeout is not None:
                ser.timeout(timeout)
            if baudrate is not None:
                ser.baudrate(baudrate)
            self.write = lambda s: ser.write(s)
            self.write_line = lambda s: ser.write_line(s)
            self.read = lambda x=0: ser.read(x)
            self.read_line = lambda: ser.read_line()
            self.read_bytes = lambda x=0: ser.read_bytes(x)
            self.close = lambda: ser.close()
            self.flushinput = lambda: ser.flushinput()
            self.flushoutput = lambda: ser.flushoutput()
            self.ID = ser.ID

    @inlineCallbacks
    def initServer(self):
        """Default method used to initialize a serial server.

        Override this method if the derived server needs to do other things at startup.
        """
        if not self.regKey or not self.serNode:
            raise SerialDeviceError("Must define regKey & serNode attributes")
        self.port = yield self.getPortFromReg(self.regKey)
        try:
            serStr = yield self.findSerial(self.serNode)
            self.initSerial(serStr, self.port, baudrate=self.baudrate)
        except SerialConnectionError as e:
            self.ser = None
            if e.code == 0:
                print("Could not find serial server for node: %s" % self.serNode)
                print("Please start correct serial server")
            elif e.code == 1:
                print("Error opening serial connection")
                print("Check set up and restart serial server")
            else:
                raise

    def initSerial(self, serStr, port, **kwargs):
        """Initializes serial connection.

        Attempts to initialize a serial connection using
        given key for serial serial and port string.
        Sets server's ser attribute if successful.

        Parameters:
            serStr: Key for serial server.
            port: Name of port to connect to.

        Raises:
            SerialConnectionError: Error code 1. Raised if we could not create serial connection.
        """
        if kwargs.get("timeout") is None and self.timeout:
            kwargs["timeout"] = self.timeout
        print("\nAttempting to connect at:")
        print("\n\tserver:\t%s" % serStr)
        print("\n\tport:\t%s" % port)
        print(
            "\n\ttimeout:\t%s\n\n"
            % (str(self.timeout) if kwargs.get("timeout") is not None else "No timeout")
        )
        cli = self.client
        try:
            # get server wrapper for serial server
            ser = cli.servers[serStr]
            # instantiate SerialConnection convenience class
            self.ser = self.SerialConnection(ser=ser, port=port, **kwargs)
            print("Serial connection opened.")
        except Error:
            self.ser = None
            raise SerialConnectionError(1)

    @inlineCallbacks
    def getPortFromReg(self, regKey=None):
        """Finds port string in registry given key.

        There must be a 'Ports' directory at the root of the registry folder

        If you do not input a parameter, it will look for the first four
        letters of your name attribute in the registry port keys.

        Args:
            regKey: String used to find key match.

        Returns:
            Name of port.

        Raises:
            PortRegError: Error code 0. Registry does not have
                correct directory structure (['','Ports']).
            PortRegError: Error code 1. Did not find match.
        """
        reg = self.client.registry
        try:
            tmp = yield reg.cd()
            yield reg.cd(["", "Ports"])
            y = yield reg.dir()
            print(y)
            if not regKey:
                if self.name:
                    regKey = self.name[:4].lower()
                else:
                    raise SerialDeviceError("name attribute is None")
            portStrKey = list(filter(lambda x: regKey in x, y[1]))
            if portStrKey:
                portStrKey = portStrKey[0]
            else:
                raise PortRegError(1)
            portStrVal = yield reg.get(portStrKey)
            reg.cd(tmp)
            returnValue(portStrVal)
        except Error as e:
            reg.cd(tmp)
            if e.code == 17:
                raise PortRegError(0)
            else:
                raise

    @inlineCallbacks
    def selectPortFromReg(self):
        """Selects port string from list of keys in registry.

        Returns:
            Name of port.

        Raises:
            PortRegError: Error code 0.  Registry not properly configured (['','Ports']).
            PortRegError: Error code 1.  No port keys in registry.
        """
        reg = self.client.registry
        try:
            yield reg.cd(["", "Ports"])
            portDir = yield reg.dir()
            portKeys = portDir[1]
            if not portKeys:
                raise PortRegError(2)
            keyDict = {}
            map(
                lambda x, y: keyDict.update({x: y}),
                [str(i) for i in range(len(portKeys))],
                portKeys,
            )
            for key in keyDict:
                print(key, ":", keyDict[key])
            selection = None
            while True:
                print("Select the number corresponding to the device you are using:")
                selection = input("")
                if selection in keyDict:
                    portStr = yield reg.get(keyDict[selection])
                    returnValue(portStr)
        except Error as e:
            if e.code == 13:
                raise PortRegError(0)
            else:
                raise

    @inlineCallbacks
    def findSerial(self, serNode=None):
        """Finds appropriate serial server.

        Look for servers with 'serial' and serNode in the name, take first result

        Args:
            serNode: Name of labrad node possessing desired serial port

        Returns:
            Key of serial server.

        Raises:
            SerialConnectionError: Error code 0.  Could not find desired serial server.
        """
        if not serNode:
            serNode = self.serNode
        cli = self.client
        servers = yield cli.manager.servers()
        try:
            returnValue([i[1] for i in servers if self._matchSerial(serNode, i[1])][0])
        except IndexError:
            raise SerialConnectionError(0)

    @staticmethod
    def _matchSerial(serNode, potMatch):
        """Checks if server name is the correct serial server.

        Args:
            serNode: Name of node of desired serial server.
            potMatch: Server name of potential match.

        Returns:
            boolean indicating comparison result.
        """
        serMatch = "serial" in potMatch.lower()
        nodeMatch = serNode.lower() in potMatch.lower()
        return serMatch and nodeMatch

    def checkConnection(self):
        if not self.ser:
            raise SerialConnectionError(2)

    def serverConnected(self, ID, name):
        """Checks to see if we can connect to serial server now."""
        should_init = (
            self.ser is None
            and None not in (self.port, self.serNode)
            and self._matchSerial(self.serNode, name)
        )
        if should_init:
            self.initSerial(name, self.port)
            print("Serial server connected after we connected")

    def serverDisconnected(self, ID, name):
        """Closes connection (if we are connected)."""
        if self.ser and self.ser.ID == ID:
            print("Serial server disconnected.  Relaunch the serial server")
            self.ser = None

    def stopServer(self):
        """Closes serial connection before exiting."""
        if self.ser:
            self.ser.close()
