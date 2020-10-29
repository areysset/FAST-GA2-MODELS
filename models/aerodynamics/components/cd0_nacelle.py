"""
    FAST - Copyright (c) 2016 ONERA ISAE
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

import math

import numpy as np
from openmdao.core.explicitcomponent import ExplicitComponent


class Cd0Nacelle(ExplicitComponent):
    def initialize(self):
        self.options.declare("low_speed_aero", default=False, types=bool)
        
    def setup(self):
        
        self.add_input("data:geometry:propulsion:engine:count", val=np.nan)
        self.add_input("data:geometry:wing:MAC:length", val=np.nan, units="m")
        self.add_input("data:geometry:propulsion:nacelle:height", val=np.nan, units="m")
        self.add_input("data:geometry:propulsion:nacelle:width", val=np.nan, units="m")
        self.add_input("data:geometry:propulsion:nacelle:length", val=np.nan, units="m")
        self.add_input("data:geometry:propulsion:nacelle:wet_area", val=np.nan, units="m**2")
        self.add_input("data:geometry:wing:area", val=np.nan, units="m**2")
        if self.options["low_speed_aero"]:
            self.add_input("data:aerodynamics:low_speed:mach", val=np.nan)
            self.add_input("data:aerodynamics:low_speed:unit_reynolds", val=np.nan)
            self.add_output("data:aerodynamics:nacelles:low_speed:CD0")
        else:
            self.add_input("data:aerodynamics:cruise:mach", val=np.nan)
            self.add_input("data:aerodynamics:cruise:unit_reynolds", val=np.nan)
            self.add_output("data:aerodynamics:nacelles:cruise:CD0")

        self.declare_partials(
                "*",
                [
                        "data:geometry:wing:MAC:length",
                        "data:geometry:propulsion:nacelle:height",
                        "data:geometry:propulsion:nacelle:width",
                        "data:geometry:propulsion:nacelle:length",
                        "data:geometry:propulsion:nacelle:wet_area",
                        "data:geometry:wing:area",
                ],
                method="fd",
        )

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):

        try:
            engine_number = int(float(inputs["data:geometry:propulsion:engine:count"]))
        except ValueError:
            engine_number = 0
        l0_wing = inputs["data:geometry:wing:MAC:length"]
        nac_height = inputs["data:geometry:propulsion:nacelle:height"]
        nac_width = inputs["data:geometry:propulsion:nacelle:width"]
        nac_length = inputs["data:geometry:propulsion:nacelle:length"]
        wet_area_nac = inputs["data:geometry:propulsion:nacelle:wet_area"]
        wing_area = inputs["data:geometry:wing:area"]
        if self.options["low_speed_aero"]:
            mach = inputs["data:aerodynamics:low_speed:mach"]
            unit_reynolds = inputs["data:aerodynamics:low_speed:unit_reynolds"]
        else:
            mach = inputs["data:aerodynamics:cruise:mach"]
            unit_reynolds = inputs["data:aerodynamics:cruise:unit_reynolds"]
        
        # Local Reynolds:
        reynolds = unit_reynolds*nac_length
        # Roskam method for wing-nacelle interaction factor (vol 6 page 3.62)
        cf_nac = 0.455 / ((1 + 0.144 * mach ** 2)**0.65 * (math.log10(reynolds)) ** 2.58)  # 100% turbulent
        f = nac_length/math.sqrt(4*nac_height*nac_width/math.pi) 
        ff_nac = 1 + 0.35/f  # Raymer (seen in Gudmunsson)
        if_nac = 0.036 * nac_width * l0_wing/wing_area * 0.04
        engine_in_fus = engine_number % 2
        
        cd0 = (cf_nac * ff_nac * wet_area_nac / wing_area + if_nac) \
            * (engine_number - engine_in_fus)

        if self.options["low_speed_aero"]:
            outputs["data:aerodynamics:nacelles:low_speed:CD0"] = cd0
        else:
            outputs["data:aerodynamics:nacelles:cruise:CD0"] = cd0
