"""
Estimation of centers of gravity
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

from .compute_cg_control_surfaces import ComputeControlSurfacesCG
from .compute_cg_engine import ComputeEngineCG
from .compute_cg_ht import ComputeHTcg
from .compute_cg_loadcase import ComputeCGLoadCase
from .compute_cg_others import ComputeOthersCG
from .compute_cg_ratio_aft import ComputeCGRatioAft
from .compute_cg_tanks import ComputeTanksCG
from .compute_cg_wing import ComputeWingCG
from .compute_cg_vt import ComputeVTcg
from .compute_global_cg import ComputeGlobalCG
from .compute_max_cg_ratio import ComputeMaxCGratio
from .update_mlg import UpdateMLG
