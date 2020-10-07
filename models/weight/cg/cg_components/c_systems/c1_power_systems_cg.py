"""
    Estimation of power systems center(s) of gravity
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
from openmdao.core.explicitcomponent import ExplicitComponent


class ComputePowerSystemsCG(ExplicitComponent):
    # TODO: Document equations. Cite sources
    """ Power systems center(s) of gravity estimation """

    def setup(self):

        self.add_input("data:geometry:fuselage:front_length", val=np.nan, units="m")

        self.add_output("data:weight:systems:power:electric_systems:CG:x", units="m")
        self.add_output("data:weight:systems:power:hydraulic_systems:CG:x", units="m")
        
        self.declare_partials("*", "*", method="fd")

    def compute(self, inputs, outputs):

        lav = inputs["data:geometry:fuselage:front_length"]

        # Electric system gravity center
        x_cg_c12 = 0 * lav
        # Hydraulic system gravity center
        x_cg_c13 = 0 * lav

        outputs["data:weight:systems:power:electric_systems:CG:x"] = x_cg_c12
        outputs["data:weight:systems:power:hydraulic_systems:CG:x"] = x_cg_c13