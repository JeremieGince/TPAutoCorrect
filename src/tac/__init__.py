__author__ = "Jérémie Gince"
__email__ = "gincejeremie@gmail.com"
__copyright__ = "Copyright 2023, Jérémie Gince"
__license__ = "Apache 2.0"
__url__ = "https://github.com/JeremieGince/TPAutoCorrect"
__version__ = "0.0.1-beta0"

from .source import (
    SourceCode,
    SourceTests,
    Source,
    SourceMasterCode,
    SourceMasterTests,
)
from .tester import Tester, TesterInput
from .report import Report
from . import utils as tac_utils

import warnings

warnings.filterwarnings("ignore", category=Warning, module="docutils")
warnings.filterwarnings("ignore", category=Warning, module="sphinx")
