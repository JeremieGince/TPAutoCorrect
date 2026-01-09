__author__ = "Jérémie Gince"
__email__ = "gincejeremie@gmail.com"
__copyright__ = "Copyright 2023, Jérémie Gince"
__license__ = "Apache 2.0"
__url__ = "https://github.com/JeremieGince/TPAutoCorrect"
__version__ = "0.0.1-beta0"

import warnings

from . import utils as tac_utils
from .report import Report
from .source import (Source, SourceCode, SourceMasterCode, SourceMasterTests,
                     SourceTests)
from .tester import Tester

warnings.filterwarnings("ignore", category=Warning, module="docutils")
warnings.filterwarnings("ignore", category=Warning, module="sphinx")
