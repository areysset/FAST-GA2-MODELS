"""
    Estimation of geometry of horizontal tail
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

import openmdao.api as om

from fastoad.models.geometry.geom_components.ht.components import ComputeHTChord
from fastoad.models.aerodynamics.components.compute_ht_cl_alpha import ComputeHTClalpha
from fastoad.models.geometry.geom_components.ht.components import ComputeHTDistance
from fastoad.models.geometry.geom_components.ht.components import ComputeHTMAC
from fastoad.models.geometry.geom_components.ht.components import ComputeHTSweep


class ComputeHorizontalTailGeometry(om.Group):
    """ Horizontal tail geometry estimation """

    def setup(self):
        self.add_subsystem("ht_chord", ComputeHTChord(), promotes=["*"])
        self.add_subsystem("ht_aspect_ratio", ComputeHTDistance(), promotes=["*"])
        self.add_subsystem("ht_mac", ComputeHTMAC(), promotes=["*"])
        self.add_subsystem("ht_sweep", ComputeHTSweep(), promotes=["*"])
        self.add_subsystem("ht_cl_alpha", ComputeHTClalpha(), promotes=["*"])