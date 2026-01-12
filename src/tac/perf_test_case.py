import numpy as np
import pycodestyle


class TestResult:
    def __init__(self, name: str, percent_value: float, message: str = ""):
        self.name = name
        self.percent_value = percent_value
        self.message = message

    def __str__(self):
        _str = f"[{self.name}: {self.percent_value:.2f} %"
        if self.message:
            _str += f", ({self.message})"
        _str += "]"
        return _str


class TestCase:
    def run(self) -> TestResult:
        pass


class PEP8TestCase(TestCase):
    MAX_LINE_LENGTH = 120

    def __init__(self, name: str, files_dir: str):
        self.name = name
        self.files_dir = files_dir

    def run(self):
        pep8style = pycodestyle.StyleGuide(ignore="W191,E501", max_line_length=self.MAX_LINE_LENGTH, quiet=True)
        result = pep8style.check_files([self.files_dir])
        message = ", ".join(set([f"{key}:'{err_msg}'" for key, err_msg in result.messages.items()]))
        if result.counters["physical lines"] == 0:
            err_ratio = 0.0
        else:
            err_ratio = result.total_errors / result.counters["physical lines"]
        percent_value = np.clip(100.0 - (err_ratio * 100.0), 0.0, 100.0).item()
        return TestResult(self.name, percent_value, message=message)
