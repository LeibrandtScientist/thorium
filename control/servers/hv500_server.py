from labrad.support import getNodeName
from labrad.types import Value
from twisted.internet.defer import returnValue

from thorium.control.servers.base_servers.serial_device_server import SerialDeviceServer, inlineCallbacks, setting

SERVERNAME = "hv500_server"
TIMEOUT = 0.1
BAUDRATE = 9600

"""
### BEGIN NODE INFO
[info]
name = hv500 serial server
version = 1.0
description =
instancename = hv500_server

[startup]
cmdline = %PYTHON% %FILE%
timeout = 40

[shutdown]
message = 987654321
timeout = 5
### END NODE INFO
"""

VLIM = 300

class HV500Server(SerialDeviceServer):
    """Serial server for the HV500-16 low noise voltage supply."""

    name = SERVERNAME
    regKey = "HV500_HV264"
    serNode = getNodeName()
    timeout = Value(TIMEOUT, "s")
    baudrate = BAUDRATE

    def channel_to_str(self, channel):
        _channel = str(channel)
        if len(_channel) > 1:
            return _channel
        else:
            return "0" + _channel

    def voltage_to_kw(self, v):
        d = (v+500)/1000
        return f'{d:.6f}'

    @inlineCallbacks
    def initServer(self):
        yield super(HV500Server, self).initServer()
        self.listeners = set()
        self.IDN = self.regKey[-5:]

    @setting(1, returns="s")
    def get_ID(self, c):
        """
        Returns device identification number e.g. 'HV264 500 16 b'.
        First string 'HV264' is the IDN necessary to address device.
        """
        yield self.ser.write("IDN\r")
        val = yield self.ser.read_line()
        returnValue(val)

    @setting(2, channel="i", returns='v')
    def get_voltage(self, c, channel):
        """
        Disclaimer: reading is digitized to 10s of mV.

        Args:
            channel: int, channel between 1 and 16.

        Returns:
            float, voltage in volts.
        """
        ch_str = self.channel_to_str(channel)
        yield self.ser.write(self.IDN+" Q"+ch_str+"\r")
        val = yield self.ser.read_line()
        returnValue(float(val[:-1]))

    @setting(3, channel="i", voltage='v')
    def set_voltage(self, c, channel, voltage):
        """
        Sets voltage on the specified channel.

        Args:
            channel: int, channel between 1 and 16.
            voltage: float, voltage in volts.
        """
        if voltage > VLIM or voltage < -VLIM:
            raise ValueError("Voltage setpoint out of bounds.")
        else:
            ch_str = self.channel_to_str(channel)
            volt_str = self.voltage_to_kw(voltage)
            yield self.ser.write(self.IDN+" CH"+ch_str+" "+volt_str+"\r")


if __name__ == "__main__":
    from labrad import util

    util.runServer(HV500Server())
