from qcodes.instrument.base import Instrument
from qcodes.instrument.parameter import Parameter
import numpy as np
from time import sleep


class CustomYokogawa(Instrument):
    """Meta instrument that wraps the Yokogawa GS210 to allow setting (x) fields
    rather than currents.

    x-field is hardcoded to allow for easy integrating into CustomMagnet below,
    but we could/should generalize this.

    """

    def __init__(self, name, yokogawa, coil_constant, step=1e-6, delay=10e-3):
        super().__init__(name)

        self.source = yokogawa
        self.coil_constant = coil_constant
        self._field_target = self.source.x_measured()
        self.step = step
        self.delay = delay

        self.add_parameter(
            "x_measured", unit="T", label="x measured field", get_cmd=self._get_field,
        )

        self.add_parameter(
            "x_target",
            unit="T",
            label="x target field",
            get_cmd=self._get_target,
            set_cmd=self._set_target,
        )

    def _get_field(self):
        if self.source.output() == "off":
            B_value = 0
        else:
            I_value = self.source.current()
            B_value = I_value / self.coil_constant
        return B_value

    def _get_target(self):
        return self._field_target

    def _set_target(self, val):
        self._field_target = val * self.coil_constant

    def ramp_to_target(self):
        self.source.source_mode("CURR")
        self.source.output("on")
        self.source.ramp_current(
            ramp_to=self.x_target(), step=self.step, delay=self.delay
        )


class CustomKeysightE(Instrument):
    """Meta instrument that wraps the Keysight E36313A to allow setting (x) fields
    rather than currents.

    x-field is hardcoded to allow for easy integrating into CustomMagnet below,
    but we could/should generalize this.

    """

    def __init__(self, name, keysightE, coil_constant):
        super().__init__(name)

        self.source = keysightE
        self.coil_constant = coil_constant
        self._field_target = self.source.x_measured()

        self.add_parameter(
            "x_measured", unit="T", label="x measured field", get_cmd=self._get_field,
        )

        self.add_parameter(
            "x_target",
            unit="T",
            label="x target field",
            get_cmd=self._get_target,
            set_cmd=self._set_target,
        )

    def _get_field(self):
        if self.source.ch1.enable() == "off":
            B_value = 0
        else:
            I_value = self.source.ch1.current()
            B_value = I_value / self.coil_constant
        return B_value

    def _get_target(self):
        return self._field_target

    def _set_target(self, val):
        self._field_target = val * self.coil_constant

    def ramp_to_target(self):
        self.source.ch1.enable("on")
        self.source.ch1.source_current(self.x_target())


class CustomMagnet(Instrument):
    """
    Meta instrument to control the magnet using the MercuryIPS for the y and z axes
    and a second source for the x axis.
    """

    def __init__(self, name, mercury_IPS, x_source):
        super().__init__(name)

        self.mercury = mercury_IPS
        self.x_source = x_source

        self.add_parameter(
            "x_measured",
            unit="T",
            label="x measured field",
            get_cmd=self.x_source.x_measured,
        )

        self.add_parameter(
            "x_target",
            unit="T",
            label="x target field",
            get_cmd=self.x_source.x_target,
            set_cmd=self.x_source.x_target,
        )

        self.add_parameter(
            "y_measured",
            unit="T",
            label="y measured field",
            get_cmd=self.mercury.y_measured,
        )

        self.add_parameter(
            "y_target",
            unit="T",
            label="y target field",
            get_cmd=self.mercury.y_target,
            set_cmd=self.mercury.y_target,
        )

        self.add_parameter(
            "z_measured",
            unit="T",
            label="z measured field",
            get_cmd=self.mercury.z_measured,
        )

        self.add_parameter(
            "z_target",
            unit="T",
            label="z target field",
            get_cmd=self.mercury.z_target,
            set_cmd=self.mercury.z_target,
        )

    def ramp(self):
        """Ramp the fields to their present target value. Mode is always 'safe' for
        now. Did not implement the others.

        In 'safe' mode, the fields are ramped one-by-one in a blocking way that
        ensures that the total field stays within the safe region (provided that
        this region is convex).

        """

        meas_vals = self._get_measured()
        targ_vals = self._get_targets()
        order = np.argsort(np.abs(np.array(targ_vals) - np.array(meas_vals)))

        for slave in np.array(["x", "y", "z"])[order]:
            if slave == "y" or slave == "z":
                eval(self.mercury.slave.ramp_to_target())
                # now just wait for the ramp to finish
                # (unless we are testing)
                while slave.ramp_status() == "TO SET":
                    sleep(0.1)
            elif slave == "x":
                eval(self.x_source.slave.ramp_to_target())

        self._update_field()

    def _get_measured(self):
        field_components = []
        for axis in ["x", "y", "z"]:
            field_components.append(eval("self.{0:}_measured()".format(axis)))
        return field_components

    def _get_targets(self):
        field_components = []
        for axis in ["x", "y", "z"]:
            field_components.append(eval("self.{0:}_target()".format(axis)))
        return field_components

    def _update_field(self):
        coords = ["x", "y", "z"]
        [getattr(self, f"{i}_measured").get() for i in coords]