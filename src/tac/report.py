import json
from typing import Callable, Optional

import numpy as np


class Report:
    """
    Class for storing and manipulating data for a report.

    Stores key-value pairs with associated weights, computes a weighted grade, supports normalization,
    and provides methods for saving/loading report state to/from a file.

    :ivar dict data: The data stored in the report.
    :ivar str report_filepath: The filepath to save or load the report.
    :ivar float grade_min: The minimum grade for the report.
    :ivar float grade_min_value: The value of the report when the grade is the minimum.
    :ivar float grade_max: The maximum grade for the report.
    :ivar Callable[[float], float] grade_norm_func: The function to use to normalize the grade.
    :ivar tuple args: Additional positional arguments.
    :ivar dict kwargs: Additional keyword arguments.
    """

    VALUE_KEY = "value"
    WEIGHT_KEY = "weight"
    DEFAULT_GRADE_MIN = 0.0
    DEFAULT_GRADE_MAX = 100.0
    DEFAULT_GRADE_MIN_VALUE = 0.0

    def __init__(
        self,
        data: Optional[dict] = None,
        report_filepath: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """
        Initialize a Report instance.

        :param dict data: The data to store in the report.
        :param str report_filepath: The filepath to save or load the report.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
            - grade_min (float, optional): The minimum grade for the report.
            - grade_min_value (float, optional): The value of the report when the grade is the minimum.
            - grade_max (float, optional): The maximum grade for the report.
            - grade_norm_func (Callable[[float], float], optional): The function to use to normalize the grade.
        """
        self.data = data
        self.report_filepath = report_filepath
        self.grade_min = kwargs.pop("grade_min", self.DEFAULT_GRADE_MIN)
        self.grade_min_value = kwargs.pop("grade_min_value", self.DEFAULT_GRADE_MIN_VALUE)
        self.grade_max = kwargs.pop("grade_max", self.DEFAULT_GRADE_MAX)
        self.grade_norm_func: Optional[Callable[[float], float]] = kwargs.pop("grade_norm_func", None)
        self.args = args
        self.kwargs = kwargs

        self._initialize_data_()

    @property
    def grade(self) -> float:
        """
        Compute and return the weighted grade for the report.

        :return float: The computed grade.
        """
        return self.get_grade()

    @property
    def is_normalized(self) -> bool:
        """
        Check if the sum of weights is (approximately) 1.0.

        :return bool: True if weights sum to 1.0, False otherwise.
        """
        return np.isclose(sum([self.get_weight(k) for k in self.keys()]), 1.0)

    def _initialize_data_(self):
        """
        Initialize the data dictionary if it is None.
        """
        if self.data is None:
            self.data = {}

    def get_state(self) -> dict:
        """
        Get the current state of the report as a dictionary.

        :return dict: The state of the report.
        """
        return {
            "grade": self.grade,
            "data": self.data,
            "report_filepath": self.report_filepath,
            "args": self.args,
            "kwargs": self.kwargs,
        }

    def set_state(self, state: dict):
        """
        Set the state of the report from a dictionary.

        :param dict state: The state to set.
        """
        self.data = state["data"]
        self.report_filepath = state["report_filepath"]
        self.args = state["args"]
        self.kwargs = state["kwargs"]

    def add(self, key, value, weight=1.0):
        """
        Add a key-value pair with a weight to the report.

        :param key: The key to add.
        :param value: The value to associate with the key.
        :param float weight: The weight for the value. Defaults to 1.0.
        """
        self.data[key] = {self.VALUE_KEY: value, self.WEIGHT_KEY: weight}

    def get(self, key, default=None):
        """
        Get the value dictionary for a key.

        :param key: The key to retrieve.
        :param default: The default value if key is not found.
        :return: dict or default. The value dictionary or default.
        """
        return self.data.get(key, default)

    def get_value(self, key, default=None):
        """
        Get the value associated with a key.

        :param key: The key to retrieve.
        :param default: The default value if key is not found.
        :return: value or default. The value or default.
        """
        value = self.get(key, default)
        if value is None:
            return value
        return value[self.VALUE_KEY]

    def get_weight(self, key, default=None):
        """
        Get the weight associated with a key.

        :param key: The key to retrieve.
        :param default: The default value if key is not found.
        :return float or default: The weight or default.
        """
        value = self.get(key, default)
        if value is None:
            return value
        return value[self.WEIGHT_KEY]

    def get_weighted(self, key, default=None):
        """
        Get the weighted value for a key (value * weight).

        :param key: The key to retrieve.
        :param default: The default value if key is not found.
        :return float or None: The weighted value, or None if value or weight is missing.
        """
        value = self.get_value(key, default)
        weight = self.get_weight(key, default)
        if value is None or weight is None:
            return None
        return value * weight

    def get_item(self, key, default=None):
        """
        Get a tuple of (key, value dictionary).

        :param key: The key to retrieve.
        :param default: The default value if key is not found.
        :return tuple: (key, value dictionary)
        """
        return key, self.get(key, default)

    def keys(self):
        """
        Get all keys in the report data.

        :return KeysView: The keys of the data dictionary.
        """
        return self.data.keys()

    def __getitem__(self, item):
        """
        Get the value dictionary for a key using indexing.

        :param item: The key to retrieve.
        :return dict: The value dictionary.
        """
        return self.data[item]

    def __setitem__(self, key, value, weight=1.0):
        """
        Set a key-value pair with a weight using indexing.

        :param key: The key to set.
        :param value: The value to associate with the key.
        :param float weight: The weight for the value. Defaults to 1.0.
        """
        if isinstance(value, tuple):
            assert len(value) == 2, "value must be a tuple of length 2"
            self.data[key] = value
        else:
            self.data[key] = (value, weight)

    def normalize_weights_(self) -> "Report":
        """
        Normalize the weights of all entries so that their sum is 1.0.

        :return Report: The current instance with normalized weights.
        """
        total_weight = sum([self.get_weight(k) for k in self.keys()])
        for k in self.keys():
            self.data[k][self.WEIGHT_KEY] = self.get_weight(k) / total_weight  # type: ignore
        return self

    def get_normalized(self) -> "Report":
        """
        Return a new Report instance with normalized weights.

        :return Report: A new Report with normalized weights.
        """
        total_weight = sum([self.get_weight(k) for k in self.keys()])
        return Report(
            {
                k: {
                    self.VALUE_KEY: self.get_value(k),
                    self.WEIGHT_KEY: self.get_weight(k) / total_weight,
                }
                for k in self.keys()
            }
        )

    def get_grade(self) -> float:
        """
        Compute the weighted grade for the report.

        :return float: The computed grade.
        """
        if self.is_normalized:
            report = self
        else:
            report = self.get_normalized()
        grade = sum([report.get_weighted(k) for k in report.keys()])
        grade_scale = self.grade_max - self.grade_min
        grade = (self.grade_max - self.grade_min_value) * (grade - self.grade_min) / grade_scale + self.grade_min_value
        if self.grade_norm_func is not None:
            grade = self.grade_norm_func(grade)
        return grade

    def save(self, report_filepath: Optional[str] = None):
        """
        Save the report state to a JSON file.

        :param str report_filepath: The filepath to save to. If None, uses the instance's filepath.
        :return str: The filepath where the report was saved.
        """
        if report_filepath is not None:
            self.report_filepath = report_filepath
        assert self.report_filepath is not None, "report_filepath must be initialized before saving"
        with open(self.report_filepath, "w") as f:
            json.dump(self.get_state(), f, indent=4)
        return self.report_filepath

    def load(self, report_filepath: Optional[str] = None):
        """
        Load the report state from a JSON file.

        :param str report_filepath: The filepath to load from. If None, uses the instance's filepath.
        :return Report: The current instance with loaded state.
        """
        if report_filepath is not None:
            self.report_filepath = report_filepath
        assert self.report_filepath is not None, "report_filepath must be initialized before loading"
        with open(self.report_filepath, "r") as f:
            self.set_state(json.load(f))
        return self

    def __repr__(self):
        """
        Return a string representation of the Report.

        :return str: String representation.
        """
        return (
            f"{self.__class__.__name__}("
            f"grade={self.grade}, "
            f"data={self.data}, "
            f"report_filepath={self.report_filepath}"
            f")"
        )

    def __str__(self):
        """
        Return a JSON string representation of the Report.

        :return str: JSON string representation.
        """
        json_str = json.dumps(self.get_state(), indent=4)
        return f"{self.__class__.__name__}({json_str})"

    def __len__(self):
        """
        Return the number of items in the report data.

        :return int: Number of items.
        """
        return len(self.data)

    def __iter__(self):
        """
        Return an iterator over the report data keys.

        :return Iterator: Iterator over keys.
        """
        return iter(self.data)

    def __contains__(self, item):
        """
        Check if a key is in the report data.

        :param item: The key to check.
        :return bool: True if key is in data, False otherwise.
        """
        return item in self.data
