import json
import logging
import os
import shutil
import warnings
from copy import deepcopy
from typing import Dict, List, Optional

from . import utils
from .perf_test_case import PEP8TestCase
from .report import Report
from .source import SourceCode, SourceTests
from .utils import find_filepath, rm_pyc_files, rm_pycache, rm_pytest_cache


class Tester:
    """
    Tester class for running code and test evaluation, collecting metrics, and generating reports.

    Handles code coverage, test pass rates, PEP8 compliance, and supports both student and master test sources.
    """

    CODE_COVERAGE_KEY = "code_coverage"
    PERCENT_PASSED_KEY = "percent_passed"
    MASTER_PERCENT_PASSED_KEY = "master_percent_passed"
    PEP8_KEY = "PEP8"
    DEFAULT_WEIGHTS = {
        CODE_COVERAGE_KEY: 1.0,
        PERCENT_PASSED_KEY: 1.0,
        MASTER_PERCENT_PASSED_KEY: 1.0,
        PEP8_KEY: 1.0,
    }
    MASTER_TESTS_RENAME_PATTERN = "{}_master.py"
    DOT_JSON_REPORT_NAME = ".tmp_report.json"
    MASTER_DOT_JSON_REPORT_NAME = ".tmp_master_report.json"
    DEFAULT_REPORT_FILENAME = "report.json"
    DEFAULT_PASSED_RATIO_ZERO_TESTS = 0.0
    DEFAULT_LOGGING_FUNC = logging.info

    def __init__(
        self,
        code_src: Optional[SourceCode] = None,
        tests_src: Optional[SourceTests] = None,
        *,
        master_code_src: Optional[SourceCode] = None,
        master_tests_src: Optional[SourceTests] = None,
        report_kwargs: Optional[dict] = None,
        **kwargs,
    ):
        """
        Initialize the Tester.

        Args:
            code_src (Optional[SourceCode]): The source code to test.
            tests_src (Optional[SourceTests]): The test source.
            master_code_src (Optional[SourceCode], optional): Master code source for reference.
            master_tests_src (Optional[SourceTests], optional): Master test source for reference.
            report_kwargs (Optional[dict], optional): Additional arguments for the report.
            **kwargs: Additional keyword arguments for configuration.
        """
        if code_src is None:
            code_src = SourceCode()
        if tests_src is None:
            tests_src = SourceTests()
        self.code_src = code_src
        self.tests_src = tests_src
        self.master_code_src = master_code_src
        self.master_tests_src = master_tests_src
        self.kwargs = kwargs
        self.logging_func = kwargs.get("logging_func", self.DEFAULT_LOGGING_FUNC)

        self.test_cases_summary = None
        self.master_test_cases_summary = None
        self.report_dir = self.kwargs.get("report_dir")
        if self.report_dir is None:
            self.report_dir = os.path.join(os.getcwd(), "report_dir")
        self.report_filepath = self.kwargs.get(
            "report_filepath",
            os.path.join(self.report_dir, self.DEFAULT_REPORT_FILENAME),
        )
        report_kwargs = report_kwargs or {}
        self.report = Report(report_filepath=self.report_filepath, **report_kwargs)
        self.weights = self.kwargs.get("weights", self.DEFAULT_WEIGHTS)

    @property
    def dot_coverage_path(self):
        """
        Get the path to the temporary .coverage file.

        Returns:
            str or None: Path to the .coverage file, or None if not found.
        """
        return self._find_temp_filepath(".coverage")

    @property
    def coverage_json_path(self):
        """
        Get the path to the temporary coverage.json file.

        Returns:
            str or None: Path to the coverage.json file, or None if not found.
        """
        return self._find_temp_filepath("coverage.json")

    @property
    def coverage_xml_path(self):
        """
        Get the path to the temporary coverage.xml file.

        Returns:
            str or None: Path to the coverage.xml file, or None if not found.
        """
        return self._find_temp_filepath("coverage.xml")

    @property
    def dot_report_json_path(self):
        """
        Get the path to the temporary pytest JSON report file.

        Returns:
            str or None: Path to the .tmp_report.json file, or None if not found.
        """
        return self._find_temp_filepath(self.DOT_JSON_REPORT_NAME)

    @property
    def master_dot_report_json_path(self):
        """
        Get the path to the temporary master pytest JSON report file.

        Returns:
            str or None: Path to the .tmp_master_report.json file, or None if not found.
        """
        return self._find_temp_filepath(self.MASTER_DOT_JSON_REPORT_NAME)

    @property
    def temp_files(self):
        """
        List all temporary files used during testing.

        Returns:
            List[str]: List of temporary file paths.
        """
        tmp_files = [
            self.dot_coverage_path,
            self.coverage_json_path,
            self.coverage_xml_path,
            self.dot_report_json_path,
            self.master_dot_report_json_path,
        ]
        return [f for f in tmp_files if f is not None]

    def get_pytest_plugins_options(
        self,
        add_cov: bool = True,
        add_json_report: bool = True,
        json_report_file: Optional[str] = None,
        **kwargs,
    ):
        """
        Build the list of pytest command-line options for plugins.

        Args:
            add_cov (bool, optional): Whether to add coverage options. Defaults to True.
            add_json_report (bool, optional): Whether to add JSON report options. Defaults to True.
            json_report_file (Optional[str], optional): Name of the JSON report file.
            **kwargs: Additional keyword arguments.

        Returns:
            List[str]: List of pytest options.
        """
        options = []
        if add_cov:
            options += [
                f"--cov={self.code_src.local_path}",
                "--cov-report=json",
                "-p no:cacheprovider",
            ]
        if add_json_report:
            json_report_file = json_report_file or self.DOT_JSON_REPORT_NAME
            options += [
                "--json-report",
                f"--json-report-file={json_report_file}",
                "--json-report-summary",
                "--json-report-indent=4",
            ]
        return options

    @property
    def all_sources(self):
        """
        Get all source objects (code, tests, master code, master tests).

        Returns:
            List[Source]: List of all non-None source objects.
        """
        sources = [
            self.code_src,
            self.tests_src,
            self.master_code_src,
            self.master_tests_src,
        ]
        return [s for s in sources if s is not None]

    @property
    def is_setup(self):
        """
        Check if all sources are set up.

        Returns:
            bool: True if all sources are set up, False otherwise.
        """
        return all([s.is_setup for s in self.all_sources])

    def _find_temp_filepath(self, filename: str):
        """
        Find the path to a temporary file in the report directory or current working directory.

        Args:
            filename (str): The filename to search for.

        Returns:
            str or None: The path to the file, or None if not found.
        """
        roots = [self.report_dir, os.getcwd()]
        found_files = [find_filepath(filename, root=root) for root in roots]
        found_files = [f for f in found_files if f is not None] + [None]
        return found_files[0]

    def setup_at(self, **kwargs):
        """
        Set up all sources at the report directory.

        Args:
            **kwargs: Additional keyword arguments for setup.

        Returns:
            Tester: The current instance.
        """
        force = kwargs.pop("force_setup", False)
        debug = kwargs.get("debug", False)
        if self.is_setup and (not force):
            return self
        self.code_src.setup_at(self.report_dir, **kwargs)
        self.tests_src.setup_at(self.report_dir, **kwargs)
        if self.master_code_src is not None:
            self.master_code_src.setup_at(self.report_dir, **kwargs)
        if self.master_tests_src is not None:
            self.master_tests_src.setup_at(self.report_dir, **kwargs)
        if debug:
            self.logging_func(f"self.code_src: {self.code_src}")
            self.logging_func(f"self.tests_src: {self.tests_src}")
            self.logging_func(f"self.master_code_src: {self.master_code_src}")
            self.logging_func(f"self.master_tests_src: {self.master_tests_src}")
        return self

    def run(self, *args, **kwargs):
        """
        Run the full test and evaluation pipeline.

        Args:
            *args: Unused positional arguments.
            **kwargs: Additional keyword arguments for configuration.
        """
        self.weights.update(kwargs.pop("weights", {}))
        save_report = kwargs.pop("save_report", True)
        clear_pytest_temporary_files = kwargs.pop("clear_pytest_temporary_files", False)
        clear_temporary_files = kwargs.pop("clear_temporary_files", False)
        self.setup_at(**kwargs)
        self._run(**kwargs)
        if save_report:
            self.report.save(self.report_filepath)
        if clear_pytest_temporary_files:
            self.clear_pytest_temporary_files()
        if clear_temporary_files:
            self.clear_temporary_files()

    def _run(self, **kwargs):
        """
        Internal method to run pytest, collect metrics, and update the report.

        Args:
            **kwargs: Additional keyword arguments.
        """
        self.clear_pycache()
        self._run_pytest(**kwargs)
        self.report.add(
            self.CODE_COVERAGE_KEY,
            self.get_code_coverage(),
            weight=self.weights[self.CODE_COVERAGE_KEY],
        )
        self.test_cases_summary = deepcopy(self.get_test_cases_summary(self.dot_report_json_path))
        self.report.add(
            self.PERCENT_PASSED_KEY,
            self.test_cases_summary[self.PERCENT_PASSED_KEY],
            weight=self.weights[self.PERCENT_PASSED_KEY],
        )
        self.report.add(
            self.PEP8_KEY,
            self.get_pep8_score(),
            weight=self.weights[self.PEP8_KEY],
        )

        if self.master_tests_src is not None:
            self.master_tests_src.rename_test_files(pattern=self.MASTER_TESTS_RENAME_PATTERN)
            self._run_master_pytest(**kwargs)
            self.master_test_cases_summary = deepcopy(self.get_test_cases_summary(self.master_dot_report_json_path))
            self.report.add(
                self.MASTER_PERCENT_PASSED_KEY,
                self.master_test_cases_summary[self.PERCENT_PASSED_KEY],
                weight=self.weights[self.MASTER_PERCENT_PASSED_KEY],
            )

        self.clear_pycache()

    def _run_pytest(self, **kwargs):
        """
        Run pytest on the student's code and tests.

        Args:
            **kwargs: Additional keyword arguments.
        """
        options = self.get_pytest_plugins_options(
            add_cov=True,
            add_json_report=True,
            json_report_file=self.DOT_JSON_REPORT_NAME,
            **kwargs,
        )
        pytest_path = self.code_src.get_venv_module_path("pytest")
        cmd = f"{pytest_path} {' '.join(options)} {self.tests_src.local_path}"
        if kwargs.get("debug", False):
            self.logging_func(f"os.system: {cmd}")
        os.system(cmd)
        self.clear_pycache()
        self.move_temp_files_to_report_dir(**kwargs)

    def _run_master_pytest(self, **kwargs):
        """
        Run pytest on the master code and master tests.

        Args:
            **kwargs: Additional keyword arguments.
        """
        if self.master_code_src is None:
            return
        if self.master_tests_src is None:
            return
        options = self.get_pytest_plugins_options(
            add_cov=False,
            add_json_report=True,
            json_report_file=self.MASTER_DOT_JSON_REPORT_NAME,
            **kwargs,
        )
        pytest_path = self.master_code_src.get_venv_module_path("pytest")
        cmd = f"{pytest_path} {' '.join(options)} {self.master_tests_src.local_path}"
        if kwargs.get("debug", False):
            self.logging_func(f"os.system: {cmd}")
        os.system(cmd)
        self.clear_pycache()
        self.move_temp_files_to_report_dir(**kwargs)

    def get_code_coverage(self) -> float:
        """
        Compute the mean code coverage percentage using pytest-cov.

        Returns:
            float: Mean percent of code covered by tests.
        """
        try:
            coverage_file = utils.reindent_json_file(self.coverage_json_path)
            coverage_data: Dict[str, Dict[str, Dict[str, float]]] = json.load(open(coverage_file))
        except Exception as err:
            warnings.warn(f"Could not reindent or load {self.coverage_json_path=} -> {err}")
            return 0.0
        summaries: List[Dict[str, float]] = [  # type: ignore
            d["summary"]  # type: ignore
            for f, d in coverage_data["files"].items()
            if f.endswith(".py") and utils.is_subpath_in_path(self.code_src.local_path, f)  # type: ignore
        ]
        mean_percent_covered = sum([s["percent_covered"] for s in summaries]) / len(summaries)
        return mean_percent_covered

    def get_test_cases_summary(self, dot_report_json_path: Optional[str] = None):
        """
        Parse the pytest JSON report and summarize test results.

        Args:
            dot_report_json_path (Optional[str], optional): Path to the JSON report file.

        Returns:
            dict: Summary of test results (passed, failed, total, ratios, percentages).
        """
        dot_report_json_path = dot_report_json_path or self.dot_report_json_path
        json_plugin_report_data = json.load(open(dot_report_json_path))
        passed_tests = json_plugin_report_data["summary"].get("passed", 0)
        failed_tests = json_plugin_report_data["summary"].get("failed", 0)
        total_tests = json_plugin_report_data["summary"]["total"]
        if total_tests > 0:
            ratio_passed = passed_tests / total_tests
            ratio_failed = failed_tests / total_tests
        else:
            ratio_passed = self.DEFAULT_PASSED_RATIO_ZERO_TESTS
            ratio_failed = 1.0 - self.DEFAULT_PASSED_RATIO_ZERO_TESTS
        percent_passed = 100 * ratio_passed
        percent_failed = 100 * ratio_failed
        return {
            "passed": passed_tests,
            "failed": failed_tests,
            "total": total_tests,
            "ratio_passed": ratio_passed,
            "ratio_failed": ratio_failed,
            self.PERCENT_PASSED_KEY: percent_passed,
            "percent_failed": percent_failed,
        }

    def get_pep8_score(self):
        """
        Compute the average PEP8 compliance score for code and test sources.

        Returns:
            float: Average PEP8 compliance percentage.
        """
        src_test_case = PEP8TestCase(self.PEP8_KEY, self.code_src.local_path)
        src_test_case_result = src_test_case.run()
        tests_test_case = PEP8TestCase(self.PEP8_KEY, self.tests_src.local_path)
        tests_test_case_result = tests_test_case.run()
        return (src_test_case_result.percent_value + tests_test_case_result.percent_value) / 2.0

    def move_temp_files_to_report_dir(self, **kwargs):
        """
        Move temporary files to the report directory.

        Args:
            **kwargs: Additional keyword arguments.

        Returns:
            Tester: The current instance.
        """
        for f in self.temp_files:
            try:
                shutil.move(f, self.report_dir)
            except shutil.Error as e:
                if kwargs.get("debug", False):
                    self.logging_func(f"shutil.move({f},{self.report_dir}) -> raises: {e}")
        return self

    def clear_pycache(self):
        """
        Remove __pycache__, .pytest_cache, and .pyc files from the report directory.
        """
        rm_pycache(self.report_dir)
        rm_pytest_cache(self.report_dir)
        rm_pyc_files(self.report_dir)

    def clear_pytest_temporary_files(self):
        """
        Remove pytest temporary files and caches.
        """
        self.clear_pycache()
        for f in self.temp_files:
            utils.rm_file(f)

    def clear_temporary_files(self):
        """
        Remove all temporary files and caches for all sources.
        """
        self.clear_pytest_temporary_files()
        for src in self.all_sources:
            src.clear_temporary_files()

    def push_report_to(self, push_report_to: Optional[str] = "auto", **kwargs) -> "Tester":
        """
        Push the generated report to a remote git repository.

        Args:
            push_report_to (Optional[str], optional): The remote URL or "auto" to detect. Defaults to "auto".
            **kwargs: Additional keyword arguments.

        Returns:
            Tester: The current instance.
        """
        if push_report_to is None or push_report_to == "auto":
            push_report_to = self.kwargs.get("push_report_to", push_report_to)
        if push_report_to is None or push_report_to == "auto":
            self.logging_func(f"trying to detect git repo url from {self.code_src.working_dir}")
            push_report_to = utils.get_git_repo_url(
                self.code_src.working_dir,  # type: ignore
            )
        if push_report_to is None:
            warnings.warn(
                f"Could not detect git repo url from {push_report_to=} nor {self.code_src.working_dir}",
                RuntimeWarning,
            )
            return self
        kwargs.setdefault("local_tmp_path", os.path.join(self.report_dir, "tmp_repo"))  # type: ignore
        self.report.save(self.report_filepath)
        utils.push_file_to_git_repo(self.report_filepath, push_report_to, **kwargs)
        return self

    def rm_report_dir(self):
        """
        Remove the report directory and its contents.

        Returns:
            Tester: The current instance.
        """
        rmtree_func = shutil.rmtree
        try:
            from git import rmtree as git_rmtree

            rmtree_func = git_rmtree
        except ImportError:
            pass
        rmtree_func(self.report_dir)
        return self
