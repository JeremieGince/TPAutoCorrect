import numpy as np
import pycodestyle


class TestResult:
    """
    Represents the result of a test case, including its name, percentage value, and an optional message.

    :ivar str name: The name of the test.
    :ivar float percent_value: The percentage value representing the test result.
    :ivar str message: An optional message describing the result.
    """

    def __init__(self, name: str, percent_value: float, message: str = ""):
        """
        Initialize a TestResult.

        :param str name: The name of the test.
        :param float percent_value: The percentage value of the test result.
        :param str message: An optional message describing the result.
        """
        self.name = name
        self.percent_value = percent_value
        self.message = message

    def __str__(self):
        """
        Return a string representation of the TestResult.

        :return: String representation of the test result.
        :rtype: str
        """
        _str = f"[{self.name}: {self.percent_value:.2f} %"
        if self.message:
            _str += f", ({self.message})"
        _str += "]"
        return _str


class TestCase:
    """
    Abstract base class for a test case.

    Subclasses should implement the :meth:`run` method to execute the test and return a :class:`TestResult`.

    :cvar run: Execute the test and return the result.
    :vartype run: Callable[[], TestResult]
    """

    def run(self) -> TestResult:
        """
        Execute the test case.

        :raises NotImplementedError: If the method is not implemented by a subclass.
        :return: The result of the test case.
        :rtype: TestResult
        """
        raise NotImplementedError


class PEP8TestCase(TestCase):
    """
    Test case for checking PEP8 compliance using pycodestyle.

    :cvar int MAX_LINE_LENGTH: The maximum allowed line length for PEP8 checks.
    :ivar str name: The name of the test case.
    :ivar str files_dir: The directory containing files to check.
    """

    MAX_LINE_LENGTH = 120

    def __init__(self, name: str, files_dir: str):
        """
        Initialize a PEP8TestCase.

        :param str name: The name of the test case.
        :param str files_dir: The directory containing files to check for PEP8 compliance.
        """
        self.name = name
        self.files_dir = files_dir

    def run(self):
        """
        Run the PEP8 compliance test using pycodestyle.

        :return: The result of the PEP8 compliance test.
        :rtype: TestResult
        """
        pep8style = pycodestyle.StyleGuide(ignore="W191,E501", max_line_length=self.MAX_LINE_LENGTH, quiet=True)
        result = pep8style.check_files([self.files_dir])
        message = ", ".join(set([f"{key}:'{err_msg}'" for key, err_msg in result.messages.items()]))
        if result.counters["physical lines"] == 0:
            err_ratio = 0.0
        else:
            err_ratio = result.total_errors / result.counters["physical lines"]
        percent_value = np.clip(100.0 - (err_ratio * 100.0), 0.0, 100.0).item()
        return TestResult(self.name, percent_value, message=message)
