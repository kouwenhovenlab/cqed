# Authors: Lukas Splitthoff, Lukas Gruenhaupt, Arno Bargerbos @TUDelft

from pysweep.core.measurementfunctions import MakeMeasurementFunction
from pysweep.core.sweepobject import SweepObject
from pysweep.databackends.base import DataParameter
import numpy as np
from warnings import showwarning


def field_limit(Bx, By, Bz, max_field_strength=1.5) -> bool:
    """ Calculate the absolute field amplitude and check against the max_field_strength.
    For use with QCoDeS oxford.MercuryiPS_VISA driver.
    Inputs:
    Bx, By, Bz (float): magnetic field components
    Outputs:
    bool: true, if sqrt(Bx^2+By^2+Bz^2) < max_field_strength; else false
    """
    if max_field_strength > 1.5:
        showwarning(
            "Be aware that mu-metal shields are saturated by too large magnetic fields and will not work afterwards. "
            "Are you sure you want to go to more than 1.5 T?",
            ResourceWarning,
            "cqed/cqed/custom_pysweep_functions/magnet",
            20,
        )

    if np.sqrt(Bx ** 2 + By ** 2 + Bz ** 2) > max_field_strength:
        return bool(False)

    else:
        return bool(True)


class Magnet:
    """ A class containing a set of functions to conveniently use for magnet sweeping with pysweep.
    Code assumes that the magnet instrument provided has a similar get/set_field structure as the Oxford Mercury IPS.
    To also include the AMI sources we might have to get a little creative. 
    """

    def __init__(self, instrument):
        self.magnet = instrument

    def measure_magnet_components(self):
        """ Measure the x, y, z component of the magnet and return as list
        output: [x, y, z]
        """

        @MakeMeasurementFunction(
            [
                DataParameter(name="x", unit="T"),
                DataParameter(name="y", unit="T"),
                DataParameter(name="z", unit="T"),
            ]
        )
        def measurement_function(d):
            x_meas = self.magnet.x_measured()
            y_meas = self.magnet.y_measured()
            z_meas = self.magnet.z_measured()
            return [x_meas, y_meas, z_meas]

        return measurement_function

    def measure_magnet_components_sph(self):
        """ Measure the x, y, z component of the magnet, convert to spherical using the 
        ISO 80000-2:2009 physics convention for the (r, theta, phi) <--> (x, y, z) definition 
        and return as list. 
        output: [r, theta, phi] 
        r (float): magentic field strength, unit: T
        theta (float): inclination angle, unit: degrees, 0 <= theta <= 180
        phi (float): the azimuth (in plane) angle, unit: degrees, range: 0 <= phi < 360
        """

        @MakeMeasurementFunction(
            [
                DataParameter(name="r", unit="T"),
                DataParameter(name="theta", unit="deg"),
                DataParameter(name="phi", unit="deg"),
            ]
        )
        def measurement_function(d):
            x = self.magnet.x_measured() + 1e-9  # avoiding dividing by true zero
            y = self.magnet.y_measured() + 1e-9
            z = self.magnet.z_measured() + 1e-9

            r_meas = np.sqrt(x ** 2 + y ** 2 + z ** 2)
            phi_meas = np.arctan2(y, x) / np.pi * 180
            if phi_meas < 0:
                phi_meas += 360
            theta_meas = np.arccos(z / r_meas) / np.pi * 180

            return [r_meas, theta_meas, phi_meas]

        return measurement_function

    def sweep_phi(self, r, theta, points, max_field_strength=1.5, use_conventions=True):
        """ Generate a pysweep.SweepObject to sweep phi at fixed amplitude and theta.
        Here we use the ISO 80000-2:2009 physics convention for the (r, theta, phi) <--> (x, y, z) definition. 
        Only values for the x, y, and z component are passed to the magnet.

        Inputs:
        r (float): magentic field strength, unit: T
        theta (float): inclination angle, unit: degrees, 0 <= theta <= 180
        points (float): sweep values for phi, i.e. the azimuth (in plane) angle, unit: degrees, range: 0 <= phi <= 360 
        max_field_strength (float): maximum magnetic field strength, unit: T
        use_conventions (boolean): check if the values specified are consistent with conventions. Can be problematic when sweeping through 0 degrees.

        Output:
        pysweep.SweepObject
        """

        if max_field_strength > 1.5:
            showwarning(
                "Be aware that mu-metal shields are saturated by too large magnetic fields and will not work afterwards."
                "Are you sure you want to go to more than 1.5 T?",
                ResourceWarning,
                "cqed/cqed/custom_pysweep_functions/magnet",
                60,
            )

        @MakeMeasurementFunction([])
        def point_function(d):
            return points, []

        @MakeMeasurementFunction([])
        def set_function(phi, d):

            if use_conventions:
                assert max_field_strength > r >= 0, (
                    "The field amplitude must not exceed {} and be larger than 0."
                    " Upper limit can be adjusted with kwarg: max_field_strength."
                    " Proceed with caution (Mu-metal shields do not appreciate high fields!)".format(
                        max_field_strength
                    )
                )
                assert (
                    0.0 <= theta <= 180.0
                ), "The inclination angle must be equal or lager than 0 and smaller or equal than 180. Change setting!"
                assert (
                    0.0 <= phi <= 2 * 180.0
                ), "The azimuth angle must be equal or larger than 0 and smaller or equal than 360. Change setting!"

            assert max_field_strength > np.abs(r) >= 0, (
                "The field amplitude must not exceed {} and be larger than 0."
                " Upper limit can be adjusted with kwarg: max_field_strength."
                " Proceed with caution (Mu-metal shields do not appreciate high fields!)".format(
                    max_field_strength
                )
            )

            x = r * np.sin(np.radians(theta)) * np.cos(np.radians(phi))
            y = r * np.sin(np.radians(theta)) * np.sin(np.radians(phi))
            z = r * np.cos(np.radians(theta))

            self.magnet.x_target(x)
            self.magnet.y_target(y)
            self.magnet.z_target(z)

            self.magnet.ramp(mode="safe")

            return []

        return SweepObject(
            set_function=set_function,
            unit="degrees",
            label="phi",
            point_function=point_function,
            dataparameter=None,
        )

    def sweep_theta(self, r, phi, points, max_field_strength=1.5, use_conventions=True):
        """ Generate a pysweep.SweepObject to sweep theta at fixed amplitude and phi.
        Here we use the ISO 80000-2:2009 physics convention for the (r, theta, phi) <--> (x, y, z) definition. 
        Only values for the x, y, and z component are passed to the magnet.

        Inputs:
        r (float): magentic field strength, unit: T
        phi (float): the azimuth (in plane) angle, unit: degrees, range: 0 <= phi <= 360
        points (float): sweep values for theta, i.e. the inclination angle, unit: degrees, range: 0 <= phi <= 180
        max_field_strength (float): maximum magnetic field strength, unit: T
        use_conventions (boolean): check if the values specified are consistent with conventions. Can be problematic when sweeping through 0 degrees.

        Output:
        pysweep.SweepObject
        """

        if max_field_strength > 1.5:
            showwarning(
                "Be aware that mu-metal shields are saturated by too large magnetic fields and will not work afterwards."
                "Are you sure you want to go to more than 1.5 T?",
                ResourceWarning,
                "cqed/cqed/custom_pysweep_functions/magnet",
                109,
            )

        @MakeMeasurementFunction([])
        def point_function(d):
            return points, []

        @MakeMeasurementFunction([])
        def set_function(theta, d):
            # Here we use the ISO 80000-2:2009 physics convention for the (r, theta, phi) <--> (x, y, z) definition.
            # Note that r is the radial distance, theta the inclination and phi the azimuth (in-plane) angle.
            # For uniqueness, we restrict the parameter choice to r>=0, 0<= theta <= pi and 0<= phi <= 2pi.
            # The units are: r in T, theta in degrees, phi in degrees.

            if use_conventions:
                assert max_field_strength > r >= 0, (
                    "The field amplitude must not exceed {} and be larger than 0."
                    " Upper limit can be adjusted with kwarg: max_field_strength."
                    " Proceed with caution (Mu-metal shields do not appreciate high fields!)".format(
                        max_field_strength
                    )
                )
                assert (
                    0.0 <= theta <= 180.0
                ), "The inclination angle must be equal or lager than 0 and smaller or equal than 180. Change setting!"
                assert (
                    0.0 <= phi <= 2 * 180.0
                ), "The azimuth angle must be equal or larger than 0 and smaller or equal than 360. Change setting!"

            assert max_field_strength > np.abs(r) >= 0, (
                "The field amplitude must not exceed {} and be larger than 0."
                " Upper limit can be adjusted with kwarg: max_field_strength."
                " Proceed with caution (Mu-metal shields do not appreciate high fields!)".format(
                    max_field_strength
                )
            )

            x = r * np.sin(np.radians(theta)) * np.cos(np.radians(phi))
            y = r * np.sin(np.radians(theta)) * np.sin(np.radians(phi))
            z = r * np.cos(np.radians(theta))

            self.magnet.x_target(x)
            self.magnet.y_target(y)
            self.magnet.z_target(z)

            self.magnet.ramp(mode="safe")

            return []

        return SweepObject(
            set_function=set_function,
            unit="degrees",
            label="theta",
            point_function=point_function,
            dataparameter=None,
        )

    def sweep_r(self, phi, theta, points, max_field_strength=1.5, use_conventions=True):
        """ Generate a pysweep.SweepObject to sweep field amplitude at fixed phi and theta.
        Here we use the ISO 80000-2:2009 physics convention for the (r, theta, phi) <--> (x, y, z) definition. 
        Only values for the x, y, and z component are passed to the magnet.

        Inputs:
        phi (float): the azimuth (in plane) angle, unit: degrees, range: 0 <= phi <= 360
        theta (float): inclination angle, unit: degrees, 0 <= theta <= 180
        points (float): sweep values for r, i.e. the magentic field strength, unit: T, range: 0 <= r <= max_field_strength
        max_field_strength (float): maximum magnetic field strength, unit: T
        use_conventions (boolean): check if the values specified are consistent with conventions. Can be problematic when sweeping through 0 magnitude.

        Output:
        pysweep.SweepObject
        """

        if max_field_strength > 1.5:
            showwarning(
                "Be aware that mu-metal shields are saturated by too large magnetic fields and will not work afterwards."
                "Are you sure you want to go to more than 1.5 T?",
                ResourceWarning,
                "cqed/cqed/custom_pysweep_functions/magnet",
                162,
            )

        @MakeMeasurementFunction([])
        def point_function(d):
            return points, []

        @MakeMeasurementFunction([])
        def set_function(r, d):
            # Here we use the ISO 80000-2:2009 physics convention for the (r, theta, phi) <--> (x, y, z) definition.
            # Note that r is the radial distance, theta the inclination and phi the azimuth (in-plane) angle.
            # For uniqueness, we restrict the parameter choice to r>=0, 0<= theta <= pi and 0<= phi <= 2pi.
            # The units are: r in T, theta in degrees, phi in degrees.

            if use_conventions:
                assert max_field_strength > r >= 0, (
                    "The field amplitude must not exceed {} and be larger than 0."
                    " Upper limit can be adjusted with kwarg: max_field_strength."
                    " Proceed with caution (Mu-metal shields do not appreciate high fields!)".format(
                        max_field_strength
                    )
                )
                assert (
                    0.0 <= theta <= 180.0
                ), "The inclination angle must be equal or lager than 0 and smaller or equal than 180. Change setting!"
                assert (
                    0.0 <= phi <= 2 * 180.0
                ), "The azimuth angle must be equal or larger than 0 and smaller or equal than 360. Change setting!"

            assert max_field_strength > np.abs(r) >= 0, (
                "The field amplitude must not exceed {} and be larger than 0."
                " Upper limit can be adjusted with kwarg: max_field_strength."
                " Proceed with caution (Mu-metal shields do not appreciate high fields!)".format(
                    max_field_strength
                )
            )

            x = r * np.sin(np.radians(theta)) * np.cos(np.radians(phi))
            y = r * np.sin(np.radians(theta)) * np.sin(np.radians(phi))
            z = r * np.cos(np.radians(theta))

            self.magnet.x_target(x)
            self.magnet.y_target(y)
            self.magnet.z_target(z)

            self.magnet.ramp(mode="safe")

            return []

        return SweepObject(
            set_function=set_function,
            unit="T",
            label="r",
            point_function=point_function,
            dataparameter=None,
        )

    def sweep_x(self, points, max_field_strength=1.5):
        ''' Generate a pysweep.SweepObject to sweep field x amplitude at fixed y and z.
        Inputs:
        points (float): sweep values for x, i.e. the magentic field strength, unit: T, range: -max_field_strength <= x <= max_field_strength
        max_field_strength (float): maximum magnetic field strength, unit: T
        Output:
        pysweep.SweepObject
        '''

        if max_field_strength > 1.5:
            showwarning('Be aware that mu-metal shields are saturated by too large magnetic fields and will not work afterwards.'
                        'Are you sure you want to go to more than 1.5 T?', ResourceWarning, 'cqed/cqed/custom_pysweep_functions/magnet', 162)

        @MakeMeasurementFunction([])
        def point_function(d):
            return points, []

        @MakeMeasurementFunction([])
        def set_function(x, d):
            assert max_field_strength > np.abs(x) >= 0, 'The field amplitude must not exceed {} and be lager than 0.' \
                ' Upper limit can be adjusted with kwarg: max_field_strength.' \
                ' Proceed with caution (Mu-metal shields do not appreciate high fields!)'.format(
                max_field_strength)

            self.magnet.x_target(x)
            self.magnet.ramp(mode="safe")

            return []

        return SweepObject(set_function=set_function, unit="T", label="x_field", point_function=point_function, dataparameter=None)

    def sweep_y(self, points, max_field_strength=1.5):
        ''' Generate a pysweep.SweepObject to sweep field y amplitude at fixed x and z.
        Inputs:
        points (float): sweep values for y, i.e. the magentic field strength, unit: T, range: -max_field_strength <= y <= max_field_strength
        max_field_strength (float): maximum magnetic field strength, unit: T
        Output:
        pysweep.SweepObject
        '''

        if max_field_strength > 1.5:
            showwarning('Be aware that mu-metal shields are saturated by too large magnetic fields and will not work afterwards.'
                        'Are you sure you want to go to more than 1.5 T?', ResourceWarning, 'cqed/cqed/custom_pysweep_functions/magnet', 162)

        @MakeMeasurementFunction([])
        def point_function(d):
            return points, []

        @MakeMeasurementFunction([])
        def set_function(y, d):
            assert max_field_strength > np.abs(y) >= 0, 'The field amplitude must not exceed {} and be lager than 0.' \
                ' Upper limit can be adjusted with kwarg: max_field_strength.' \
                ' Proceed with caution (Mu-metal shields do not appreciate high fields!)'.format(
                max_field_strength)

            self.magnet.y_target(y)
            self.magnet.ramp(mode="safe")

            return []

        return SweepObject(set_function=set_function, unit="T", label="y_field", point_function=point_function, dataparameter=None)

    def sweep_z(self, points, max_field_strength=1.5):
        ''' Generate a pysweep.SweepObject to sweep field z amplitude at fixed x and y.
        Inputs:
        points (float): sweep values for z, i.e. the magentic field strength, unit: T, range: -max_field_strength <= z <= max_field_strength
        max_field_strength (float): maximum magnetic field strength, unit: T
        Output:
        pysweep.SweepObject
        '''

        if max_field_strength > 1.5:
            showwarning('Be aware that mu-metal shields are saturated by too large magnetic fields and will not work afterwards.'
                        'Are you sure you want to go to more than 1.5 T?', ResourceWarning, 'cqed/cqed/custom_pysweep_functions/magnet', 162)

        @MakeMeasurementFunction([])
        def point_function(d):
            return points, []

        @MakeMeasurementFunction([])
        def set_function(z, d):
            assert max_field_strength > np.abs(z) >= 0, 'The field amplitude must not exceed {} and be lager than 0.' \
                ' Upper limit can be adjusted with kwarg: max_field_strength.' \
                ' Proceed with caution (Mu-metal shields do not appreciate high fields!)'.format(
                max_field_strength)

            self.magnet.z_target(z)
            self.magnet.ramp(mode="safe")

            return []

        return SweepObject(set_function=set_function, unit="T", label="z_field", point_function=point_function, dataparameter=None)