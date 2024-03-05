import os
import warnings
from typing import List

import numpy as np
import pycodestyle


class TestResult:
    def __init__(
            self,
            name: str,
            percent_value: float,
            message: str = "",
    ):
        self.name = name
        self.percent_value = percent_value
        self.message = message

    def __str__(self):
        _str = f'[{self.name}: {self.percent_value:.2f} %'
        if self.message:
            _str += f', ({self.message})'
        _str += ']'
        return _str


class TestCase:
    def __init__(self, name: str, weight: float = 1.0, **kwargs):
        self.name = name
        self.weight = weight
        self.kwargs = kwargs

    def run(self) -> TestResult:
        pass


class PEP8TestCase(TestCase):
    MAX_LINE_LENGTH = 120
    
    def __init__(self, name: str, files_dir: str, **kwargs):
        super().__init__(name, **kwargs)
        self.files_dir = files_dir
    
    def run(self):
        pep8style = pycodestyle.StyleGuide(ignore="W191,E501", max_line_length=self.MAX_LINE_LENGTH, quiet=True)
        result = pep8style.check_files([self.files_dir])
        message = ', '.join(set([f"{key}:'{err_msg}'" for key, err_msg in result.messages.items()]))
        if result.counters['physical lines'] == 0:
            err_ratio = 0.0
        else:
            err_ratio = result.total_errors / result.counters['physical lines']
        percent_value = np.clip(100.0 - (err_ratio * 100.0), 0.0, 100.0).item()
        return TestResult(self.name, percent_value, message=message)


class CheckNotAllowedLibrariesTestCase(TestCase):
    def __init__(self, name: str, path: str, not_allowed_libraries: List[str], **kwargs):
        super().__init__(name, **kwargs)
        self.path = path
        self.not_allowed_libraries = not_allowed_libraries
        self._warnings = set()
        self._excluded_files = kwargs.get("excluded_files", [])
        self._excluded_folders = kwargs.get("excluded_folders", [])

    def check_file(self, file_path: str) -> bool:
        with open(file_path, "r") as f:
            file_content = f.read()
        check = True
        for lib in self.not_allowed_libraries:
            if f"import {lib}" in file_content:
                self._warnings.add(f"The library '{lib}' is not allowed.")
                check = False
        return check

    def gather_files(self) -> List[str]:
        r"""
        Check if self.path is a file or a folder. If it is a file, return a list with only self.path. If it is a
        folder, return all the files in the folder and its subfolders.
        """
        if os.path.isfile(self.path):
            return [self.path]
        elif os.path.isdir(self.path):
            files = []
            for root, dirs, filenames in os.walk(self.path):
                if any([
                    os.path.normpath(excluded_folder) in os.path.normpath(root)
                    for excluded_folder in self._excluded_folders
                ]):
                    continue
                for filename in filenames:
                    if filename.endswith(".py") and filename not in self._excluded_files:
                        files.append(os.path.join(root, filename))
            return files
        else:
            raise ValueError(f"Invalid path: '{self.path}'.")

    def run(self):
        files = self.gather_files()
        score = 100.0
        message = ""
        for file_path in files:
            if not self.check_file(file_path):
                score = 0.0
        if self._warnings:
            warnings.warn(f"{self.name}: {' & '.join(self._warnings)}", RuntimeWarning)
            message = f"Warnings: {' & '.join(self._warnings)}"
        return TestResult(self.name, score, message=message)
