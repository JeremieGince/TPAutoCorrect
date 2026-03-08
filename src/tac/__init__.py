"""
TPAutoCorrect - Automated homework grading and testing framework.

This package provides a comprehensive framework for automatically grading
programming assignments, including PEP8 compliance checking, test execution,
code coverage analysis, and report generation.

Main Components:
    - Source: Manage source code and test files from local or remote sources
    - Tester: Run automated tests and collect metrics
    - Report: Store and compute weighted grades
    - Homework: Manage full homework assignments with student repositories

Example Usage::

    import tac

    # Create sources
    code = tac.SourceCode(src_path="student/src")
    tests = tac.SourceTests(src_path="student/tests")

    # Run tests
    tester = tac.Tester(code, tests)
    tester.run()

    # Access results
    print(f"Grade: {tester.report.grade}/100")

Author: Jérémie Gince
Email: gincejeremie@gmail.com
License: Apache 2.0
"""

__author__ = "Jérémie Gince"
__email__ = "gincejeremie@gmail.com"
__copyright__ = "Copyright 2023, Jérémie Gince"
__license__ = "Apache 2.0"
__url__ = "https://github.com/JeremieGince/TPAutoCorrect"
__package__ = "tac"

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version(__package__)
except Exception:
    __version__ = "unknown"

import warnings

# Import core modules
from . import utils as tac_utils
from .grade import make_notes_template, update_notes_yaml
from .homework import Homework
from .report import Report
from .source import (
    Source,
    SourceBaseTests,
    SourceCode,
    SourceHiddenTests,
    SourceMasterCode,
    SourceSuppTests,
    SourceTests,
)
from .tester import Tester
from .utils import get_report, get_report_with_pdf

# Suppress warnings from dependencies
warnings.filterwarnings("ignore", category=Warning, module="docutils")
warnings.filterwarnings("ignore", category=Warning, module="sphinx")

# Public API
__all__ = [
    "Report",
    "Source",
    "SourceBaseTests",
    "SourceCode",
    "SourceHiddenTests",
    "SourceMasterCode",
    "SourceSuppTests",
    "SourceTests",
    "Tester",
    "tac_utils",
    "make_notes_template",
    "update_notes_yaml",
    "get_report",
    "get_report_with_pdf",
    "Homework",
    "__version__",
    "__author__",
    "__email__",
]
