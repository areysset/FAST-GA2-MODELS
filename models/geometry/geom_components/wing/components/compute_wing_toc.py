"""
    Estimation of wing ToC
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
import openmdao.api as om


# TODO: computes relative thickness and generates profiles --> decompose
class ComputeWingToc(om.ExplicitComponent):
    # TODO: Document hypothesis. Cite sources
    """ Wing ToC estimation """

    def setup(self):
        
        self.add_input("data:geometry:wing:thickness_ratio", val=np.nan)
        
        self.add_output("data:geometry:wing:root:thickness_ratio")
        self.add_output("data:geometry:wing:kink:thickness_ratio")
        self.add_output("data:geometry:wing:tip:thickness_ratio")
        
        self.declare_partials("*", "*", method="fd")
        
    def compute(self, inputs, outputs):
        
        el_aero = inputs["data:geometry:wing:thickness_ratio"]
        
        el_emp = 1.24 * el_aero
        el_break = 0.94 * el_aero
        el_ext = 0.86 * el_aero
        
        outputs["data:geometry:wing:root:thickness_ratio"] = el_emp
        outputs["data:geometry:wing:kink:thickness_ratio"] = el_break
        outputs["data:geometry:wing:tip:thickness_ratio"] = el_ext
        
        
