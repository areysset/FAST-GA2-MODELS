"""
Estimation of horizontal tail area
"""
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

import numpy as np
import math
import openmdao.api as om
from scipy.constants import g
from fastoad.utils.physics import Atmosphere
from ...aerodynamics.constants import HT_POINT_COUNT
from fastoad import BundleLoader
from fastoad.models.propulsion.fuel_propulsion.base import FuelEngineSet
from fastoad.base.flight_point import FlightPoint
from fastoad.constants import EngineSetting
from typing import Union, List, Optional, Tuple

_ANG_VEL = 12 * math.pi / 180  # 12 deg/s (typical for light aircraft)


class ComputeHTArea(om.Group):
    """
    Computes needed ht area to:
      - have enough rotational power during take-off phase
      - have enough rotational power during landing phase
    """

    def initialize(self):
        self.options.declare("propulsion_id", default="", types=str)

    def setup(self):

        self.add_subsystem(
            "aero_coeff_landing",
            _ComputeAeroCoeff(landing=True),
            promotes=self.get_io_names(_ComputeAeroCoeff(landing=True), iotypes='inputs')
        )
        self.add_subsystem(
            "aero_coeff_takeoff",
            _ComputeAeroCoeff(),
            promotes=self.get_io_names(_ComputeAeroCoeff(), iotypes='inputs')
        )
        self.add_subsystem(
            "ht_area",
            _ComputeArea(propulsion_id=self.options["propulsion_id"]),
            promotes=self.get_io_names(
                _ComputeArea(propulsion_id=self.options["propulsion_id"]),
                excludes=[
                    "landing:cl_ht",
                    "landing:cm_wing",
                    "takeoff:cl_ht",
                    "takeoff:cm_wing",
                    "low_speed:cl_alpha_ht",
                ]
            )
        )

        self.connect("aero_coeff_landing.cl_ht", "ht_area.landing:cl_ht")
        self.connect("aero_coeff_landing.cm_wing", "ht_area.landing:cm_wing")
        self.connect("aero_coeff_takeoff.cl_ht", "ht_area.takeoff:cl_ht")
        self.connect("aero_coeff_takeoff.cm_wing", "ht_area.takeoff:cm_wing")
        self.connect("aero_coeff_takeoff.cl_alpha_ht", "ht_area.low_speed:cl_alpha_ht")

    @staticmethod
    def get_io_names(
            component: om.ExplicitComponent,
            excludes: Optional[Union[str, List[str]]] = None,
            iotypes: Optional[Union[str, Tuple[str]]] = ('inputs', 'outputs')) -> List[str]:
        prob = om.Problem(model=component)
        prob.setup()
        data = []
        if type(iotypes) == tuple:
            data.extend(prob.model.list_inputs(out_stream=None))
            data.extend(prob.model.list_outputs(out_stream=None))
        else:
            if iotypes == 'inputs':
                data.extend(prob.model.list_inputs(out_stream=None))
            else:
                data.extend(prob.model.list_outputs(out_stream=None))
        list_names = []
        for idx in range(len(data)):
            variable_name = data[idx][0]
            if excludes is None:
                list_names.append(variable_name)
            else:
                if variable_name not in list(excludes):
                    list_names.append(variable_name)

        return list_names


class _ComputeArea(om.ExplicitComponent):
    """
    Computes area of horizontal tail plane (internal function)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine_wrapper = None

    def initialize(self):
        self.options.declare("propulsion_id", default="", types=str)

    def setup(self):
        self._engine_wrapper = BundleLoader().instantiate_component(self.options["propulsion_id"])
        self._engine_wrapper.setup(self)

        self.add_input("data:geometry:propulsion:count", val=np.nan)
        self.add_input("settings:weight:aircraft:CG:range", val=0.3)
        self.add_input("data:mission:sizing:takeoff:thrust_rate", val=np.nan)
        self.add_input("data:geometry:wing:area", val=np.nan, units="m**2")
        self.add_input("data:geometry:wing:MAC:at25percent:x", val=np.nan, units="m")
        self.add_input("data:geometry:horizontal_tail:MAC:at25percent:x:from_wingMAC25", val=np.nan, units="m")
        self.add_input("data:geometry:wing:MAC:length", val=np.nan, units="m")
        self.add_input("data:geometry:propulsion:nacelle:height", val=np.nan, units="m")
        self.add_input("data:weight:aircraft:MTOW", val=np.nan, units="kg")
        self.add_input("data:weight:aircraft:MLW", val=np.nan, units="kg")
        self.add_input("data:weight:aircraft:CG:aft:x", val=np.nan, units="m")
        self.add_input("data:weight:airframe:landing_gear:main:CG:x", val=np.nan, units="m")
        self.add_input("data:aerodynamics:aircraft:low_speed:CL0_clean", val=np.nan)
        self.add_input("data:aerodynamics:aircraft:landing:CL_max", val=np.nan)
        self.add_input("data:aerodynamics:aircraft:takeoff:CL_max", val=np.nan)
        self.add_input("data:aerodynamics:wing:low_speed:CL_max_clean", val=np.nan)
        self.add_input("data:aerodynamics:flaps:landing:CL", val=np.nan)
        self.add_input("data:aerodynamics:flaps:takeoff:CL", val=np.nan)
        self.add_input("data:aerodynamics:flaps:landing:CM", val=np.nan)
        self.add_input("data:aerodynamics:flaps:takeoff:CM", val=np.nan)
        self.add_input("data:aerodynamics:horizontal_tail:low_speed:CL_alpha", val=np.nan, units="rad**-1")

        self.add_input("landing:cl_ht", val=np.nan)
        self.add_input("takeoff:cl_ht", val=np.nan)
        self.add_input("landing:cm_wing", val=np.nan)
        self.add_input("takeoff:cm_wing", val=np.nan)
        self.add_input("low_speed:cl_alpha_ht", val=np.nan)

        self.add_output("data:geometry:horizontal_tail:area", val=4.0, units="m**2")

        self.declare_partials("*", "*", method="fd")  # FIXME: write partial avoiding discrete parameters

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        # Sizing constraints for the horizontal tail (methods from Torenbeek).
        # Limiting cases: Rotating power at takeoff/landing, with the most 
        # forward CG position. Returns maximum area.

        propulsion_model = FuelEngineSet(
            self._engine_wrapper.get_model(inputs), inputs["data:geometry:propulsion:count"]
        )
        n_engines = inputs["data:geometry:propulsion:count"]
        cg_range = inputs["settings:weight:aircraft:CG:range"]
        takeoff_t_rate = inputs["data:mission:sizing:takeoff:thrust_rate"]
        wing_area = inputs["data:geometry:wing:area"]
        x_wing_aero_center = inputs["data:geometry:wing:MAC:at25percent:x"]
        lp_ht = inputs["data:geometry:horizontal_tail:MAC:at25percent:x:from_wingMAC25"]
        wing_mac = inputs["data:geometry:wing:MAC:length"]
        z_eng = inputs["data:geometry:propulsion:nacelle:height"]/2
        mtow = inputs["data:weight:aircraft:MTOW"]
        mlw = inputs["data:weight:aircraft:MLW"]
        x_cg_aft = inputs["data:weight:aircraft:CG:aft:x"]
        x_lg = inputs["data:weight:airframe:landing_gear:main:CG:x"]
        cl0_clean = inputs["data:aerodynamics:aircraft:low_speed:CL0_clean"]
        cl_max_landing = inputs["data:aerodynamics:aircraft:landing:CL_max"]
        cl_max_takeoff = inputs["data:aerodynamics:aircraft:takeoff:CL_max"]
        cl_max_clean = inputs["data:aerodynamics:wing:low_speed:CL_max_clean"]
        cl_flaps_landing = inputs["data:aerodynamics:flaps:landing:CL"]
        cl_flaps_takeoff = inputs["data:aerodynamics:flaps:takeoff:CL"]
        cl_ht_landing = inputs["landing:cl_ht"]
        cl_ht_takeoff = inputs["takeoff:cl_ht"]
        cm_landing = inputs["landing:cm_wing"] + inputs["data:aerodynamics:flaps:landing:CM"]
        cm_takeoff = inputs["takeoff:cm_wing"] + inputs["data:aerodynamics:flaps:takeoff:CM"]
        cl_alpha_ht = inputs["low_speed:cl_alpha_ht"]

        # Conditions for calculation
        atm = Atmosphere(0.0)
        rho = atm.density

        # CASE1: TAKE-OFF ##############################################################################################
        # method extracted from Torenbeek 1982 p325

        # Calculation of take-off minimum speed
        weight = mtow * g
        vs0 = math.sqrt(weight / (0.5 * rho * wing_area * cl_max_takeoff))
        vs1 = math.sqrt(weight / (0.5 * rho * wing_area * cl_max_clean))
        # Rotation speed requirement from FAR 23.51 (depends on number of engines)
        if n_engines == 1:
            v_r = vs1 * 1.0
        else:
            v_r = vs1 * 1.1
        # Definition of max forward gravity center position
        x_cg = x_cg_aft - cg_range * wing_mac
        # Definition of horizontal tail global position
        x_ht = x_wing_aero_center + lp_ht
        # Calculation of wheel factor
        flight_point = FlightPoint(
            mach=v_r / atm.speed_of_sound,
            altitude=0.0,
            engine_setting=EngineSetting.TAKEOFF,
            thrust_rate=takeoff_t_rate
        )
        propulsion_model.compute_flight_points(flight_point)
        thrust = float(flight_point.thrust)
        fact_wheel = (
                (x_lg - x_cg - z_eng * thrust / weight)
                / wing_mac * (vs0 / v_r) ** 2
        )  # FIXME: not clear if vs0 or vs1 should be used in formula
        # Compute aerodynamic coefficients for takeoff @ 0° aircraft angle
        cl0_takeoff = cl0_clean + cl_flaps_takeoff
        # Calculation of correction coefficient n_h and n_q            
        n_h = (x_ht - x_lg) / lp_ht * 0.9  # 0.9=(v_h/v_r)²: dynamic pressure reduction at tail (typical value)
        n_q = 1 + cl_alpha_ht / cl_ht_takeoff * _ANG_VEL * (x_ht - x_lg) / v_r
        # Calculation of volume coefficient based on Torenbeek formula
        coef_vol = (
                cl_max_takeoff / (n_h * n_q * cl_ht_takeoff)
                * (cm_takeoff / cl_max_takeoff - fact_wheel)
                + cl0_takeoff / cl_ht_takeoff * (x_lg - x_wing_aero_center) / wing_mac
        )
        # Calculation of equivalent area
        area_1 = coef_vol * wing_area * wing_mac / lp_ht

        # CASE2: LANDING ###############################################################################################
        # method extracted from Torenbeek 1982 p325

        # Calculation of take-off minimum speed
        weight = mlw * g
        vs0 = math.sqrt(weight / (0.5 * rho * wing_area * cl_max_landing))
        # Rotation speed requirement from FAR 23.73
        v_r = vs0 * 1.3
        # Calculation of wheel factor
        flight_point = FlightPoint(
            mach=v_r / atm.speed_of_sound, altitude=0.0, engine_setting=EngineSetting.IDLE,
            thrust_rate=0.1
        )  # FIXME: fixed thrust rate (should depend on wished descent rate)
        propulsion_model.compute_flight_points(flight_point)
        thrust = float(flight_point.thrust)
        fact_wheel = (
                (x_lg - x_cg - z_eng * thrust / weight)
                / wing_mac * (vs0 / v_r) ** 2
        )  # FIXME: not clear if vs0 or vs1 should be used in formula
        # Evaluate aircraft overall angle (aoa)
        cl0_landing = cl0_clean + cl_flaps_landing
        # Calculation of correction coefficient n_h and n_q            
        n_h = (x_ht - x_lg) / lp_ht * 0.9  # 0.9=(v_htp/v_r)²: dynamic pressure reduction at tail (typical value)
        n_q = 1 + cl_alpha_ht / cl_ht_landing * _ANG_VEL * (x_ht - x_lg) / v_r
        # Calculation of volume coefficient based on Torenbeek formula
        coef_vol = (
                cl_max_landing / (n_h * n_q * cl_ht_landing)
                * (cm_landing / cl_max_landing - fact_wheel)
                + cl0_landing / cl_ht_landing * (x_lg - x_wing_aero_center) / wing_mac
        )
        # Calculation of equivalent area
        area_2 = coef_vol * wing_area * wing_mac / lp_ht

        outputs["data:geometry:horizontal_tail:area"] = max(area_1, area_2)


class _ComputeAeroCoeff(om.ExplicitComponent):
    """
    Adapts aero-coefficients (reference surface is tail area for cl_ht)
    """

    def initialize(self):
        self.options.declare("landing", default=False, types=bool)

    def setup(self):

        self.add_input("data:geometry:propulsion:count", val=np.nan)
        self.add_input("data:geometry:wing:area", val=np.nan, units="m**2")
        self.add_input("data:geometry:horizontal_tail:area", val=2.0, units="m**2")
        self.add_input("data:weight:aircraft:MLW", val=np.nan, units="kg")
        self.add_input("data:weight:aircraft:MTOW", val=np.nan, units="kg")
        nans_array = np.full(HT_POINT_COUNT, np.nan)
        self.add_input("data:aerodynamics:horizontal_tail:low_speed:alpha", val=nans_array, units="deg")
        self.add_input("data:aerodynamics:horizontal_tail:low_speed:CL", val=nans_array)
        self.add_input("data:aerodynamics:wing:low_speed:alpha", val=nans_array, units="deg")
        self.add_input("data:aerodynamics:wing:low_speed:CM", val=nans_array)
        self.add_input("data:aerodynamics:horizontal_tail:low_speed:CL_alpha", val=np.nan, units="rad**-1")
        self.add_input("data:aerodynamics:elevator:low_speed:CL_alpha", val=np.nan, units="rad**-1")
        self.add_input("data:aerodynamics:aircraft:landing:CL_max", val=np.nan)
        self.add_input("data:aerodynamics:wing:low_speed:CL_max_clean", val=np.nan)
        self.add_input("data:aerodynamics:aircraft:low_speed:CL0_clean", val=np.nan)
        self.add_input("data:aerodynamics:flaps:landing:CL", val=np.nan)
        self.add_input("data:aerodynamics:flaps:takeoff:CL", val=np.nan)
        self.add_input("data:aerodynamics:aircraft:low_speed:CL_alpha", val=np.nan, units="rad**-1")
        self.add_input("data:mission:sizing:landing:elevator_angle", val=np.nan, units="rad")
        self.add_input("data:mission:sizing:takeoff:elevator_angle", val=np.nan, units="rad")
        self.add_output("cl_ht")
        self.add_output("cm_wing")
        self.add_output("cl_alpha_ht")

        self.declare_partials("*", "*", method="fd")

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):

        n_engines = inputs["data:geometry:propulsion:count"]
        wing_area = inputs["data:geometry:wing:area"]
        ht_area = inputs["data:geometry:horizontal_tail:area"]
        mlw = inputs["data:weight:aircraft:MLW"]
        mtow = inputs["data:weight:aircraft:MTOW"]
        alpha_ht_interp = inputs["data:aerodynamics:horizontal_tail:low_speed:alpha"]
        cl_ht_interp = inputs["data:aerodynamics:horizontal_tail:low_speed:CL"]
        alpha_wing_interp = inputs["data:aerodynamics:wing:low_speed:alpha"]
        cm_wing_interp = inputs["data:aerodynamics:wing:low_speed:CM"]
        cl_alpha_ht = inputs["data:aerodynamics:horizontal_tail:low_speed:CL_alpha"]
        cl_alpha_elev = inputs["data:aerodynamics:elevator:low_speed:CL_alpha"]
        cl_max_landing = inputs["data:aerodynamics:aircraft:landing:CL_max"]
        cl_max_clean = inputs["data:aerodynamics:wing:low_speed:CL_max_clean"]
        cl0_clean = inputs["data:aerodynamics:aircraft:low_speed:CL0_clean"]
        cl_flaps_landing = inputs["data:aerodynamics:flaps:landing:CL"]
        cl_flaps_takeoff = inputs["data:aerodynamics:flaps:takeoff:CL"]
        cl_alpha_wing = inputs["data:aerodynamics:aircraft:low_speed:CL_alpha"]

        # Conditions for calculation
        atm = Atmosphere(0.0)
        rho = atm.density

        # Calculate elevator max. additional lift
        if self.options["landing"]:
            elev_angle = inputs["data:mission:sizing:landing:elevator_angle"]
        else:
            elev_angle = inputs["data:mission:sizing:takeoff:elevator_angle"]
        cl_elev = cl_alpha_elev * elev_angle
        # Define alpha angle depending on phase
        if self.options["landing"]:
            # Calculation of take-off minimum speed
            weight = mlw * g
            vs0 = math.sqrt(weight / (0.5 * rho * wing_area * cl_max_landing))
            # Rotation speed correction
            v_r = vs0 * 1.3
            # Evaluate aircraft overall angle (aoa)
            cl0_landing = cl0_clean + cl_flaps_landing
            cl_landing = weight / (0.5 * rho * v_r ** 2 * wing_area)
            alpha = (cl_landing - cl0_landing) / cl_alpha_wing * 180 / math.pi
        else:
            # Calculation of take-off minimum speed
            weight = mtow * g
            vs1 = math.sqrt(weight / (0.5 * rho * wing_area * cl_max_clean))
            # Rotation speed requirement from FAR 23.51 (depends on number of engines)
            if n_engines == 1:
                v_r = vs1 * 1.0
            else:
                v_r = vs1 * 1.1
            # Evaluate aircraft overall angle (aoa)
            cl0_takeoff = cl0_clean + cl_flaps_takeoff
            cl_takeoff = weight / (0.5 * rho * v_r ** 2 * wing_area)
            alpha = (cl_takeoff - cl0_takeoff) / cl_alpha_wing * 180 / math.pi
        # Interpolate cl/cm and define with ht reference surface
        cl_ht = (
                (self._extrapolate(alpha, alpha_ht_interp, cl_ht_interp) + cl_elev)
                * wing_area / ht_area
        )
        # FIXME: are we sure it is cm_wing and not cm_htp passed to wing?
        cm_wing = self._extrapolate(alpha, alpha_wing_interp, cm_wing_interp)
        # Define Cl_alpha with ht reference surface
        cl_alpha_ht = cl_alpha_ht * wing_area / ht_area

        outputs["cl_ht"] = cl_ht
        outputs["cm_wing"] = cm_wing
        outputs["cl_alpha_ht"] = cl_alpha_ht

    @staticmethod
    def _extrapolate(x, xp, yp) -> float:
        """
        Extrapolate linearly out of range x-value
        """
        if (x >= xp[0]) and (x <= xp[-1]):
            result = float(np.interp(x, xp, yp))
        elif x < xp[0]:
            result = float(yp[0] + (x - xp[0]) * (yp[1] - yp[0]) / (xp[1] - xp[0]))
        else:
            result = float(yp[-1] + (x - xp[-1]) * (yp[-1] - yp[-2]) / (xp[-1] - xp[-2]))

        if result is None:
            result = np.array([np.nan])

        return result
