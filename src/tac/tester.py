"""
Testing and evaluation module for TPAutoCorrect.

This module provides the Tester class for running code evaluation,
collecting metrics (coverage, test results, PEP8 compliance), and
generating comprehensive reports.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import warnings
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Union

from . import utils
from .perf_test_case import PEP8TestCase
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


class Tester:
    """
    Tester class for running code and test evaluation.

    Handles code coverage analysis, test pass rates, PEP8 compliance checking,
    and supports three test suites: supp_tests (student), base_tests (master),
    and hidden_tests (master).

    :cvar str CODE_COVERAGE_KEY: Key for code coverage metric.
    :cvar str SUPP_TESTS_KEY: Key for supplementary (student) tests passed metric.
    :cvar str BASE_TESTS_KEY: Key for base (master) tests passed metric.
    :cvar str HIDDEN_TESTS_KEY: Key for hidden (master) tests passed metric.
    :cvar str PEP8_KEY: Key for PEP8 compliance metric.
    :cvar dict DEFAULT_WEIGHTS: Default weights for metrics.
    :cvar int DEFAULT_PYTEST_TIMEOUT: Default timeout for pytest execution (seconds).
    :cvar str SUPP_PYTEST_REPORT: Filename for supp_tests pytest JSON report.
    :cvar str BASE_PYTEST_REPORT: Filename for base_tests pytest JSON report.
    :cvar str HIDDEN_PYTEST_REPORT: Filename for hidden_tests pytest JSON report.
    :cvar str SUPP_PYTEST_OUTPUT: Filename for supp_tests pytest stdout/stderr.
    :cvar str BASE_PYTEST_OUTPUT: Filename for base_tests pytest stdout/stderr.
    :cvar str HIDDEN_PYTEST_OUTPUT: Filename for hidden_tests pytest stdout/stderr.
    :cvar str DEFAULT_REPORT_FILENAME: Default report filename.
    :cvar float DEFAULT_PASSED_RATIO_ZERO_TESTS: Default ratio when there are zero tests.
    :cvar Callable DEFAULT_LOGGING_FUNC: Default logging function.

    :ivar SourceCode code_src: The student source code to test.
    :ivar SourceSuppTests supp_tests_src: Student supplementary test source.
    :ivar SourceBaseTests base_tests_src: Master base test source.
    :ivar SourceHiddenTests hidden_tests_src: Master hidden test source.
    :ivar SourceMasterCode master_code_src: Optional master code source.
    :ivar dict kwargs: Additional keyword arguments.
    :ivar Callable logging_func: Logging function.
    :ivar dict supp_test_cases_summary: Summary of supp_tests results.
    :ivar dict base_test_cases_summary: Summary of base_tests results.
    :ivar dict hidden_test_cases_summary: Summary of hidden_tests results.
    :ivar str report_dir: Directory for storing reports and temporary files.
    :ivar str report_filepath: Path to the final report file.
    :ivar Report report: The report object containing all metrics.
    :ivar dict weights: Weights for different metrics.
    """

    # Metric keys
    CODE_COVERAGE_KEY = "code_coverage"
    SUPP_TESTS_KEY = "supp_tests_passed"
    BASE_TESTS_KEY = "base_tests_passed"
    HIDDEN_TESTS_KEY = "hidden_tests_passed"
    PEP8_KEY = "PEP8"

    # Default configuration
    DEFAULT_WEIGHTS = {
        CODE_COVERAGE_KEY: 1.0,
        SUPP_TESTS_KEY: 1.0,
        BASE_TESTS_KEY: 1.0,
        HIDDEN_TESTS_KEY: 1.0,
        PEP8_KEY: 1.0,
    }
    DEFAULT_PYTEST_TIMEOUT = 60  # seconds

    # File naming conventions
    SUPP_PYTEST_REPORT = "supp_tests_report.json"
    BASE_PYTEST_REPORT = "base_tests_report.json"
    HIDDEN_PYTEST_REPORT = "hidden_tests_report.json"
    SUPP_PYTEST_OUTPUT = "supp_tests_execution.log"
    BASE_PYTEST_OUTPUT = "base_tests_execution.log"
    HIDDEN_PYTEST_OUTPUT = "hidden_tests_execution.log"
    DOT_COVERAGE = ".coverage"
    COVERAGE_JSON = "coverage.json"
    COVERAGE_XML = "coverage.xml"
    PEP8_ERRORS = "pep8_errors.log"
    DEFAULT_REPORT_FILENAME = "report.json"
    DEFAULT_PASSED_RATIO_ZERO_TESTS = 0.0
    DEFAULT_LOGGING_FUNC = logging.info

    def __init__(
        self,
        code_src: Optional[SourceCode] = None,
        supp_tests_src: Optional[SourceSuppTests] = None,
        *,
        base_tests_src: Optional[SourceBaseTests] = None,
        hidden_tests_src: Optional[SourceHiddenTests] = None,
        master_code_src: Optional[SourceMasterCode] = None,
        report_kwargs: Optional[dict] = None,
        **kwargs,
    ):
        """
        Initialize the Tester.

        :param code_src: The student source code to test.
        :type code_src: Optional[SourceCode]
        :param supp_tests_src: Student supplementary tests (run with coverage).
        :type supp_tests_src: Optional[SourceSuppTests]
        :param base_tests_src: Master base tests (run without coverage).
        :type base_tests_src: Optional[SourceBaseTests]
        :param hidden_tests_src: Master hidden tests (run without coverage).
        :type hidden_tests_src: Optional[SourceHiddenTests]
        :param master_code_src: Master code source (unused at runtime, kept for setup).
        :type master_code_src: Optional[SourceMasterCode]
        :param report_kwargs: Additional arguments for the Report object.
        :type report_kwargs: Optional[dict]
        :param kwargs: Additional keyword arguments including:
            - logging_func: Custom logging function
            - report_dir: Directory for reports
            - report_filepath: Path to report file
            - weights: Custom weights for metrics
            - pytest_timeout: Timeout for pytest execution (default: 60 seconds)
        """
        self.code_src = code_src or SourceCode()
        self.supp_tests_src = supp_tests_src or SourceSuppTests()
        self.base_tests_src = base_tests_src
        self.hidden_tests_src = hidden_tests_src
        self.master_code_src = master_code_src

        self.kwargs = kwargs
        self.logging_func = kwargs.get("logging_func", self.DEFAULT_LOGGING_FUNC)
        self.pytest_timeout = kwargs.get("pytest_timeout", self.DEFAULT_PYTEST_TIMEOUT)

        # Initialize test summaries
        self.supp_test_cases_summary: Optional[dict] = None
        self.base_test_cases_summary: Optional[dict] = None
        self.hidden_test_cases_summary: Optional[dict] = None

        # Setup report directory and filepath
        self.report_dir = self.kwargs.get("report_dir")
        if self.report_dir is None:
            self.report_dir = os.path.join(os.getcwd(), "report_dir")
        # Always store as an absolute path so that venv executables built from
        # report_dir remain valid when subprocess changes its cwd to report_dir.
        self.report_dir = str(Path(self.report_dir).resolve())

        self.report_filepath = self.kwargs.get(
            "report_filepath",
            os.path.join(self.report_dir, self.DEFAULT_REPORT_FILENAME),
        )

        # Initialize report
        report_kwargs = report_kwargs or {}
        self.report = Report(report_filepath=self.report_filepath, **report_kwargs)

        # Setup weights
        self.weights = self.kwargs.get("weights", self.DEFAULT_WEIGHTS.copy())

    @property
    def dot_coverage_path(self) -> Path:
        """Path to the temporary .coverage file."""
        return Path(self.report_dir) / self.DOT_COVERAGE

    @property
    def coverage_json_path(self) -> Path:
        """Path to the temporary coverage.json file."""
        return Path(self.report_dir) / self.COVERAGE_JSON

    @property
    def coverage_xml_path(self) -> Path:
        """Path to the temporary coverage.xml file."""
        return Path(self.report_dir) / self.COVERAGE_XML

    @property
    def supp_report_json_path(self) -> Path:
        """Path to the supp_tests pytest JSON report file."""
        return Path(self.report_dir) / self.SUPP_PYTEST_REPORT

    @property
    def base_report_json_path(self) -> Path:
        """Path to the base_tests pytest JSON report file."""
        return Path(self.report_dir) / self.BASE_PYTEST_REPORT

    @property
    def hidden_report_json_path(self) -> Path:
        """Path to the hidden_tests pytest JSON report file."""
        return Path(self.report_dir) / self.HIDDEN_PYTEST_REPORT

    @property
    def pep8_errors_path(self) -> Path:
        """Path to the PEP8 errors log file."""
        return Path(self.report_dir) / self.PEP8_ERRORS

    @property
    def all_sources(self) -> List[Source]:
        """Get all non-None source objects."""
        sources = [
            self.code_src,
            self.supp_tests_src,
            self.base_tests_src,
            self.hidden_tests_src,
            self.master_code_src,
        ]
        return [s for s in sources if s is not None]

    @property
    def is_setup(self) -> bool:
        """Check if all sources are set up."""
        return all(s.is_setup for s in self.all_sources)

    def get_pytest_plugins_options(
        self,
        add_cov: bool = True,
        append_cov: bool = False,
        add_json_report: bool = True,
        json_report_file: Optional[str] = None,
        **kwargs,
    ) -> List[str]:
        """
        Build the list of pytest command-line options for plugins.

        :param add_cov: Whether to add coverage options. Defaults to True.
        :param append_cov: Whether to append to an existing coverage file (--cov-append).
            Only relevant when add_cov is True. Defaults to False.
        :param add_json_report: Whether to add JSON report options. Defaults to True.
        :param json_report_file: Name of the JSON report file.
        :param kwargs: Additional keyword arguments.
        :return: List of pytest options.
        """
        options = []

        if add_cov:
            src_dirname = os.path.basename(self.code_src.local_path)
            options += [
                f"--cov={src_dirname}",
                "--cov-report=json",
                "-p",
                "no:cacheprovider",
            ]
            if append_cov:
                options.append("--cov-append")

        if add_json_report:
            json_report_file = json_report_file or self.SUPP_PYTEST_REPORT
            options += [
                "--json-report",
                f"--json-report-file={json_report_file}",
                "--json-report-summary",
                "--json-report-indent=4",
            ]

        return options

    def setup_at(self, **kwargs) -> "Tester":
        """
        Set up all sources at the report directory.

        :param kwargs: Additional keyword arguments including:
            - force_setup: Force setup even if already set up
            - debug: Enable debug logging
        :return: The current instance.
        """
        force = kwargs.pop("force_setup", False)
        debug = kwargs.get("debug", False)

        if self.is_setup and not force:
            self.logging_func("All sources already set up, skipping...")
            return self

        self.code_src.setup_at(self.report_dir, **kwargs)

        _supp_available = False
        try:
            _supp_available = (
                self.supp_tests_src is not None and self.supp_tests_src.is_local
            )
        except (ValueError, Exception):
            pass

        if _supp_available:
            self.supp_tests_src.setup_at(self.report_dir, **kwargs)
        else:
            _supp_path = None
            try:
                _supp_path = (
                    self.supp_tests_src.src_path if self.supp_tests_src else None
                )
            except (ValueError, Exception):
                pass
            # Set working_dir so that local_path returns a (non-existent) path
            # rather than None — preventing downstream None-path errors in _run
            # and get_pep8_score.
            if self.supp_tests_src is not None:
                self.supp_tests_src.working_dir = self.report_dir
            warnings.warn(
                f"supp_tests source not found at {_supp_path!r}. "
                f"Skipping supp_tests setup. Scores for "
                f"{self.CODE_COVERAGE_KEY!r} and {self.SUPP_TESTS_KEY!r} will be set to 0.",
                RuntimeWarning,
            )

        if self.master_code_src is not None:
            self.master_code_src.setup_at(self.report_dir, **kwargs)

        if self.base_tests_src is not None:
            _base_available = False
            try:
                _base_available = (
                    self.base_tests_src.is_local or self.base_tests_src.is_remote
                )
            except (ValueError, Exception):
                pass

            if _base_available:
                try:
                    self.base_tests_src.setup_at(self.report_dir, **kwargs)
                except FileNotFoundError as e:
                    _base_path = None
                    try:
                        _base_path = self.base_tests_src.src_path
                    except (ValueError, Exception):
                        pass
                    self.base_tests_src.working_dir = self.report_dir
                    warnings.warn(
                        f"base_tests source path not found: {e}. "
                        f"Skipping base_tests setup. Score for "
                        f"{self.BASE_TESTS_KEY!r} will be set to 0.",
                        RuntimeWarning,
                    )
            else:
                _base_path = None
                try:
                    _base_path = self.base_tests_src.src_path
                except (ValueError, Exception):
                    pass
                if self.base_tests_src is not None:
                    self.base_tests_src.working_dir = self.report_dir
                warnings.warn(
                    f"base_tests source not found at {_base_path!r}. "
                    f"Skipping base_tests setup. Score for "
                    f"{self.BASE_TESTS_KEY!r} will be set to 0.",
                    RuntimeWarning,
                )

        if self.hidden_tests_src is not None:
            _hidden_available = False
            try:
                _hidden_available = (
                    self.hidden_tests_src.is_local or self.hidden_tests_src.is_remote
                )
            except (ValueError, Exception):
                pass

            if _hidden_available:
                try:
                    self.hidden_tests_src.setup_at(self.report_dir, **kwargs)
                except FileNotFoundError as e:
                    self.hidden_tests_src.working_dir = self.report_dir
                    warnings.warn(
                        f"hidden_tests source path not found: {e}. "
                        f"Skipping hidden_tests setup. Score for "
                        f"{self.HIDDEN_TESTS_KEY!r} will be set to 0.",
                        RuntimeWarning,
                    )
            else:
                _hidden_path = None
                try:
                    _hidden_path = self.hidden_tests_src.src_path
                except (ValueError, Exception):
                    pass
                if self.hidden_tests_src is not None:
                    self.hidden_tests_src.working_dir = self.report_dir
                warnings.warn(
                    f"hidden_tests source not found at {_hidden_path!r}. "
                    f"Skipping hidden_tests setup. Score for "
                    f"{self.HIDDEN_TESTS_KEY!r} will be set to 0.",
                    RuntimeWarning,
                )

        if debug:
            self.logging_func(f"✓ Student code: {self.code_src.local_path}")
            _supp_local = self.supp_tests_src.local_path if _supp_available else None
            self.logging_func(f"✓ Supp tests: {_supp_local}")
            if self.base_tests_src:
                self.logging_func(f"✓ Base tests: {self.base_tests_src.local_path}")
            if self.hidden_tests_src:
                self.logging_func(f"✓ Hidden tests: {self.hidden_tests_src.local_path}")
            if self.master_code_src:
                self.logging_func(f"✓ Master code: {self.master_code_src.local_path}")

        return self

    def run(self, *args, **kwargs) -> None:
        """
        Run the full test and evaluation pipeline.

        :param args: Unused positional arguments.
        :param kwargs: Additional keyword arguments including:
            - weights: Custom weights to merge with defaults
            - save_report: Whether to save the report (default: True)
            - clear_pytest_temporary_files: Whether to clear pytest temp files
            - clear_temporary_files: Whether to clear all temp files
            - overwrite: Whether to overwrite existing files
            - debug: Enable debug logging
        """
        self.weights.update(kwargs.pop("weights", {}))

        save_report = kwargs.pop("save_report", True)
        clear_pytest_temporary_files = kwargs.pop("clear_pytest_temporary_files", False)
        clear_temporary_files = kwargs.pop("clear_temporary_files", False)

        self.setup_at(**kwargs)
        self._run(**kwargs)

        if save_report:
            self.report.save(self.report_filepath)
            self.logging_func(f"✓ Report saved to {self.report_filepath}")

        if clear_pytest_temporary_files:
            self.clear_pytest_temporary_files()

        if clear_temporary_files:
            self.clear_temporary_files()

    def _run(self, **kwargs) -> None:
        """
        Internal method to run all test suites, collect metrics, and update the report.

        Order:
        1. supp_tests (student) — with coverage → SUPP_TESTS_KEY
        2. base_tests (master) — with coverage append → BASE_TESTS_KEY
           (coverage is read after both supp_tests and base_tests have run)
        3. CODE_COVERAGE from the combined .coverage file
        4. PEP8 on code_src and supp_tests_src
        5. hidden_tests (master) — no coverage → HIDDEN_TESTS_KEY

        Missing suites produce score=0 with a warning (no exception).
        """
        self.clear_pycache()

        supp_dir = self.supp_tests_src.local_path if self.supp_tests_src else None
        base_dir = self.base_tests_src.local_path if self.base_tests_src else None

        # --- supp_tests (with coverage, fresh run) ---
        supp_ran = False
        if supp_dir and os.path.isdir(supp_dir):
            self._run_supp_pytest(append_cov=False, **kwargs)
            self.supp_test_cases_summary = deepcopy(
                self.get_test_cases_summary(self.supp_report_json_path)
            )
            self.report.add(
                self.SUPP_TESTS_KEY,
                self.supp_test_cases_summary["percent_passed"],
                weight=self.weights.get(self.SUPP_TESTS_KEY, 1.0),
            )
            supp_ran = True
        else:
            warnings.warn(
                f"supp_tests directory not found at {supp_dir!r}. "
                f"Score for {self.SUPP_TESTS_KEY!r} excluded from grade (weight=0).",
                RuntimeWarning,
            )
            self.report.add(self.SUPP_TESTS_KEY, 0.0, weight=0.0)

        # --- base_tests (with coverage append) ---
        if base_dir and os.path.isdir(base_dir):
            self._run_master_suite_pytest(
                suite_dirname=os.path.relpath(
                    self.base_tests_src.local_path, self.report_dir
                ),
                report_filename=self.BASE_PYTEST_REPORT,
                output_filename=self.BASE_PYTEST_OUTPUT,
                test_type="Base Tests",
                add_cov=True,
                append_cov=supp_ran,
                **kwargs,
            )
            self.base_test_cases_summary = deepcopy(
                self.get_test_cases_summary(self.base_report_json_path)
            )
            self.report.add(
                self.BASE_TESTS_KEY,
                self.base_test_cases_summary["percent_passed"],
                weight=self.weights.get(self.BASE_TESTS_KEY, 1.0),
            )
        else:
            warnings.warn(
                f"base_tests directory not found at {base_dir!r}. "
                f"Score for {self.BASE_TESTS_KEY!r} excluded from grade (weight=0).",
                RuntimeWarning,
            )
            self.report.add(self.BASE_TESTS_KEY, 0.0, weight=0.0)
            self.report.add(
                self.BASE_TESTS_KEY,
                0.0,
                weight=self.weights.get(self.BASE_TESTS_KEY, 1.0),
            )

        # --- CODE_COVERAGE (from combined supp_tests + base_tests run) ---
        if supp_ran or (base_dir and os.path.isdir(base_dir)):
            self.report.add(
                self.CODE_COVERAGE_KEY,
                self.get_code_coverage(),
                weight=self.weights.get(self.CODE_COVERAGE_KEY, 1.0),
            )
        else:
            warnings.warn(
                f"Neither supp_tests nor base_tests were run. "
                f"Score for {self.CODE_COVERAGE_KEY!r} excluded from grade (weight=0).",
                RuntimeWarning,
            )
            self.report.add(self.CODE_COVERAGE_KEY, 0.0, weight=0.0)
            self.report.add(
                self.CODE_COVERAGE_KEY,
                0.0,
                weight=self.weights.get(self.CODE_COVERAGE_KEY, 1.0),
            )

        # --- PEP8 ---
        self.report.add(
            self.PEP8_KEY,
            self.get_pep8_score(),
            weight=self.weights.get(self.PEP8_KEY, 1.0),
        )

        # --- hidden_tests (no coverage) ---
        hidden_dir = self.hidden_tests_src.local_path if self.hidden_tests_src else None
        if hidden_dir and os.path.isdir(hidden_dir):
            self._run_master_suite_pytest(
                suite_dirname=os.path.relpath(
                    self.hidden_tests_src.local_path, self.report_dir
                ),
                report_filename=self.HIDDEN_PYTEST_REPORT,
                output_filename=self.HIDDEN_PYTEST_OUTPUT,
                test_type="Hidden Tests",
                **kwargs,
            )
            self.hidden_test_cases_summary = deepcopy(
                self.get_test_cases_summary(self.hidden_report_json_path)
            )
            self.report.add(
                self.HIDDEN_TESTS_KEY,
                self.hidden_test_cases_summary["percent_passed"],
                weight=self.weights.get(self.HIDDEN_TESTS_KEY, 1.0),
            )
        else:
            warnings.warn(
                f"hidden_tests directory not found at {hidden_dir!r}. "
                f"Score for {self.HIDDEN_TESTS_KEY!r} excluded from grade (weight=0).",
                RuntimeWarning,
            )
            self.report.add(self.HIDDEN_TESTS_KEY, 0.0, weight=0.0)

        self.clear_pycache()

    def _run_pytest_command(
        self, cmd: List[str], output_filename: str, test_type: str = "pytest", **kwargs
    ) -> subprocess.CompletedProcess:
        """
        Execute a pytest command and save formatted output to file.

        On timeout, logs the error, emits a :class:`RuntimeWarning`, and returns a
        synthetic ``CompletedProcess(returncode=-1)`` so the grading run can continue
        with a score of 0 for the affected suite (the JSON report file will be absent,
        causing :meth:`get_test_cases_summary` to return the empty/zero summary).

        :param cmd: Command to execute as a list.
        :param output_filename: Filename to save stdout/stderr.
        :param test_type: Type of test being run (for logging).
        :param kwargs: Additional keyword arguments including 'debug'.
        :return: CompletedProcess object from subprocess.run.
        :raises Exception: For non-timeout failures during subprocess execution.
        """
        debug = kwargs.get("debug", False)
        output_path = Path(self.report_dir) / output_filename

        Path(self.report_dir).mkdir(parents=True, exist_ok=True)

        if debug:
            self.logging_func(f"→ Running {test_type} in {self.report_dir}")
            self.logging_func(f"  Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.report_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.pytest_timeout,
                check=False,
            )

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"{'=' * 70}\n")
                f.write(f"{test_type.upper()} EXECUTION LOG\n")
                f.write(f"{'=' * 70}\n\n")
                f.write(f"Working Directory: {self.report_dir}\n")
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Return Code: {result.returncode}\n")
                f.write(f"Timeout: {self.pytest_timeout}s\n")
                f.write(f"\n{'=' * 70}\n")
                f.write("STDOUT\n")
                f.write(f"{'=' * 70}\n")
                f.write(result.stdout or "(no output)\n")
                f.write(f"\n{'=' * 70}\n")
                f.write("STDERR\n")
                f.write(f"{'=' * 70}\n")
                f.write(result.stderr or "(no output)\n")

            if debug:
                status = "✓" if result.returncode == 0 else "✗"
                self.logging_func(
                    f"{status} {test_type} completed (exit code: {result.returncode})"
                )
                if result.returncode != 0:
                    self.logging_func(f"  Details saved to: {output_path}")

            return result

        except subprocess.TimeoutExpired:
            error_msg = f"{test_type} exceeded timeout of {self.pytest_timeout}s"
            self.logging_func(f"✗ {error_msg}")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"{'=' * 70}\n")
                f.write(f"{test_type.upper()} EXECUTION LOG - TIMEOUT\n")
                f.write(f"{'=' * 70}\n\n")
                f.write(f"ERROR: {error_msg}\n")
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Working Directory: {self.report_dir}\n")
                f.write(f"Timeout Limit: {self.pytest_timeout}s\n")

            warnings.warn(
                f"{error_msg}. Score for this suite will be set to 0.",
                RuntimeWarning,
                stacklevel=2,
            )
            # Return a synthetic failed result so callers can continue grading.
            # The JSON report file will be absent, causing get_test_cases_summary
            # to return the empty summary (0% passed).
            return subprocess.CompletedProcess(
                args=cmd, returncode=-1, stdout="", stderr=error_msg
            )

        except Exception as e:
            error_msg = f"Failed to execute {test_type}: {e}"
            self.logging_func(f"✗ {error_msg}")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"{'=' * 70}\n")
                f.write(f"{test_type.upper()} EXECUTION LOG - ERROR\n")
                f.write(f"{'=' * 70}\n\n")
                f.write(f"ERROR: {error_msg}\n")
                f.write(f"Exception Type: {type(e).__name__}\n")
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"Working Directory: {self.report_dir}\n")

            raise

    def _get_venv_python_exe(self) -> str:
        """
        Return the path to the Python executable in the student's venv.

        Falls back to ``sys.executable`` if the venv path cannot be resolved
        (e.g. on an unsupported platform or before setup).

        :return: Path to the Python executable.
        :rtype: str
        """
        try:
            return self.code_src.get_venv_python_path()
        except (ValueError, AttributeError):
            return sys.executable

    def _run_supp_pytest(self, append_cov: bool = False, **kwargs) -> None:
        """
        Run pytest on the student's supp_tests with coverage measurement.

        Uses the student venv's Python executable (platform-aware) and targets
        the ``supp_tests/`` working directory.

        :param append_cov: Whether to append to an existing coverage file. Defaults to False.
        """
        options = self.get_pytest_plugins_options(
            add_cov=True,
            append_cov=append_cov,
            add_json_report=True,
            json_report_file=self.SUPP_PYTEST_REPORT,
            **kwargs,
        )

        python_exe = self._get_venv_python_exe()
        cmd = [python_exe, "-m", "pytest", *options, "supp_tests"]

        self._run_pytest_command(
            cmd,
            self.SUPP_PYTEST_OUTPUT,
            test_type="Supp Tests",
            **kwargs,
        )
        self.clear_pycache()

    def _run_master_suite_pytest(
        self,
        suite_dirname: str,
        report_filename: str,
        output_filename: str,
        test_type: str = "Master Suite",
        add_cov: bool = False,
        append_cov: bool = False,
        **kwargs,
    ) -> None:
        """
        Run pytest for a master test suite (base_tests or hidden_tests).

        Uses the student venv's Python executable (platform-aware) since tests
        run against student src/.
        Coverage is not collected by default; pass ``add_cov=True`` and
        ``append_cov=True`` to append coverage to an existing ``.coverage`` file.

        :param suite_dirname: Working directory name of the suite (e.g. "base_tests").
        :param report_filename: Filename for the JSON report.
        :param output_filename: Filename for the execution log.
        :param test_type: Label for logging.
        :param add_cov: Whether to collect coverage. Defaults to False.
        :param append_cov: Whether to append to an existing coverage file. Defaults to False.
        """
        options = self.get_pytest_plugins_options(
            add_cov=add_cov,
            append_cov=append_cov,
            add_json_report=True,
            json_report_file=report_filename,
            **kwargs,
        )

        python_exe = self._get_venv_python_exe()
        cmd = [python_exe, "-m", "pytest", *options, suite_dirname]

        self._run_pytest_command(
            cmd,
            output_filename,
            test_type=test_type,
            **kwargs,
        )
        self.clear_pycache()

    def get_code_coverage(self) -> float:
        """
        Compute the mean code coverage percentage using pytest-cov.

        :return: Mean percent of code covered by tests (0-100).
        :rtype: float
        """
        try:
            coverage_file = utils.reindent_json_file(self.coverage_json_path)

            if coverage_file is None:
                warnings.warn(f"Coverage file not found at {self.coverage_json_path}")
                return 0.0

            with open(coverage_file, "r", encoding="utf-8") as f:
                coverage_data: Dict = json.load(f)

        except Exception as err:
            warnings.warn(
                f"Could not load coverage data from {self.coverage_json_path}: {err}"
            )
            return 0.0

        if not self.code_src.local_path:
            warnings.warn("code_src.local_path is not set; cannot filter coverage data")
            return 0.0

        src_dirname = os.path.basename(self.code_src.local_path)

        summaries: List[Dict] = [
            file_data["summary"]
            for filepath, file_data in coverage_data.get("files", {}).items()
            if filepath.endswith(".py") and Path(filepath).parts[0] == src_dirname
        ]

        if not summaries:
            warnings.warn("No coverage data found for source files")
            return 0.0

        mean_percent_covered = sum(s["percent_covered"] for s in summaries) / len(
            summaries
        )
        return mean_percent_covered

    def get_test_cases_summary(
        self,
        report_json_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, float]:
        """
        Parse a pytest JSON report and return a summary dict.

        :param report_json_path: Path to the JSON report file.
        :return: Summary with keys: passed, failed, total, ratio_passed,
                 ratio_failed, percent_passed, percent_failed.
        """
        if report_json_path is None:
            warnings.warn("No pytest JSON report path provided")
            return self._get_empty_summary()

        try:
            with open(report_json_path, "r", encoding="utf-8") as f:
                json_plugin_report_data = json.load(f)
        except Exception as err:
            warnings.warn(
                f"Could not load pytest report from {report_json_path}: {err}"
            )
            return self._get_empty_summary()

        summary = json_plugin_report_data.get("summary", {})
        passed_tests = summary.get("passed", 0)
        failed_tests = summary.get("failed", 0)
        error_count = summary.get("errors", 0)
        collected_tests = summary.get("collected", 0)
        total_tests = summary.get("total", 0)

        if total_tests > 0:
            ratio_passed = passed_tests / total_tests
            ratio_failed = failed_tests / total_tests
        elif collected_tests > 0 or error_count > 0:
            # pytest collected (or tried to collect) tests but none ran —
            # this means a collection-phase error (ImportError, SyntaxError, etc.)
            # The student's code is broken; assign 0%.
            warnings.warn(
                f"Collection error in {report_json_path!r} "
                f"({collected_tests} item(s) attempted, {error_count} error(s), "
                f"0 tests ran). Assigning 0% for this suite.",
                RuntimeWarning,
            )
            ratio_passed = 0.0
            ratio_failed = 1.0
        else:
            # Truly empty suite (no tests discovered at all) — not an error.
            warnings.warn(
                f"No tests found in {report_json_path!r}. "
                f"Assigning a perfect grade (100%) for this suite.",
                RuntimeWarning,
            )
            ratio_passed = 1.0
            ratio_failed = 0.0

        percent_passed = 100.0 * ratio_passed
        percent_failed = 100.0 * ratio_failed

        return {
            "passed": passed_tests,
            "failed": failed_tests,
            "total": total_tests,
            "ratio_passed": ratio_passed,
            "ratio_failed": ratio_failed,
            "percent_passed": percent_passed,
            "percent_failed": percent_failed,
        }

    def _get_empty_summary(self) -> Dict[str, float]:
        """Return a default empty test summary."""
        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "ratio_passed": self.DEFAULT_PASSED_RATIO_ZERO_TESTS,
            "ratio_failed": 1.0 - self.DEFAULT_PASSED_RATIO_ZERO_TESTS,
            "percent_passed": 0.0,
            "percent_failed": 100.0,
        }

    def get_pep8_score(self) -> float:
        """
        Compute the average PEP8 compliance score for code_src and supp_tests_src.

        :return: Average PEP8 compliance percentage (0-100).
        :rtype: float
        """
        src_test_case = PEP8TestCase(self.PEP8_KEY, self.code_src.local_path)
        src_result = src_test_case.run()

        supp_local = (
            self.supp_tests_src.local_path if self.supp_tests_src is not None else None
        )
        # Fall back to code_src if supp_tests is not available
        if not supp_local or not os.path.isdir(supp_local):
            supp_local = self.code_src.local_path
        tests_test_case = PEP8TestCase(self.PEP8_KEY, supp_local)
        tests_result = tests_test_case.run()

        with open(self.pep8_errors_path, "w", encoding="utf-8") as f:
            if src_result.message:
                f.write("=== SOURCE CODE PEP8 ERRORS ===\n")
                f.write(f"Score: {src_result.percent_value:.2f}%\n")
                f.write(src_result.message + "\n\n")

            if tests_result.message:
                f.write("=== TEST CODE PEP8 ERRORS ===\n")
                f.write(f"Score: {tests_result.percent_value:.2f}%\n")
                f.write(tests_result.message + "\n\n")

        average_score = (src_result.percent_value + tests_result.percent_value) / 2.0
        return average_score

    def clear_pycache(self) -> None:
        """Remove __pycache__, .pytest_cache, and .pyc files from the report directory."""
        utils.rm_pycache(self.report_dir)
        utils.rm_pytest_cache(self.report_dir)
        utils.rm_pyc_files(self.report_dir)

    def clear_pytest_temporary_files(self) -> None:
        """Remove pytest temporary files and caches."""
        self.clear_pycache()

    def clear_temporary_files(self) -> None:
        """Remove all temporary files for all sources."""
        for src in self.all_sources:
            src.clear_temporary_files()

    def push_report_to(
        self,
        push_report_to: Optional[str] = "auto",
        **kwargs,
    ) -> "Tester":
        """
        Push the generated report to a remote git repository.

        :param push_report_to: The remote URL or "auto" to auto-detect.
        :param kwargs: Additional keyword arguments.
        :return: The current instance.
        """
        if push_report_to is None or push_report_to == "auto":
            push_report_to = self.kwargs.get("push_report_to", push_report_to)

        if push_report_to is None or push_report_to == "auto":
            self.logging_func(
                f"Auto-detecting git repo URL from {self.code_src.working_dir}"
            )
            push_report_to = utils.get_git_repo_url(self.code_src.working_dir)

        if push_report_to is None:
            warnings.warn(
                f"Could not detect git repo URL from {self.code_src.working_dir}. "
                f"Report will not be pushed.",
                RuntimeWarning,
            )
            return self

        kwargs.setdefault("local_tmp_path", os.path.join(self.report_dir, "tmp_repo"))

        self.report.save(self.report_filepath)
        utils.push_file_to_git_repo(self.report_filepath, push_report_to, **kwargs)

        self.logging_func(f"✓ Report pushed to {push_report_to}")
        return self

    def rm_report_dir(self) -> "Tester":
        """Remove the report directory and its contents."""
        try:
            from git import rmtree as git_rmtree

            rmtree_func = git_rmtree
        except ImportError:
            rmtree_func = shutil.rmtree

        if os.path.exists(self.report_dir):
            rmtree_func(self.report_dir)
            self.logging_func(f"✓ Removed report directory: {self.report_dir}")

        return self

    def __repr__(self) -> str:
        return (
            f"Tester("
            f"code={self.code_src.local_path}, "
            f"supp_tests={self.supp_tests_src.local_path}, "
            f"report={self.report_filepath}"
            f")"
        )
