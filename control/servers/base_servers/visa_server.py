import pyvisa as visa
from labrad.server import LabradServer
from twisted.internet.defer import inlineCallbacks, returnValue


class VisaServer(LabradServer):
    """Generic LabRAD server for VISA devices."""

    def initServer(self, links):
        try:
            # finds all available VISA devices
            rm = visa.ResourceManager()
            self.instruments = rm.list_resources()

            if len(self.instruments) == 0:
                print("Device not connected!")
            else:
                print("Visa devices: ", self.instruments)
                self.address = ""
                for _name, address in links:
                    if address in self.instruments:
                        self.address = address
                        break

                if self.address == "":
                    print("Device not found!")
                else:
                    self.device = rm.open_resource(self.address)
                    print("Device connected!")

        except visa.VisaIOError:
            print("Pyvisa is not able to find the connections")

    @inlineCallbacks
    def loadConfigInfo(self):
        """Loads configuration information from the registry."""
        if not self.regKey:
            raise Exception("self.regKey must be defined to find the port!")
        self.port = yield self.getPortFromReg(self.regKey)
        self.usb_links = dict([(self.regKey, self.port)])

    @inlineCallbacks
    def getPortFromReg(self, regKey=None):
        """Finds port string in registry given key.

        If you do not input a parameter, it will look for the first four letters
        of your name attribute in the registry port keys.

        Args:
            regKey: String used to find key match.

        Returns:
            Name of port.

        Raises:
            PortRegError: Error code 0.
                Registry does not have correct directory structure (['','Ports']).
            PortRegError: Error code 1.  Did not find match.
        """
        reg = self.client.registry
        # There must be a 'Ports' directory at the root of the registry folder
        try:
            tmp = yield reg.cd()
            yield reg.cd(["", "Ports"])
            y = yield reg.dir()
            print(y)
            if not regKey:
                if self.name:
                    regKey = self.name[:4].lower()
                else:
                    raise Exception("name attribute is None")
            portStrKey = [x for x in y[1] if regKey in x]
            if portStrKey:
                portStrKey = portStrKey[0]
            else:
                raise Exception("")
            portStrVal = yield reg.get(portStrKey)
            reg.cd(tmp)
            returnValue(portStrVal)
        except Exception as e:
            reg.cd(tmp)
            if e.code == 17:
                Exception("")
            else:
                raise
