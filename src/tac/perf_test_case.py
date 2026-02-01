import numpy as np
import pycodestyle


class TestResult:
    """
    Represents the result of a test case, including its name, percentage value, and an optional message.

    Attributes:
        name (str): The name of the test.
        percent_value (float): The percentage value representing the test result.
        message (str): An optional message describing the result.
    """

    def __init__(self, name: str, percent_value: float, message: str = ""):
        """
        Initialize a TestResult.

        Args:
            name (str): The name of the test.
            percent_value (float): The percentage value of the test result.
            message (str, optional): An optional message describing the result.
        """
        self.name = name
        self.percent_value = percent_value
        self.message = message

    def __str__(self):
        """
        Return a string representation of the TestResult.

        Returns:
            str: String representation of the test result.
        """
        _str = f"[{self.name}: {self.percent_value:.2f} %"
        if self.message:
            _str += f", ({self.message})"
        _str += "]"
        return _str


class TestCase:
    """
    Abstract base class for a test case.

    Subclasses should implement the run() method to execute the test and return a TestResult.

    Methods:
        run() -> TestResult: Execute the test and return the result.
    """

    def run(self) -> TestResult:
        """
        Execute the test case.

        Returns:
            TestResult: The result of the test case.

        Raises:
            NotImplementedError: If the method is not implemented by a subclass.
        """
        raise NotImplementedError


class PEP8TestCase(TestCase):
    """
    Test case for checking PEP8 compliance using pycodestyle.

    Attributes:
        MAX_LINE_LENGTH (int): The maximum allowed line length for PEP8 checks.
        name (str): The name of the test case.
        files_dir (str): The directory containing files to check.
    """

    MAX_LINE_LENGTH = 120

    def __init__(self, name: str, files_dir: str):
        """
        Initialize a PEP8TestCase.

        Args:
            name (str): The name of the test case.
            files_dir (str): The directory containing files to check for PEP8 compliance.
        """
        self.name = name
        self.files_dir = files_dir

    def run(self):
        """
        Run the PEP8 compliance test using pycodestyle.

        Returns:
            TestResult: The result of the PEP8 compliance test.
        """
        pep8style = pycodestyle.StyleGuide(
            ignore="W191,E501", max_line_length=self.MAX_LINE_LENGTH, quiet=True
        )
        result = pep8style.check_files([self.files_dir])
        message = ", ".join(
            set([f"{key}:'{err_msg}'" for key, err_msg in result.messages.items()])
        )
        if result.counters["physical lines"] == 0:
            err_ratio = 0.0
        else:
            err_ratio = result.total_errors / result.counters["physical lines"]
        percent_value = np.clip(100.0 - (err_ratio * 100.0), 0.0, 100.0).item()
        return TestResult(self.name, percent_value, message=message)
