"""
    Estimation of wing lift coefficient using OPENVSP
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

import multiprocessing
import os
import os.path as pth
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory

import math
import numpy as np
from fastoad.utils.physics import Atmosphere
from fastoad.utils.resource_management.copy import copy_resource, copy_resource_folder
from importlib_resources import path
from openmdao.components.external_code_comp import ExternalCodeComp
from openmdao.utils.file_wrap import InputFileGenerator

from . import resources
from . import openvsp3201

OPTION_OPENVSP_EXE_PATH = "openvsp_exe_path"

_INPUT_SCRIPT_FILE_NAME = "wing_openvsp.vspscript"
_INPUT_AERO_FILE_NAME = "wing_openvsp_DegenGeom"
_INPUT_AOAList = [0.0, 5.0] # !!!: arround 0° calculation
_AIRFOIL_0_FILE_NAME = "naca23012.af"
_AIRFOIL_1_FILE_NAME = "naca23012.af"
_AIRFOIL_2_FILE_NAME = "naca23012.af"
VSPSCRIPT_EXE_NAME = "vspscript.exe"
VSPAERO_EXE_NAME = "vspaero.exe"

class ComputeWingCLALPHAopenvsp(ExternalCodeComp):

    def initialize(self):
        self.options.declare("low_speed_aero", default=False, types=bool)
        self.options.declare(OPTION_OPENVSP_EXE_PATH, default="", types=str, allow_none=True)
        
    def setup(self):
        
        self.add_input("data:geometry:wing:MAC:leading_edge:x:local", val=np.nan, units="m")
        self.add_input("data:geometry:wing:MAC:length", val=np.nan, units="m")
        self.add_input("data:geometry:fuselage:maximum_width", val=np.nan, units="m")
        self.add_input("data:geometry:wing:root:y", val=np.nan, units="m")
        self.add_input("data:geometry:wing:root:chord", val=np.nan, units="m")
        self.add_input("data:geometry:wing:tip:y", val=np.nan, units="m")
        self.add_input("data:geometry:wing:tip:chord", val=np.nan, units="m")
        self.add_input("data:geometry:wing:sweep_0", val=np.nan, units="deg")
        self.add_input("data:geometry:wing:MAC:at25percent:x", val=np.nan, units="m")
        self.add_input("data:geometry:wing:area", val=np.nan, units="m**2")
        self.add_input("data:geometry:wing:span", val=np.nan, units="m")
        self.add_input("data:geometry:fuselage:maximum_height", val=np.nan, units="m")

        if self.options["low_speed_aero"]:
            self.add_input("data:aerodynamics:low_speed:mach", val=np.nan)
            self.add_output("data:aerodynamics:aircraft:low_speed:CL0_clean")
            self.add_output("data:aerodynamics:aircraft:low_speed:CL_alpha")
        else:
            self.add_input("data:aerodynamics:cruise:mach", val=np.nan)
            self.add_input("data:mission:sizing:cruise:altitude", val=np.nan, units='ft')
            self.add_output("data:aerodynamics:aircraft:cruise:CL0_clean")
            self.add_output("data:aerodynamics:aircraft:cruise:CL_alpha")
        
        self.declare_partials("*", "*", method="fd")        
    
    def compute(self, inputs, outputs):
        
        # Get inputs (and calculate missing ones)
        x0_wing = inputs["data:geometry:wing:MAC:leading_edge:x:local"]
        l0_wing = inputs["data:geometry:wing:MAC:length"]
        width_max = inputs["data:geometry:fuselage:maximum_width"]
        y1_wing = width_max/2.0
        y2_wing = inputs["data:geometry:wing:root:y"]
        l2_wing = inputs["data:geometry:wing:root:chord"]
        y4_wing = inputs["data:geometry:wing:tip:y"]
        l4_wing = inputs["data:geometry:wing:tip:chord"]
        sweep_0_wing = inputs["data:geometry:wing:sweep_0"]
        fa_length = inputs["data:geometry:wing:MAC:at25percent:x"]
        Sref_wing = inputs['data:geometry:wing:area']
        span_wing = inputs['data:geometry:wing:span']
        height_max = inputs["data:geometry:fuselage:maximum_height"]
        if self.options["low_speed_aero"]:
            altitude = 0.0
            atm = Atmosphere(altitude)
            mach = inputs["data:aerodynamics:low_speed:mach"]
        else:
            altitude = inputs["data:mission:sizing:cruise:altitude"]
            atm = Atmosphere(altitude)
            mach = inputs["data:aerodynamics:cruise:mach"]
        
        # Initial parameters calculation
        x_wing = fa_length-x0_wing-0.25*l0_wing
        z_wing = -(height_max - 0.12*l2_wing)*0.5
        span2_wing = y4_wing - y2_wing
        viscosity = atm.kinematic_viscosity
        rho = atm.density
        V_inf = max(atm.speed_of_sound * mach, 0.01) # avoid V=0 m/s crashes
        reynolds = V_inf * l0_wing / viscosity
        
        # OPENVSP-SCRIPT: Geometry generation ######################################################
        
        # I/O files --------------------------------------------------------------------------------
        tmp_directory = self._create_tmp_directory()
        if self.options[OPTION_OPENVSP_EXE_PATH]:
            target_directory = pth.abspath(self.options[OPTION_OPENVSP_EXE_PATH])
        else:
            target_directory = tmp_directory.name
        input_file_list = [pth.join(target_directory, _INPUT_SCRIPT_FILE_NAME)]
        input_file_list.append(pth.join(target_directory, _AIRFOIL_0_FILE_NAME))
        input_file_list.append(pth.join(target_directory, _AIRFOIL_1_FILE_NAME))
        input_file_list.append(pth.join(target_directory, _AIRFOIL_2_FILE_NAME))
        tmp_result_file_path = pth.join(target_directory, _INPUT_AERO_FILE_NAME + '.csv')
        output_file_list = [tmp_result_file_path]
        self.options["external_input_files"] = input_file_list
        self.options["external_output_files"] = output_file_list
        
        # Pre-processing (populating temp directory and generate batch file) -----------------------
        # Copy resource in temp directory if needed
        if not(self.options[OPTION_OPENVSP_EXE_PATH]):
            copy_resource_folder(openvsp3201.__path__[0], target_directory) # FIXME: look if old version is working
            copy_resource(resources, _AIRFOIL_0_FILE_NAME, target_directory)
            copy_resource(resources, _AIRFOIL_1_FILE_NAME, target_directory)
            copy_resource(resources, _AIRFOIL_2_FILE_NAME, target_directory)
        # Create corresponding .bat file
        self.options["command"] = [pth.join(target_directory, 'vspscript.bat')]
        self.options['allowed_return_codes'] = [0]
        command = pth.join(target_directory, VSPSCRIPT_EXE_NAME) + ' -script ' + pth.join(target_directory, pth.splitext(_INPUT_AERO_FILE_NAME)[0] + '.vspscript')
        batch_file = open(self.options["command"][0], "w+")
        batch_file.write(command)
        batch_file.close()
        
        # standard SCRIPT input file ---------------------------------------------------------------
        parser = InputFileGenerator()
        with path(resources, _INPUT_SCRIPT_FILE_NAME) as input_template_path:
            parser.set_template_file(input_template_path)
            parser.set_generated_file(input_file_list[0])
            parser.mark_anchor("x_wing")
            parser.transfer_var(float(x_wing), 0, 5)
            parser.mark_anchor("z_wing")
            parser.transfer_var(float(z_wing), 0, 5)
            parser.mark_anchor("y1_wing")
            parser.transfer_var(float(y1_wing), 0, 5)
            for i in range(3):
                parser.mark_anchor("l2_wing")
                parser.transfer_var(float(l2_wing), 0, 5)
            parser.reset_anchor()
            parser.mark_anchor("span2_wing")
            parser.transfer_var(float(span2_wing), 0, 5)
            parser.mark_anchor("l4_wing")
            parser.transfer_var(float(l4_wing), 0, 5)
            parser.mark_anchor("sweep_0_wing")
            parser.transfer_var(float(sweep_0_wing), 0, 5)
            parser.mark_anchor("airfoil_0_file")
            parser.transfer_var(self._rewrite_path(input_file_list[1]), 0, 3)
            parser.mark_anchor("airfoil_1_file")
            parser.transfer_var(self._rewrite_path(input_file_list[2]), 0, 3)
            parser.mark_anchor("airfoil_2_file")
            parser.transfer_var(self._rewrite_path(input_file_list[3]), 0, 3)
            parser.mark_anchor("csv_file")
            parser.transfer_var(self._rewrite_path(tmp_result_file_path), 0, 3)
            parser.generate()
            
        # Run SCRIPT --------------------------------------------------------------------------------
        super().compute(inputs, outputs)
 
        # OPENVSP-AERO: aero calculation ############################################################
       
        # I/O files --------------------------------------------------------------------------------
        input_file_list = [tmp_result_file_path]
        output_file_list = []
        for idx in range(len(_INPUT_AOAList)):
            input_file_list.append(pth.join(target_directory, _INPUT_AERO_FILE_NAME) + str(idx) + '.vspaero')
            output_file_list.append(pth.join(target_directory, _INPUT_AERO_FILE_NAME) + str(idx) + '.polar')
        self.options["external_input_files"] = input_file_list
        self.options["external_output_files"] = output_file_list
        
        # Pre-processing (create batch file) -------------------------------------------------------
        self.options["command"] = [pth.join(target_directory, 'vspaero.bat')]
        batch_file = open(self.options["command"][0], "w+")
        for idx in range(len(_INPUT_AOAList)):
            command = pth.join(target_directory, VSPAERO_EXE_NAME) + ' ' + pth.join(target_directory, _INPUT_AERO_FILE_NAME + str(idx) + '\n')
            batch_file.write(command)
        batch_file.close()
        
        # standard AERO input file -----------------------------------------------------------------
        parser = InputFileGenerator()
        pair_core = 2**np.linspace(1, 10, 10)
        cpu_count = pair_core[np.max(np.where(pair_core<=multiprocessing.cpu_count()))]
        for idx in range(len(_INPUT_AOAList)):
            with path(resources, _INPUT_AERO_FILE_NAME + '.vspaero') as input_template_path:
                parser.set_template_file(input_template_path)
                parser.set_generated_file(input_file_list[idx])
                parser.mark_anchor("Sref")
                parser.transfer_var(float(Sref_wing), 0, 3)
                parser.mark_anchor("Cref")
                parser.transfer_var(float(l0_wing), 0, 3)
                parser.mark_anchor("Bref")
                parser.transfer_var(float(span_wing), 0, 3)
                parser.mark_anchor("X_cg")
                parser.transfer_var(float(fa_length), 0, 3)
                parser.mark_anchor("Mach")
                parser.transfer_var(float(mach), 0, 3)
                parser.mark_anchor("AOA")
                parser.transfer_var(float(_INPUT_AOAList[idx]), 0, 3)
                parser.mark_anchor("Vinf")
                parser.transfer_var(float(V_inf), 0, 3)
                parser.mark_anchor("Rho")
                parser.transfer_var(float(rho), 0, 3)
                parser.mark_anchor("ReCref")
                parser.transfer_var(float(reynolds), 0, 3)
                parser.mark_anchor("NumWakeNodes")
                parser.transfer_var(int(cpu_count), 0, 3)
                parser.generate()
        
        # Run AERO --------------------------------------------------------------------------------
        super().compute(inputs, outputs)
        
        # Post-processing --------------------------------------------------------------------------
        result_cl = []
        for i in range(len(_INPUT_AOAList)):
            result_cl.append(self._read_polar_file(output_file_list[idx]))
        # Fuselage correction
        k_fus = 1 + 0.025*width_max/span_wing - 0.025*(width_max/span_wing)**2
        cl_0 = result_cl[0] * k_fus
        cl_5 = result_cl[1] * k_fus
        # Calculate derivative
        cl_alpha = (cl_5 - cl_0) / ((_INPUT_AOAList[1]-_INPUT_AOAList[0])*math.pi/180)           
        # Delete temporary directory    
        tmp_directory.cleanup()              
        
        if self.options["low_speed_aero"]:
            outputs['data:aerodynamics:aircraft:low_speed:CL0_clean'] = cl_0
            outputs['data:aerodynamics:aircraft:low_speed:CL_alpha'] = cl_alpha
        else:
            outputs['data:aerodynamics:aircraft:cruise:CL0_clean'] = cl_0
            outputs['data:aerodynamics:aircraft:cruise:CL_alpha'] = cl_alpha
        
    @staticmethod
    def _read_polar_file(tmp_result_file_path: str) -> float:
        result_cl = []
        result_cdi = []
        result_oswald = []
        result_cm = []
        # Colect data from .polar file
        with open(tmp_result_file_path, 'r') as hf:
            line = hf.readlines()
            i = 0
            iteration_found = True
            while iteration_found:
                try:
                    # Cl
                    iter_cl = float(line[i + 1][40:50].replace(' ', ''))
                    # Cdi
                    iter_cdi = float(line[i + 1][60:70].replace(' ', ''))
                    # Oswald
                    iter_oswald = float(line[i + 1][100:110].replace(' ', ''))
                    # Cm
                    iter_cm = float(line[i + 1][150:160].replace(' ', ''))
                    # Save
                    result_cl.append(iter_cl)
                    result_cdi.append(iter_cdi)
                    result_oswald.append(iter_oswald)
                    result_cm.append(iter_cm)
                    i += 1
                except:
                    iteration_found = False
                
        return result_cl[len(result_cl)-1]
    
    @staticmethod
    def _create_tmp_directory() -> TemporaryDirectory:
        
        """Provide temporary directory for calculation."""
        
        for tmp_base_path in [None, pth.join(str(Path.home()), ".fast")]:
            if tmp_base_path is not None:
                os.makedirs(tmp_base_path, exist_ok=True)
            tmp_directory = tempfile.TemporaryDirectory(prefix="x", dir=tmp_base_path)
            break
            
        return tmp_directory

    @staticmethod
    def _rewrite_path(file_path: str) -> str:
        file_path = '\"' + file_path.replace('\\', '\\\\') + '\"'
        return file_path