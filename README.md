[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

FAST-OAD-GA: Future Aircraft Sizing Tool - Overall Aircraft Design (General Aviation extension)
===============================================================================================

FAST-OAD-GA is derived from FAST-OAD framework performing rapid Overall Aircraft Design.

It proposes multi-disciplinary analysis and optimisation by relying on
the [OpenMDAO framework](https://openmdao.org/).

FAST-OAD-(GA) allows easy switching between models for a same discipline, and
also adding/removing disciplines to match the need of your study.

Currently, FAST-OAD-GA is bundled with models for general aviation and conventional
propulsion (ICE propeller based). Other models will come and you may create
your own models and use them instead of bundled ones.

Install
-------

**Prerequisite**:FAST-OAD-GA needs at least **Python 3.6.1**.

It is recommended (but not required) to install FAST-OAD-GA in a virtual
environment with provided .lock file ([conda](https://docs.conda.io/en/latest/),
[venv](https://docs.python.org/3.7/library/venv.html), ...)

Yet, for now the FAST-OAD-GA is not registered for a pip install.
Therefore you can copy directly the folder from ./master to:
../Anaconda3/Lib/site/packages/fastga
