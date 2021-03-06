"""
This module launches XFOIL computations
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

import logging
import os
import os.path as pth
import shutil
import tempfile
from pathlib import Path
from tempfile import TemporaryDirectory
import warnings

import numpy as np
from fastoad.models.aerodynamics.external.xfoil import xfoil699
from fastoad.utils.resource_management.copy import copy_resource
from importlib_resources import path
from openmdao.components.external_code_comp import ExternalCodeComp
from openmdao.utils.file_wrap import InputFileGenerator
from ...constants import POLAR_POINT_COUNT
from ....geometry.profiles.get_profile import get_profile

from . import resources as local_resources

OPTION_RESULT_POLAR_FILENAME = "result_polar_filename"
OPTION_RESULT_FOLDER_PATH = "result_folder_path"
OPTION_XFOIL_EXE_PATH = "xfoil_exe_path"
OPTION_ALPHA_START = "alpha_start"
OPTION_ALPHA_END = "alpha_end"
OPTION_ITER_LIMIT = "iter_limit"
DEFAULT_2D_CL_MAX = 1.9

_INPUT_FILE_NAME = "polar_session.txt"
_STDOUT_FILE_NAME = "polar_calc.log"
_STDERR_FILE_NAME = "polar_calc.err"
_DEFAULT_AIRFOIL_FILE = "naca23012.af"
_TMP_PROFILE_FILE_NAME = "in"  # as short as possible to avoid problems of path length
_TMP_RESULT_FILE_NAME = "out"  # as short as possible to avoid problems of path length
XFOIL_EXE_NAME = "xfoil.exe"  # name of embedded XFoil executable

_LOGGER = logging.getLogger(__name__)

_XFOIL_PATH_LIMIT = 64


class XfoilPolar(ExternalCodeComp):
    """
    Runs a polar computation with XFOIL and returns the 2D max lift coefficient
    """

    _xfoil_output_names = ["alpha", "CL", "CD", "CDp", "CM", "Top_Xtr", "Bot_Xtr"]
    """Column names in XFOIL polar result"""

    def initialize(self):
        
        self.options.declare(OPTION_XFOIL_EXE_PATH, default="", types=str, allow_none=True)
        self.options.declare("wing_airfoil_file", default=_DEFAULT_AIRFOIL_FILE, types=str)
        self.options.declare(OPTION_RESULT_FOLDER_PATH, default="", types=str)
        self.options.declare(OPTION_RESULT_POLAR_FILENAME, default="polar_result.txt", types=str)
        self.options.declare(OPTION_ALPHA_START, default=0.0, types=float)
        self.options.declare(OPTION_ALPHA_END, default=30.0, types=float)
        self.options.declare(OPTION_ITER_LIMIT, default=500, types=int)

    def setup(self):
        
        self.add_input("data:geometry:wing:thickness_ratio", val=np.nan)
        self.add_input("xfoil:length", val=np.nan, units="m")
        self.add_input("xfoil:mach", val=np.nan)
        self.add_input("xfoil:unit_reynolds", val=np.nan)
        self.add_output("xfoil:alpha", shape=POLAR_POINT_COUNT, units="deg")
        self.add_output("xfoil:CL", shape=POLAR_POINT_COUNT)
        self.add_output("xfoil:CD", shape=POLAR_POINT_COUNT)
        self.add_output("xfoil:CDp", shape=POLAR_POINT_COUNT)
        self.add_output("xfoil:CM", shape=POLAR_POINT_COUNT)
        self.add_output("xfoil:CL_max_2D")

        self.declare_partials("*", "*", method="fd")

    def check_config(self, logger):
        # let void to avoid logger error on "The command cannot be empty"
        pass

    def compute(self, inputs, outputs):

        # Create result folder first (if it must fail, let it fail as soon as possible)
        result_folder_path = self.options[OPTION_RESULT_FOLDER_PATH]
        if result_folder_path != "":
            os.makedirs(result_folder_path, exist_ok=True)

        # Get inputs and initialise outputs
        thickness_ratio = inputs["data:geometry:wing:thickness_ratio"]
        length = inputs["xfoil:length"]
        mach = inputs["xfoil:mach"]
        reynolds = inputs["xfoil:unit_reynolds"]*length

        # Pre-processing (populating temp directory) -----------------------------------------------
        # XFoil exe
        tmp_directory = self._create_tmp_directory()
        if self.options[OPTION_XFOIL_EXE_PATH]:
            # if a path for Xfoil has been provided, simply use it
            self.options["command"] = [self.options[OPTION_XFOIL_EXE_PATH]]
        else:
            # otherwise, copy the embedded resource in tmp dir
            # noinspection PyTypeChecker
            copy_resource(xfoil699, XFOIL_EXE_NAME, tmp_directory.name)
            self.options["command"] = [pth.join(tmp_directory.name, XFOIL_EXE_NAME)]

        # I/O files
        self.stdin = pth.join(tmp_directory.name, _INPUT_FILE_NAME)
        self.stdout = pth.join(tmp_directory.name, _STDOUT_FILE_NAME)
        self.stderr = pth.join(tmp_directory.name, _STDERR_FILE_NAME)

        # profile file
        tmp_profile_file_path = pth.join(tmp_directory.name, _TMP_PROFILE_FILE_NAME)
        profile = get_profile(
            file_name=self.options["wing_airfoil_file"],
            thickness_ratio=thickness_ratio,
        ).get_sides()
        # noinspection PyTypeChecker
        np.savetxt(
            tmp_profile_file_path,
            profile.to_numpy(),
            fmt="%.15f",
            delimiter=" ",
            header="Wing",
            comments="",
        )

        # standard input file
        tmp_result_file_path = pth.join(tmp_directory.name, _TMP_RESULT_FILE_NAME)
        parser = InputFileGenerator()
        with path(local_resources, _INPUT_FILE_NAME) as input_template_path:
            parser.set_template_file(str(input_template_path))
            parser.set_generated_file(self.stdin)
            parser.mark_anchor("RE")
            parser.transfer_var(float(reynolds), 1, 1)
            parser.mark_anchor("M")
            parser.transfer_var(float(mach), 1, 1)
            parser.mark_anchor("ITER")
            parser.transfer_var(self.options[OPTION_ITER_LIMIT], 1, 1)
            parser.mark_anchor("ASEQ")
            parser.transfer_var(self.options[OPTION_ALPHA_START], 1, 1)
            parser.transfer_var(self.options[OPTION_ALPHA_END], 2, 1)
            parser.reset_anchor()
            parser.mark_anchor("/profile")
            parser.transfer_var(tmp_profile_file_path, 0, 1)
            parser.mark_anchor("/polar_result")
            parser.transfer_var(tmp_result_file_path, 0, 1)
            parser.generate()

        # Run XFOIL --------------------------------------------------------------------------------
        self.options["external_input_files"] = [self.stdin, tmp_profile_file_path]
        self.options["external_output_files"] = [tmp_result_file_path]
        super().compute(inputs, outputs)

        # Post-processing --------------------------------------------------------------------------
        result_array = self._read_polar(tmp_result_file_path)
        cl_max_2d = self._get_max_cl(result_array["alpha"], result_array["CL"])
        real_length = min(POLAR_POINT_COUNT, len(result_array["alpha"]))
        if real_length < len(result_array["alpha"]):
            warnings.warn("Defined maximum polar point count in constants.py exceeded!")
            outputs["xfoil:alpha"] = np.linspace(result_array["alpha"][0], result_array["alpha"][-1], POLAR_POINT_COUNT)
            outputs["xfoil:CL"] = np.interp(outputs["xfoil:alpha"], result_array["alpha"], result_array["CL"])
            outputs["xfoil:CD"] = np.interp(outputs["xfoil:alpha"], result_array["alpha"], result_array["CD"])
            outputs["xfoil:CDp"] = np.interp(outputs["xfoil:alpha"], result_array["alpha"], result_array["CDp"])
            outputs["xfoil:CDp"] = np.interp(outputs["xfoil:alpha"], result_array["alpha"], result_array["CM"])
        else:
            outputs["xfoil:alpha"] = np.zeros(POLAR_POINT_COUNT)
            outputs["xfoil:CL"] = np.zeros(POLAR_POINT_COUNT)
            outputs["xfoil:CD"] = np.zeros(POLAR_POINT_COUNT)
            outputs["xfoil:CDp"] = np.zeros(POLAR_POINT_COUNT)
            outputs["xfoil:CM"] = np.zeros(POLAR_POINT_COUNT)
            outputs["xfoil:alpha"][0:real_length] = result_array["alpha"]
            outputs["xfoil:CL"][0:real_length] = result_array["CL"]
            outputs["xfoil:CD"][0:real_length] = result_array["CD"]
            outputs["xfoil:CDp"][0:real_length] = result_array["CDp"]
            outputs["xfoil:CM"][0:real_length] = result_array["CM"]
        outputs["xfoil:CL_max_2D"] = cl_max_2d

        # Getting output files if needed
        if self.options[OPTION_RESULT_FOLDER_PATH] != "":
            if pth.exists(tmp_result_file_path):
                polar_file_path = pth.join(
                    result_folder_path, self.options[OPTION_RESULT_POLAR_FILENAME]
                )
                shutil.move(tmp_result_file_path, polar_file_path)

            if pth.exists(self.stdout):
                stdout_file_path = pth.join(result_folder_path, _STDOUT_FILE_NAME)
                shutil.move(self.stdout, stdout_file_path)

            if pth.exists(self.stderr):
                stderr_file_path = pth.join(result_folder_path, _STDERR_FILE_NAME)
                shutil.move(self.stderr, stderr_file_path)

        tmp_directory.cleanup()

    @staticmethod
    def _read_polar(xfoil_result_file_path: str) -> np.ndarray:
        """
        :param xfoil_result_file_path:
        :return: numpy array with XFoil polar results
        """
        if os.path.isfile(xfoil_result_file_path):
            dtypes = [(name, "f8") for name in XfoilPolar._xfoil_output_names]
            result_array = np.genfromtxt(xfoil_result_file_path, skip_header=12, dtype=dtypes)
            return result_array

        _LOGGER.error("XFOIL results file not found")
        return np.array([])

    @staticmethod
    def _get_max_cl(alpha: np.ndarray, lift_coeff: np.ndarray) -> float:
        """

        :param alpha:
        :param lift_coeff: CL
        :return: max CL if enough alpha computed, or default value otherwise
        """
        if len(alpha) > 0 and max(alpha) >= 5.0:
            return max(lift_coeff)

        _LOGGER.warning("2D CL max not found. Using default value (%s)", DEFAULT_2D_CL_MAX)
        return DEFAULT_2D_CL_MAX


    @staticmethod
    def _create_tmp_directory() -> TemporaryDirectory:
        # Dev Note: XFOIL fails if length of provided file path exceeds 64 characters.
        #           Changing working directory to the tmp dir would allow to just provide file name,
        #           but it is not really safe (at least, it does mess with the coverage report).
        #           Then the point is to get a tmp directory with a short path.
        #           On Windows, the default (user-dependent) tmp dir can exceed the limit.
        #           Therefore, as a second choice, tmp dir is created as close of user home
        #           directory as possible.
        tmp_candidates = []
        for tmp_base_path in [None, pth.join(str(Path.home()), ".fast")]:
            if tmp_base_path is not None:
                os.makedirs(tmp_base_path, exist_ok=True)
            tmp_directory = tempfile.TemporaryDirectory(prefix="x", dir=tmp_base_path)
            tmp_candidates.append(tmp_directory.name)
            tmp_profile_file_path = pth.join(tmp_directory.name, _TMP_PROFILE_FILE_NAME)
            tmp_result_file_path = pth.join(tmp_directory.name, _TMP_RESULT_FILE_NAME)

            if max(len(tmp_profile_file_path), len(tmp_result_file_path)) <= _XFOIL_PATH_LIMIT:
                # tmp_directory is OK. Stop there
                break
            # tmp_directory has a too long path. Erase and continue...
            tmp_directory.cleanup()

        if max(len(tmp_profile_file_path), len(tmp_result_file_path)) > _XFOIL_PATH_LIMIT:
            raise IOError(
                "Could not create a tmp directory where file path will respects XFOIL "
                "limitation (%i): tried %s" % (_XFOIL_PATH_LIMIT, tmp_candidates)
            )

        return tmp_directory
