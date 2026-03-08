"""
Performance test cases module for code quality testing.

This module provides test cases for PEP8 compliance checking
using pycodestyle.
"""

from typing import Optional

import numpy as np
import pycodestyle


class TestResult:
    """
    Represents the result of a test case.

    Includes test name, percentage value, and an optional message.

    :ivar str name: The name of the test.
    :ivar float percent_value: The percentage value representing the test result (0-100).
    :ivar str message: An optional message describing the result.
    """

    def __init__(self, name: str, percent_value: float, message: str = ""):
        """
        Initialize a TestResult.

        :param name: The name of the test.
        :type name: str
        :param percent_value: The percentage value of the test result (0-100).
        :type percent_value: float
        :param message: An optional message describing the result.
        :type message: str
        """
        self.name = name
        self.percent_value = percent_value
        self.message = message

    def __str__(self) -> str:
        """
        Return a string representation of the TestResult.

        :return: String representation of the test result in format [name: value%, (message)].
        :rtype: str
        """
        result_str = f"[{self.name}: {self.percent_value:.2f}%"
        if self.message:
            result_str += f", ({self.message})"
        result_str += "]"
        return result_str

    def __repr__(self) -> str:
        """
        Return a detailed string representation of the TestResult.

        :return: Detailed string representation.
        :rtype: str
        """
        return (
            f"TestResult(name='{self.name}', " f"percent_value={self.percent_value:.2f}, " f"message='{self.message}')"
        )


class TestCase:
    """
    Abstract base class for a test case.

    Subclasses should implement the :meth:`run` method to execute
    the test and return a :class:`TestResult`.

    :cvar run: Execute the test and return the result.
    :vartype run: Callable[[], TestResult]
    """

    def run(self) -> TestResult:
        """
        Execute the test case.

        This method must be implemented by subclasses.

        :raises NotImplementedError: If the method is not implemented by a subclass.
        :return: The result of the test case.
        :rtype: TestResult
        """
        raise NotImplementedError(f"{self.__class__.__name__}.run() must be implemented by subclasses")


class PEP8TestCase(TestCase):
    """
    Test case for checking PEP8 compliance using pycodestyle.

    Checks Python code for style guide violations according to PEP8,
    with configurable maximum line length and ignored error codes.

    :ivar int MAX_LINE_LENGTH: The maximum allowed line length for PEP8 checks.
    :ivar str DEFAULT_IGNORE: Default error codes to ignore.
    :ivar str name: The name of the test case.
    :ivar str files_dir: The directory containing files to check.
    :ivar int max_line_length: Maximum line length for this instance.
    :ivar str ignore: Error codes to ignore for this instance.
    """

    MAX_LINE_LENGTH = 120
    DEFAULT_IGNORE = None  # W191: indentation contains tabs, E501: line too long

    def __init__(
        self,
        name: str,
        files_dir: str,
        max_line_length: Optional[int] = None,
        ignore: Optional[str] = None,
    ):
        """
        Initialize a PEP8TestCase.

        :param name: The name of the test case.
        :type name: str
        :param files_dir: The directory containing files to check for PEP8 compliance.
        :type files_dir: str
        :param max_line_length: Maximum line length. Defaults to MAX_LINE_LENGTH.
        :type max_line_length: Optional[int]
        :param ignore: Comma-separated error codes to ignore. Defaults to DEFAULT_IGNORE.
        :type ignore: Optional[str]
        """
        self.name = name
        self.files_dir = files_dir
        self.max_line_length = max_line_length or self.MAX_LINE_LENGTH
        self.ignore = ignore or self.DEFAULT_IGNORE

    def run(self) -> TestResult:
        """
        Run the PEP8 compliance test using pycodestyle.

        Analyzes the code in files_dir and computes a compliance score
        based on the ratio of errors to lines of code. The score is
        calculated as: 100 - (errors/lines * 100), clamped to [0, 100].

        :return: The result of the PEP8 compliance test with:
            - name: The test case name
            - percent_value: Compliance percentage (100 = perfect, 0 = many errors)
            - message: Summary of error types found
        :rtype: TestResult
        """
        pep8style = pycodestyle.StyleGuide(
            ignore=self.ignore,
            max_line_length=self.max_line_length,
            quiet=True,
        )

        result = pep8style.check_files([self.files_dir])

        # Create message from unique error types
        error_counts = {
            code: count for code, count in result.counters.items() if code not in {"physical lines"} and count
        }
        message = ", ".join(f"{code}:{count}" for code, count in sorted(error_counts.items()))

        physical_lines = result.counters.get("physical lines", 0)

        if physical_lines == 0:
            err_ratio = 0.0
        else:
            err_ratio = result.total_errors / physical_lines

        # Convert to percentage (100% = no errors, 0% = error on every line)
        percent_value = np.clip(100.0 - (err_ratio * 100.0), 0.0, 100.0).item()

        return TestResult(self.name, percent_value, message=message)

    def __repr__(self) -> str:
        """
        Return a string representation of the PEP8TestCase.

        :return: String representation.
        :rtype: str
        """
        return (
            f"PEP8TestCase(name='{self.name}', "
            f"files_dir='{self.files_dir}', "
            f"max_line_length={self.max_line_length}, "
            f"ignore='{self.ignore}')"
        )
