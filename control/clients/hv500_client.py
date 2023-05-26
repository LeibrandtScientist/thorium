from functools import partial
from PyQt5 import QtWidgets
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from thorium.control.clients.qtui.QCustomSpinBox import QCustomSpinBox


class HV500Client(QtWidgets.QWidget):
    """Client for HV500 high voltage power supply."""

    def __init__(self, reactor, parent=None):
        super(HV500Client, self).__init__()
        self.setWindowTitle("HV500 Client")
        self.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.reactor = reactor

        self.ch_gen = range(1, 17)
        self._loop_updates = []
        for kk in self.ch_gen:
            loop = LoopingCall(partial(self._update_voltage, kk))
            self._loop_updates.append(loop)

        self.connect()

    @inlineCallbacks
    def connect(self):
        """
        Connects to LabRAD and initializes the GUI.

        GUI init is placed in this function rather than __init__,
        because this function runs async, and GUI initialization should happen after connect.
        """
        from labrad.wrappers import connectAsync

        self.cxn = yield connectAsync(name="HV500 Client")
        self.server = yield self.cxn.hv500_server
        self._vmax = 300
        self._vmin = -300
        self.initializeGUI()
        yield self._update_widgets()
        self._connect_widgets()

    def _get_vmon_text(self, channel, voltage):
        """Returns label text for a voltage monitor label."""
        return f"V{channel}: {voltage} V"

    def _get_qbox_channel(self, channel):
        """Returns a QGroupBox instance that contains controls for a output channel."""
        qbox = QtWidgets.QGroupBox(f"Channel {channel}")
        sub_layout = QtWidgets.QGridLayout()
        qbox.setLayout(sub_layout)

        vmon = QtWidgets.QLabel(self._get_vmon_text(channel, 0))
        self._vmon_labels.append(vmon)
        sub_layout.addWidget(vmon, 0, 0, 1, 2)

        vset = QCustomSpinBox("Setpoint (V): ", (-self._vmax, self._vmax))
        vset.spinLevel.setDecimals(1)
        vset.setStepSize(1)
        self._vset_spinboxes.append(vset)
        sub_layout.addWidget(vset, 2, 0, 1, 2)

        return qbox

    def initializeGUI(self):
        layout = QtWidgets.QGridLayout()

        qbox = QtWidgets.QGroupBox("HV500 Client")
        sub_layout = QtWidgets.QGridLayout()
        qbox.setLayout(sub_layout)
        layout.addWidget(qbox, 0, 0)

        self._vmon_labels = []
        self._vset_spinboxes = []
        self._vset_update_buttons = []
        self._status_labels = []

        for kk in self.ch_gen:
            qbox_channel = self._get_qbox_channel(kk)
            if kk <= 8:
                sub_layout.addWidget(qbox_channel, 0, kk - 1)
            else:
                sub_layout.addWidget(qbox_channel, 1, kk - 1 - 8)
            self._begin_mon_update(kk)

        self.setLayout(layout)

    def _connect_widgets(self):
        """Connects widget events with the corresponding functions."""
        for kk in self.ch_gen:
            self._vset_spinboxes[kk - 1].spinLevel.valueChanged.connect(
                partial(self._vset_changed, kk)
            )

    def _begin_mon_update(self, channel):
        """Sets the update period of the voltage monitor of a channel to 5 seconds."""
        self._loop_updates[channel - 1].start(5)

    @inlineCallbacks
    def _update_voltage(self, channel, recall=False):
        """Updates the voltage of a channel from the server."""
        vmon = yield self.server.get_voltage(channel)
        self._vmon_labels[channel - 1].setText(self._get_vmon_text(channel, vmon))
        if recall: return vmon

    @inlineCallbacks
    def _update_widgets(self):
        """Updates all voltages from the server."""
        for kk in self.ch_gen:
            v_init = yield self._update_voltage(kk, recall=True)
            self._vset_spinboxes[kk - 1].setValues(round(v_init))

    @inlineCallbacks
    def _vset_changed(self, channel, value):
        """Changes the server voltage setpoint when the spinbox is changed."""
        yield self.server.set_voltage(channel, value)

    def closeEvent(self, x):
        self.reactor.stop()


if __name__ == "__main__":
    a = QtWidgets.QApplication([])
    import qt5reactor

    qt5reactor.install()
    from twisted.internet import reactor

    client = HV500Client(reactor)
    client.show()
    reactor.run()
