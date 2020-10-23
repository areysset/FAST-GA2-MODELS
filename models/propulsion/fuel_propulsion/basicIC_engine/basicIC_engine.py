"""Parametric propeller IC engine."""
# -*- coding: utf-8 -*-
#  This file is part of FAST : A framework for rapid Overall Aircraft Design
#  Copyright (C) 2020  ONERA & ISAE-SUPAERO
#  FAST is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import logging

import numpy as np
import pandas as pd
from typing import Union, Sequence, Tuple, Optional

from fastoad.base.flight_point import FlightPoint
from fastoad.constants import EngineSetting
from fastoad.exceptions import FastUnknownEngineSettingError
from .exceptions import FastBasicICEngineInconsistentInputParametersError
from fastoad.models.propulsion.fuel_propulsion.base import AbstractFuelPropulsion
from fastoad.utils.physics import Atmosphere

# Logger for this module
_LOGGER = logging.getLogger(__name__)

PROPELLER_EFFICIENCY = 0.8


class BasicICEngine(AbstractFuelPropulsion):

    def __init__(
            self,
            max_power: float,
            fuel_type: float,
            strokes_nb: float,
    ):
        """
        Parametric Internal Combustion engine.

        It computes engine characteristics using fuel type, motor architecture
        and constant propeller efficiency using analytical model from following sources:

        :param max_power: maximum delivered mechanical power of engine (unit=W)
        :param fuel_type: 1.0 for gasoline and 2.0 for gasoil engine
        :param strokes_nb: can be either 2-strockes (=2.0) or 4-strockes (=4.0)
        """

        if (fuel_type != 1.0) and (fuel_type != 2.0):
            raise FastBasicICEngineInconsistentInputParametersError(
                "Bad engine configuration: fuel type {0:d} model does not exist.".format(fuel_type)
            )

        if (strokes_nb != 2.0) and (strokes_nb != 4.0):
            raise FastBasicICEngineInconsistentInputParametersError(
                "Bad engine configuration: {0:d}-strokes model does not exist.".format(strokes_nb)
            )

        self.ref = {
            "max_power": 132480,
            "max_thrust": 3600,
            "length": 0.83,
            "height": 0.57,
            "width": 0.85,
            "mass": 136,
        } # Lycoming IO-360-B1A
        self.max_power = max_power
        self.fuel_type = fuel_type
        self.strokes_nb = strokes_nb
        self.idle_thrust_rate = 0.01

        # This dictionary is expected to have a Mixture coefficient for all EngineSetting values
        self.mixture_values = {
            EngineSetting.TAKEOFF: 1.5,
            EngineSetting.CLIMB: 1.5,
            EngineSetting.CRUISE: 1.0,
            EngineSetting.IDLE: 1.0,
        }

        # ... so check that all EngineSetting values are in dict
        unknown_keys = [key for key in EngineSetting if key not in self.mixture_values.keys()]
        if unknown_keys:
            raise FastUnknownEngineSettingError("Unknown flight phases: %s", unknown_keys)

    def compute_flight_points(self, flight_points: Union[FlightPoint, pd.DataFrame]):
        # pylint: disable=too-many-arguments  # they define the trajectory
        sfc, thrust_rate, thrust = self._compute_flight_points(
            flight_points.mach,
            flight_points.altitude,
            flight_points.engine_setting,
            flight_points.thrust_is_regulated,
            flight_points.thrust_rate,
            flight_points.thrust,
        )
        flight_points.sfc = sfc
        flight_points.thrust_rate = thrust_rate
        flight_points.thrust = thrust

    def _compute_flight_points(
            self,
            mach: Union[float, Sequence],
            altitude: Union[float, Sequence],
            engine_setting: Union[float, Sequence],
            thrust_is_regulated: Optional[Union[bool, Sequence]] = None,
            thrust_rate: Optional[Union[float, Sequence]] = None,
            thrust: Optional[Union[float, Sequence]] = None,
    ) -> Tuple[Union[float, Sequence], Union[float, Sequence], Union[float, Sequence]]:
        """
        Same as :meth:`compute_flight_points`.

        :param mach: Mach number
        :param altitude: (unit=m) altitude w.r.t. to sea level
        :param engine_setting: define engine settings
        :param thrust_is_regulated: tells if thrust_rate or thrust should be used (works element-wise)
        :param thrust_rate: thrust rate (unit=none)
        :param thrust: required thrust (unit=N)
        :return: SFC (in kg/s/N), thrust rate, thrust (in N)
        """
        """
        Computes the Specific Fuel Consumption based on aircraft trajectory conditions.
        
        :param flight_points.mach: Mach number
        :param flight_points.altitude: (unit=m) altitude w.r.t. to sea level
        :param flight_points.engine_setting: define
        :param flight_points.thrust_is_regulated: tells if thrust_rate or thrust should be used (works element-wise)
        :param flight_points.thrust_rate: thrust rate (unit=none)
        :param flight_points.thrust: required thrust (unit=N)
        :return: SFC (in kg/s/N), thrust rate, thrust (in N)
        """

        # Treat inputs (with check on thrust rate <=1.0)
        mach = np.asarray(mach)
        altitude = np.asarray(altitude)
        engine_setting = np.asarray(engine_setting)
        if thrust_is_regulated is not None:
            thrust_is_regulated = np.asarray(np.round(thrust_is_regulated, 0), dtype=bool)
        thrust_is_regulated, thrust_rate, thrust = self._check_thrust_inputs(
            thrust_is_regulated, thrust_rate, thrust
        )
        thrust_is_regulated = np.asarray(np.round(thrust_is_regulated, 0), dtype=bool)
        thrust_rate = np.asarray(thrust_rate)
        thrust = np.asarray(thrust)

        # Get maximum thrust @ given altitude
        atmosphere = Atmosphere(altitude, altitude_in_feet=False)
        max_thrust = self.max_thrust(atmosphere, mach)

        # We compute thrust values from thrust rates when needed
        idx = np.logical_not(thrust_is_regulated)
        if np.size(max_thrust) == 1:
            maximum_thrust = max_thrust
            out_thrust_rate = thrust_rate
            out_thrust = thrust
        else:
            out_thrust_rate = (
                np.full(np.shape(max_thrust), thrust_rate.item())
                if np.size(thrust_rate) == 1
                else thrust_rate
            )
            out_thrust = (
                np.full(np.shape(max_thrust), thrust.item()) if np.size(thrust) == 1 else thrust
            )
            maximum_thrust = max_thrust[idx]
        if np.any(idx):
            out_thrust[idx] = out_thrust_rate[idx] * maximum_thrust

        # thrust_rate is obtained from entire thrust vector (could be optimized if needed,
        # as some thrust rates that are computed may have been provided as input)
        out_thrust_rate = out_thrust / max_thrust

        # Now SFC can be computed
        sfc_pmax = self.sfc_at_max_power(atmosphere)
        sfc_ratio, mech_power = self.sfc_ratio(altitude, out_thrust_rate, mach)
        sfc = (sfc_pmax * sfc_ratio * mech_power) / np.maximum(out_thrust, 1e-6) # avoid 0 division

        return sfc, out_thrust_rate, out_thrust

    @staticmethod
    def _check_thrust_inputs(
            thrust_is_regulated: Optional[Union[float, Sequence]],
            thrust_rate: Optional[Union[float, Sequence]],
            thrust: Optional[Union[float, Sequence]],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Checks that inputs are consistent and return them in proper shape.
        Some of the inputs can be None, but outputs will be proper numpy arrays.
        :param thrust_is_regulated:
        :param thrust_rate:
        :param thrust:
        :return: the inputs, but transformed in numpy arrays.
        """
        # Ensure they are numpy array
        if thrust_is_regulated is not None:
            # As OpenMDAO may provide floats that could be slightly different
            # from 0. or 1., a rounding operation is needed before converting
            # to booleans
            thrust_is_regulated = np.asarray(np.round(thrust_is_regulated, 0), dtype=bool)
        if thrust_rate is not None:
            thrust_rate = np.asarray(thrust_rate)
        if thrust is not None:
            thrust = np.asarray(thrust)

        # Check inputs: if use_thrust_rate is None, we will use the provided input between
        # thrust_rate and thrust
        if thrust_is_regulated is None:
            if thrust_rate is not None:
                thrust_is_regulated = False
                thrust = np.empty_like(thrust_rate)
            elif thrust is not None:
                thrust_is_regulated = True
                thrust_rate = np.empty_like(thrust)
            else:
                raise FastBasicICEngineInconsistentInputParametersError(
                    "When use_thrust_rate is None, either thrust_rate or thrust should be provided."
                )

        elif np.size(thrust_is_regulated) == 1:
            # Check inputs: if use_thrust_rate is a scalar, the matching input(thrust_rate or
            # thrust) must be provided.
            if thrust_is_regulated:
                if thrust is None:
                    raise FastBasicICEngineInconsistentInputParametersError(
                        "When thrust_is_regulated is True, thrust should be provided."
                    )
                thrust_rate = np.empty_like(thrust)
            else:
                if thrust_rate is None:
                    raise FastBasicICEngineInconsistentInputParametersError(
                        "When thrust_is_regulated is False, thrust_rate should be provided."
                    )
                thrust = np.empty_like(thrust_rate)

        else:
            # Check inputs: if use_thrust_rate is not a scalar, both thrust_rate and thrust must be
            # provided and have the same shape as use_thrust_rate
            if thrust_rate is None or thrust is None:
                raise FastBasicICEngineInconsistentInputParametersError(
                    "When thrust_is_regulated is a sequence, both thrust_rate and thrust should be "
                    "provided."
                )
            if np.shape(thrust_rate) != np.shape(thrust_is_regulated) or np.shape(
                    thrust
            ) != np.shape(thrust_is_regulated):
                raise FastBasicICEngineInconsistentInputParametersError(
                    "When use_thrust_rate is a sequence, both thrust_rate and thrust should have "
                    "same shape as use_thrust_rate"
                )

        return thrust_is_regulated, thrust_rate, thrust

    def sfc_at_max_power(self, atmosphere: Atmosphere) -> np.ndarray:
        """
        Computation of Specific Fuel Consumption at maximum power.
        :param atmosphere: Atmosphere instance at intended altitude
        :param mach: Mach number(s)
        :return: SFC_P (in kg/s/W)
        """

        altitude = atmosphere.get_altitude(altitude_in_feet=True)
        sigma = Atmosphere(altitude).density / Atmosphere(0.0).density
        max_power = (self.max_power/1e3) * (sigma - (1 - sigma) / 7.55) # max power in kW

        if self.fuel_type == 1.:
            if self.strokes_nb == 2.:  # Gasoline 2-strokes
                sfc_p = 1125.9 * max_power ** (-0.2441)
            else:  # Gasoline 4-strokes
                sfc_p = -0.0011 * max_power ** 2 + 0.5905 * max_power + 228.58
        elif self.fuel_type == 2.:
            if self.strokes_nb == 2.:  # Diesel 2-strokes
                sfc_p = -0.765 * max_power + 334.94
            else:  # Diesel 4-strokes
                sfc_p = -0.964 * max_power + 231.91

        sfc_p = sfc_p / 1e6 / 3600.0  # change units to be in kg/s/W

        return sfc_p

    def sfc_ratio(
            self,
            altitude: Union[float, Sequence[float]],
            thrust_rate: Union[float, Sequence[float]],
            mach: Union[float, Sequence[float]] = 0.8,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computation of ratio :math:`\\frac{SFC(P)}{SFC(Pmax)}`, given altitude
        and thrust_rate :math:`\\frac{F}{Fmax}`.
        Warning: this model is very limited
        :param altitude:
        :param thrust_rate:
        :param mach: Mach number(s)
        :return: SFC ratio and Power (in W)
        """

        altitude = np.asarray(altitude)
        thrust_rate = np.asarray(thrust_rate)
        mach = np.asarray(mach)
        max_thrust = self.max_thrust(Atmosphere(altitude, altitude_in_feet=False), mach)
        sigma = Atmosphere(altitude, altitude_in_feet=False).density / Atmosphere(0.0).density
        max_power = min(self.max_power * (sigma - (1 - sigma) / 7.55), max_thrust * mach * Atmosphere(altitude).speed_of_sound / PROPELLER_EFFICIENCY)
        prop_power = (max_thrust * thrust_rate * mach * Atmosphere(altitude).speed_of_sound)
        mech_power = prop_power / PROPELLER_EFFICIENCY  # FIXME: low speed efficiency drop down leading to high mechanical power!

        power_rate = mech_power / max_power

        sfc_ratio = (-0.9976 * power_rate ** 2 + 1.9964 * power_rate)

        return sfc_ratio, (power_rate * max_power)

    def max_thrust(
            self,
            atmosphere: Atmosphere,
            mach: Union[float, Sequence[float]],
    ) -> np.ndarray:
        """
        Computation of maximum thrust.
        Uses model described in ...
        :param atmosphere: Atmosphere instance at intended altitude (should be <=20km)
        :param mach: Mach number(s) (should be between 0.05 and 1.0)
        :return: maximum thrust (in N)
        """

        # Calculate maximum mechanical power @ given altitude
        altitude = atmosphere.get_altitude(altitude_in_feet=True)
        mach = np.asarray(mach)
        sigma = Atmosphere(altitude).density / Atmosphere(0.0).density
        max_power = self.max_power * (sigma - (1 - sigma) / 7.55)
        thrust_1 = self.ref["max_thrust"] * max_power / self.ref["max_power"]
        thrust_2 = max_power * PROPELLER_EFFICIENCY / (mach * Atmosphere(altitude).speed_of_sound)

        return np.minimum(thrust_1, thrust_2)

    def engine_weight(self) -> float:
        """
        Computes weight of installed engine, depending on maximum power.
        Uses model described in :...
        :return: installed weight (in kg)
        """
        # FIXME : separate raw engine weight and installation factor
        installation_factor = 1.0
        weight = self.ref["mass"] * (self.max_power / self.ref["max_power"])

        installed_weight = installation_factor * weight

        return installed_weight

    def engine_dim(self) -> Tuple[float, float, float]:
        """
        Computes engine dimensions from maximum power.
        Model from :...
        :return: engine length (in m)
        """
        length = self.ref["length"] * (self.max_power / self.ref["max_power"]) ** (1 / 3)
        height = self.ref["height"] * (self.max_power / self.ref["max_power"]) ** (1 / 3)
        width = self.ref["width"] * (self.max_power / self.ref["max_power"]) ** (1 / 3)

        return length, height, width