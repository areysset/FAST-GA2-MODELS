"""
Test module for geometry functions of cg components
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

# pylint: disable=redefined-outer-name  # needed for pytest fixtures
import os.path as pth
import openmdao.api as om

import pytest
from fastoad.io import VariableIO

from tests.testing_utilities import run_system

from ..cg import CG
from ..cg_components.a_airframe import ComputeWingCG, ComputeFuselageCG, ComputeTailCG, ComputeFlightControlCG, ComputeLandingGearCG
from ..cg_components.b_propulsion import ComputeEngineCG, ComputeFuelLinesCG, ComputeTankCG
from ..cg_components.c_systems import ComputePowerSystemsCG, ComputeLifeSupportCG, ComputeNavigationSystemsCG
from ..cg_components.d_furniture import ComputePassengerSeatsCG
from ..cg_components.payload import ComputePayloadCG
from ..cg_components.loadcase import ComputeCGLoadCase
from ..cg_components.ratio_aft import ComputeCGRatioAft
from ..cg_components.max_cg_ratio import ComputeMaxCGratio
from ..cg_components.update_mlg import UpdateMLG

XML_FILE = "beechcraft_76.xml"

def get_indep_var_comp(var_names):
    """ Reads required input data and returns an IndepVarcomp() instance"""
    reader = VariableIO(pth.join(pth.dirname(__file__), "data", XML_FILE))
    reader.path_separator = ":"
    ivc = reader.read(only=var_names).to_ivc()
    return ivc


def list_inputs(group):
    """ Reads input variables from a group and return as a list (run model with 0 value can lead to raise configuration
    errors in models)"""
    prob = om.Problem(model=group)
    prob.setup()
    prob.run_model()
    data = prob.model.list_inputs(out_stream=None)
    list_names = []
    for idx in range(len(data)):
        variable_name = data[idx][0].split('.')
        list_names.append(variable_name[len(variable_name) - 1])
    return list(dict.fromkeys(list_names))


def test_compute_cg_wing():
    """ Tests computation of wing center of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeWingCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeWingCG(), ivc)
    x_cg_a1 = problem.get_val("data:weight:airframe:wing:CG:x", units="m")
    assert x_cg_a1 == pytest.approx(0.39, abs=1e-2)


def test_compute_cg_fuselage():
    """ Tests computation of fuselage center of gravity """

    # Input list from model (not generated because of assertion error for bad propulsion layout values)
    input_list = [
        "data:geometry:propulsion:layout",
        "data:geometry:fuselage:length",
        "data:geometry:propulsion:propeller:depth",
    ]

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeFuselageCG(), ivc)
    x_cg_a2 = problem.get_val("data:weight:airframe:fuselage:CG:x", units="m")
    assert x_cg_a2 == pytest.approx(3.99, abs=1e-2)


def test_compute_cg_tail():
    """ Tests computation of tail center(s) of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeTailCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeTailCG(), ivc)
    x_cg_a31 = problem.get_val("data:weight:airframe:horizontal_tail:CG:x", units="m")
    assert x_cg_a31 == pytest.approx(7.91, abs=1e-2)
    x_cg_a32 = problem.get_val("data:weight:airframe:vertical_tail:CG:x", units="m")
    assert x_cg_a32 == pytest.approx(8.05, abs=1e-2)


def test_compute_cg_flight_control():
    """ Tests computation of flight control center of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeFlightControlCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeFlightControlCG(), ivc)
    x_cg_a4 = problem.get_val("data:weight:airframe:flight_controls:CG:x", units="m")
    assert x_cg_a4 == pytest.approx(4.61, abs=1e-2)


def test_compute_cg_landing_gear():
    """ Tests computation of landing gear center(s) of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeLandingGearCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeLandingGearCG(), ivc)
    x_cg_a52 = problem.get_val("data:weight:airframe:landing_gear:front:CG:x", units="m")
    assert x_cg_a52 == pytest.approx(1.71, abs=1e-2)


def test_compute_cg_engine():
    """ Tests computation of engine(s) center of gravity """

    # Input list from model (not generated because of assertion error for bad propulsion layout values)
    input_list = [
        "data:geometry:propulsion:layout",
        "data:geometry:wing:MAC:leading_edge:x:local",
        "data:geometry:wing:MAC:length",
        "data:geometry:wing:root:y",
        "data:geometry:wing:root:chord",
        "data:geometry:wing:tip:leading_edge:x:local",
        "data:geometry:wing:tip:y",
        "data:geometry:wing:tip:chord",
        "data:geometry:wing:MAC:at25percent:x",
        "data:geometry:propulsion:nacelle:length",
        "data:geometry:propulsion:nacelle:y",
    ]

    # Research independent input value in .xml file
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeEngineCG(), ivc)
    x_cg_b1 = problem.get_val("data:weight:propulsion:engine:CG:x", units="m")
    assert x_cg_b1 == pytest.approx(2.7, abs=1e-2)


def test_compute_cg_fuel_lines():
    """ Tests fuel lines center of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeFuelLinesCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file
    ivc = get_indep_var_comp(input_list)
    ivc.add_output("data:weight:propulsion:engine:CG:x", 2.7, units="m")

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeFuelLinesCG(), ivc)
    x_cg_b2 = problem.get_val("data:weight:propulsion:fuel_lines:CG:x", units="m")
    assert x_cg_b2 == pytest.approx(2.7, abs=1e-2)


def test_compute_cg_tank():
    """ Tests tank center of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeTankCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeTankCG(), ivc)
    x_cg_b3 = problem.get_val("data:weight:propulsion:tank:CG:x", units="m")
    assert x_cg_b3 == pytest.approx(3.83, abs=1e-2)


def test_compute_cg_power_systems():
    """ Tests computation of power systems center of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputePowerSystemsCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)
    ivc.add_output("data:weight:propulsion:engine:CG:x", 2.7, units="m")

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputePowerSystemsCG(), ivc)
    x_cg_c12 = problem.get_val("data:weight:systems:power:electric_systems:CG:x", units="m")
    assert x_cg_c12 == pytest.approx(0.0, abs=1e-2)
    x_cg_c13 = problem.get_val("data:weight:systems:power:hydraulic_systems:CG:x", units="m")
    assert x_cg_c13 == pytest.approx(0.0, abs=1e-2)


def test_compute_cg_life_support_systems():
    """ Tests computation of life support systems center of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeLifeSupportCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeLifeSupportCG(), ivc)
    x_cg_c22 = problem.get_val("data:weight:systems:life_support:air_conditioning:CG:x", units="m")
    assert x_cg_c22 == pytest.approx(0.0, abs=1e-2)


def test_compute_cg_navigation_systems():
    """ Tests computation of navigation systems center of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeNavigationSystemsCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeNavigationSystemsCG(), ivc)
    x_cg_c3 = problem.get_val("data:weight:systems:navigation:CG:x", units="m")
    assert x_cg_c3 == pytest.approx(2.97, abs=1e-2)


def test_compute_cg_passenger_seats():
    """ Tests computation of passenger seats center of gravity """

    # Input list from model (not generated because of NaN convertion problem to integer)
    input_list = [
        "data:geometry:cabin:NPAX",
        "data:geometry:fuselage:front_length",
        "data:geometry:cabin:seats:passenger:count_by_row",
        "data:geometry:cabin:seats:pilot:length",
        "data:geometry:cabin:seats:passenger:length",
    ]

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputePassengerSeatsCG(), ivc)
    x_cg_d2 = problem.get_val("data:weight:furniture:passenger_seats:CG:x", units="m")
    assert x_cg_d2 == pytest.approx(4.13, abs=1e-1)


def test_compute_cg_payload():
    """ Tests computation of payload center(s) of gravity """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputePayloadCG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)
    ivc.add_output("data:weight:furniture:passenger_seats:CG:x", 4.13, units="m")

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputePayloadCG(), ivc)
    x_cg_pl = problem.get_val("data:weight:payload:PAX:CG:x", units="m")
    assert x_cg_pl == pytest.approx(4.13, abs=1e-1)
    x_cg_rear_fret = problem.get_val("data:weight:payload:rear_fret:CG:x", units="m")
    assert x_cg_rear_fret == pytest.approx(5.68, abs=1e-2)
    x_cg_front_fret = problem.get_val("data:weight:payload:front_fret:CG:x", units="m")
    assert x_cg_front_fret == pytest.approx(0.0, abs=1e-2)


def test_compute_cg_ratio_aft():
    """ Tests computation of center of gravity with aft estimation """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeCGRatioAft(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)
    ivc.add_output("data:weight:airframe:wing:CG:x", 0.39)
    ivc.add_output("data:weight:airframe:fuselage:CG:x", 3.99)
    ivc.add_output("data:weight:airframe:horizontal_tail:CG:x", 7.91)
    ivc.add_output("data:weight:airframe:vertical_tail:CG:x", 8.05)
    ivc.add_output("data:weight:airframe:flight_controls:CG:x", 4.61)
    ivc.add_output("data:weight:airframe:landing_gear:main:CG:x", 3.62)
    ivc.add_output("data:weight:airframe:landing_gear:front:CG:x", 1.71)
    ivc.add_output("data:weight:propulsion:engine:CG:x", 2.7)
    ivc.add_output("data:weight:propulsion:fuel_lines:CG:x", 2.7)
    ivc.add_output("data:weight:systems:power:electric_systems:CG:x", 0.0)
    ivc.add_output("data:weight:systems:power:hydraulic_systems:CG:x", 0.0)
    ivc.add_output("data:weight:systems:life_support:air_conditioning:CG:x", 0.0)
    ivc.add_output("data:weight:systems:navigation:CG:x", 2.97)
    ivc.add_output("data:weight:furniture:passenger_seats:CG:x", 4.13)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeCGRatioAft(), ivc)
    empty_mass = problem["data:weight:aircraft_empty:mass"]
    assert empty_mass == pytest.approx(950.47, abs=1e-2)
    cg_x = problem["data:weight:aircraft_empty:CG:x"]
    assert cg_x == pytest.approx(2.66, abs=1e-2)
    cg_mac_pos = problem["data:weight:aircraft:empty:CG:MAC_position"]
    assert cg_mac_pos == pytest.approx(-0.26, abs=1e-2)


def test_compute_cg_loadcase():
    """ Tests computation of center of gravity for all load case conf. """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", ComputeCGLoadCase(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)
    ivc.add_output("data:weight:payload:PAX:CG:x", 4.13)
    ivc.add_output("data:weight:payload:rear_fret:CG:x", 5.68)
    ivc.add_output("data:weight:payload:front_fret:CG:x", 0.0)
    ivc.add_output("data:weight:aircraft_empty:CG:x", 2.66)
    ivc.add_output("data:weight:aircraft_empty:mass", 950.47)
    ivc.add_output("data:weight:propulsion:tank:CG:x", 3.83)

    # Run problem and check obtained value(s) is/(are) correct
    for case in range(1,7):
        problem = run_system(ComputeCGLoadCase(load_case=case), ivc)
        cg_ratio_lc = problem.get_val("data:weight:aircraft:load_case_"+str(case)+":CG:MAC_position")
        if case == 1:
            assert cg_ratio_lc == pytest.approx(0.14, abs=1e-2)
        elif case == 2:
            assert cg_ratio_lc == pytest.approx(0.20, abs=1e-2)
        elif case == 3:
            assert cg_ratio_lc == pytest.approx(0.08, abs=1e-2)
        elif case == 4:
            assert cg_ratio_lc == pytest.approx(0.15, abs=1e-2)
        elif case == 5:
            assert cg_ratio_lc == pytest.approx(0.06, abs=1e-2)
        elif case == 6:
            assert cg_ratio_lc == pytest.approx(0.09, abs=1e-2)
        else:
            pass


def test_compute_max_cg_ratio():
    """ Tests computation of maximum center of gravity ratio """

    # Define the independent input values that should be filled if basic function is choosen
    ivc = om.IndepVarComp()
    ivc.add_output("data:weight:aircraft:empty:CG:MAC_position", -0.26)
    ivc.add_output("data:weight:aircraft:load_case_1:CG:MAC_position", 0.14)
    ivc.add_output("data:weight:aircraft:load_case_2:CG:MAC_position", 0.20)
    ivc.add_output("data:weight:aircraft:load_case_3:CG:MAC_position", 0.08)
    ivc.add_output("data:weight:aircraft:load_case_4:CG:MAC_position", 0.15)
    ivc.add_output("data:weight:aircraft:load_case_5:CG:MAC_position", 0.06)
    ivc.add_output("data:weight:aircraft:load_case_6:CG:MAC_position", 0.09)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(ComputeMaxCGratio(), ivc)
    cg_ratio = problem.get_val("data:weight:aircraft:CG:aft:MAC_position")
    assert cg_ratio == pytest.approx(0.25, abs=1e-2)


def test_update_mlg():
    """ Tests computation of MLG update """

    # Generate input list from model
    group = om.Group()
    group.add_subsystem("my_model", UpdateMLG(), promotes=["*"])
    input_list = list_inputs(group)

    # Research independent input value in .xml file  and add values calculated from other modules
    ivc = get_indep_var_comp(input_list)
    ivc.add_output("data:weight:aircraft:CG:aft:MAC_position", 0.25)
    ivc.add_output("data:weight:airframe:landing_gear:front:CG:x", 1.71)

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(UpdateMLG(), ivc)
    cg_a51 = problem.get_val("data:weight:airframe:landing_gear:main:CG:x", units="m")
    assert cg_a51 == pytest.approx(4.19, abs=1e-2)


def test_compute_aircraft_cg():
    """ Tests computation of static margin """

    # with data from file
    reader = VariableIO(pth.join(pth.dirname(__file__), "data", XML_FILE))
    reader.path_separator = ":"
    input_vars = reader.read().to_ivc()

    # Run problem and check obtained value(s) is/(are) correct
    problem = run_system(CG(), input_vars)
    cg_global = problem.get_val("data:weight:aircraft:CG:aft:x", units="m")
    assert cg_global == pytest.approx(3.46, abs=1e-1)
    cg_ratio = problem.get_val("data:weight:aircraft:CG:aft:MAC_position")
    assert cg_ratio == pytest.approx(0.26, abs=1e-2)