"""
    Estimation of total aircraft wet area
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


class ComputeTotalArea(ExplicitComponent):
    # TODO: Document equations. Cite sources
    """ Total aircraft wet area estimation """

    def setup(self):
        self.add_input("data:geometry:wing:wet_area", val=np.nan, units="m**2")
        self.add_input("data:geometry:fuselage:wet_area", val=np.nan, units="m**2")
        self.add_input("data:geometry:horizontal_tail:wet_area", val=np.nan, units="m**2")
        self.add_input("data:geometry:vertical_tail:wet_area", val=np.nan, units="m**2")
        self.add_input("data:geometry:propulsion:nacelle:wet_area", val=np.nan, units="m**2")
        self.add_input("data:geometry:propulsion:engine:count", val=np.nan)

        self.add_output("data:geometry:aircraft:wet_area", units="m**2")

        self.declare_partials("data:geometry:aircraft:wet_area", "*", method="fd")

    def compute(self, inputs, outputs):
        wet_area_wing = inputs["data:geometry:wing:wet_area"]
        wet_area_fus = inputs["data:geometry:fuselage:wet_area"]
        wet_area_ht = inputs["data:geometry:horizontal_tail:wet_area"]
        wet_area_vt = inputs["data:geometry:vertical_tail:wet_area"]
        wet_area_nac = inputs["data:geometry:propulsion:nacelle:wet_area"]
        n_engines = inputs["data:geometry:propulsion:engine:count"]

        wet_area_total = (
            wet_area_wing
            + wet_area_fus
            + wet_area_ht
            + wet_area_vt
            + n_engines * wet_area_nac
        )

        outputs["data:geometry:aircraft:wet_area"] = wet_area_total
