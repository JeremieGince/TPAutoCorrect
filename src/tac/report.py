"""
Report module for storing and computing graded test results.

This module provides the Report class for managing weighted metrics
and computing final grades.
"""

import json
import warnings
from typing import Any, Callable, Dict, Iterator, KeysView, List, Optional, Tuple

import numpy as np


class Report:
    """
    Class for storing and manipulating data for a grading report.

    Stores key-value pairs with associated weights, computes a weighted grade,
    supports normalization, and provides methods for saving/loading report state.

    .. note::
        ``grade_norm_func`` is not persisted by :meth:`save` / :meth:`load` because
        callables cannot be serialized to JSON.  It is restored to ``None`` on load
        and a :class:`UserWarning` is emitted if it was set before loading.

    :ivar dict data: The data stored in the report as {key: {VALUE_KEY: value, WEIGHT_KEY: weight}}.
    :ivar str report_filepath: The filepath to save or load the report.
    :ivar float score_min: Input weighted-sum value that maps to ``grade_floor`` (the zero-point).
    :ivar float grade_floor: Output grade when ``weighted_sum == score_min``.
    :ivar float score_max: Input weighted-sum ceiling (maps to 100 % output).
    :ivar Callable[[float], float] grade_norm_func: Optional function to normalize the grade.
    """

    VALUE_KEY = "value"
    WEIGHT_KEY = "weight"
    DEFAULT_SCORE_MIN = 0.0
    DEFAULT_SCORE_MAX = 100.0
    DEFAULT_GRADE_FLOOR = 0.0

    def __init__(
        self,
        data: Optional[Dict[str, Dict[str, float]]] = None,
        report_filepath: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize a Report instance.

        :param data: The data to store in the report. Each entry is {key: {VALUE_KEY: value, WEIGHT_KEY: weight}}.
        :type data: Optional[Dict[str, Dict[str, float]]]
        :param report_filepath: The filepath to save or load the report.
        :type report_filepath: Optional[str]
        :param kwargs: Additional keyword arguments including:
            - score_min (float): Input weighted-sum zero-point (maps to ``grade_floor``).
            - grade_floor (float): Output grade when ``weighted_sum == score_min``.
            - score_max (float): Input weighted-sum ceiling.
            - grade_norm_func (Callable[[float], float]): Optional function to normalize the grade.
              Note: grade_norm_func is not persisted by save()/load() because callables cannot be
              serialized to JSON. It will be silently restored to None on load().
        """
        self.data: Dict[str, Dict[str, float]] = data or {}
        self.report_filepath = report_filepath
        self.score_min: float = kwargs.pop("score_min", self.DEFAULT_SCORE_MIN)
        self.grade_floor: float = kwargs.pop("grade_floor", self.DEFAULT_GRADE_FLOOR)
        self.score_max: float = kwargs.pop("score_max", self.DEFAULT_SCORE_MAX)
        self.grade_norm_func: Optional[Callable[[float], float]] = kwargs.pop(
            "grade_norm_func", None
        )

    @property
    def grade(self) -> float:
        """
        Compute and return the weighted grade for the report.

        :return: The computed grade.
        :rtype: float
        """
        return self.get_grade()

    @property
    def is_normalized(self) -> bool:
        """
        Check if the sum of weights is approximately 1.0.

        :return: True if weights sum to 1.0 (within numerical tolerance), False otherwise.
        :rtype: bool
        """
        total_weight: float = sum(
            (self.get_weight(k) or 0.0)
            for k in self.keys()  # type: ignore[misc]
        )
        return bool(np.isclose(total_weight, 1.0))

    def get_state(self) -> Dict[str, Any]:
        """
        Get the current state of the report as a dictionary.

        Note: ``grade_norm_func`` is intentionally excluded — callables cannot be
        serialized to JSON and will be restored to ``None`` on :meth:`load`.

        :return: The state of the report including grade, data, and configuration.
        :rtype: Dict[str, Any]
        """
        return {
            "grade": self.grade,
            "data": self.data,
            "report_filepath": self.report_filepath,
            "score_min": self.score_min,
            "grade_floor": self.grade_floor,
            "score_max": self.score_max,
        }

    def set_state(self, state: Dict[str, Any]) -> None:
        """
        Set the state of the report from a dictionary.

        Note: ``grade_norm_func`` cannot be restored from a saved state because
        callables are not JSON-serializable. If the instance had a norm func before
        this call, a warning is issued and it is reset to ``None``.

        :param state: The state dictionary to restore.
        :type state: Dict[str, Any]
        """
        if self.grade_norm_func is not None:
            warnings.warn(
                "grade_norm_func is not persisted in the saved state and will be "
                "reset to None after load(). Re-assign it manually if needed.",
                UserWarning,
                stacklevel=2,
            )
        self.data = state["data"]
        self.report_filepath = state["report_filepath"]
        self.score_min = state.get("score_min", self.DEFAULT_SCORE_MIN)
        self.grade_floor = state.get("grade_floor", self.DEFAULT_GRADE_FLOOR)
        self.score_max = state.get("score_max", self.DEFAULT_SCORE_MAX)
        self.grade_norm_func = None

    def add(self, key: str, value: float, weight: float = 1.0) -> None:
        """
        Add a key-value pair with a weight to the report.

        :param key: The key to add.
        :type key: str
        :param value: The value to associate with the key.
        :type value: float
        :param weight: The weight for the value. Defaults to 1.0.
        :type weight: float
        """
        self.data[key] = {self.VALUE_KEY: value, self.WEIGHT_KEY: weight}

    def get(self, key: str, default: Any = None) -> Optional[Dict[str, float]]:
        """
        Get the value dictionary for a key.

        :param key: The key to retrieve.
        :type key: str
        :param default: The default value if key is not found.
        :type default: Any
        :return: The value dictionary {VALUE_KEY: value, WEIGHT_KEY: weight} or default.
        :rtype: Optional[Dict[str, float]]
        """
        return self.data.get(key, default)

    def get_value(self, key: str, default: Any = None) -> Optional[float]:
        """
        Get the value associated with a key.

        :param key: The key to retrieve.
        :type key: str
        :param default: The default value if key is not found.
        :type default: Any
        :return: The value or default.
        :rtype: Optional[float]
        """
        entry = self.get(key)
        if entry is None:
            return default
        return entry[self.VALUE_KEY]

    def get_weight(self, key: str, default: Any = None) -> Optional[float]:
        """
        Get the weight associated with a key.

        :param key: The key to retrieve.
        :type key: str
        :param default: The default value if key is not found.
        :type default: Any
        :return: The weight or default.
        :rtype: Optional[float]
        """
        entry = self.get(key)
        if entry is None:
            return default
        return entry[self.WEIGHT_KEY]

    def get_weighted(self, key: str, default: Any = None) -> Optional[float]:
        """
        Get the weighted value for a key (value * weight).

        :param key: The key to retrieve.
        :type key: str
        :param default: The default value if key is not found.
        :type default: Any
        :return: The weighted value, or None if value or weight is missing.
        :rtype: Optional[float]
        """
        value = self.get_value(key, default)
        weight = self.get_weight(key, default)

        if value is None or weight is None:
            return None

        return value * weight

    def get_item(
        self, key: str, default: Any = None
    ) -> Tuple[str, Optional[Dict[str, float]]]:
        """
        Get a tuple of (key, value dictionary).

        :param key: The key to retrieve.
        :type key: str
        :param default: The default value if key is not found.
        :type default: Any
        :return: Tuple of (key, value dictionary).
        :rtype: Tuple[str, Optional[Dict[str, float]]]
        """
        return key, self.get(key, default)

    def keys(self) -> KeysView:
        """
        Get all keys in the report data.

        :return: The keys of the data dictionary.
        :rtype: KeysView
        """
        return self.data.keys()

    def __getitem__(self, item: str) -> Dict[str, float]:
        """
        Get the value dictionary for a key using indexing.

        :param item: The key to retrieve.
        :type item: str
        :return: The value dictionary.
        :rtype: Dict[str, float]
        :raises KeyError: If the key doesn't exist.
        """
        return self.data[item]

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Set a key-value pair using indexing.

        Accepts either a tuple (value, weight) or just a value (weight defaults to 1.0).

        :param key: The key to set.
        :type key: str
        :param value: Either a tuple (value, weight) or just the value.
        :type value: Any
        """
        if isinstance(value, tuple):
            if len(value) != 2:
                raise ValueError("value tuple must be (value, weight)")
            self.data[key] = {self.VALUE_KEY: value[0], self.WEIGHT_KEY: value[1]}
        else:
            self.add(key, value, weight=1.0)

    def normalize_weights_(self) -> "Report":
        """
        Normalize the weights of all entries so that their sum is 1.0 (in-place).

        :return: The current instance with normalized weights.
        :rtype: Report
        """
        total_weight: float = sum(
            (self.get_weight(k) or 0.0)
            for k in self.keys()  # type: ignore[misc]
        )

        if total_weight == 0:
            raise ValueError("Cannot normalize when total weight is zero")

        for k in self.keys():
            w = self.get_weight(k)
            self.data[k][self.WEIGHT_KEY] = (w if w is not None else 0.0) / total_weight

        return self

    def get_normalized(self) -> "Report":
        """
        Return a new Report instance with normalized weights.

        :return: A new Report with normalized weights.
        :rtype: Report
        :raises ValueError: If total weight is zero.
        """
        total_weight: float = sum(
            (self.get_weight(k) or 0.0)
            for k in self.keys()  # type: ignore[misc]
        )

        if total_weight == 0:
            raise ValueError("Cannot normalize when total weight is zero")

        normalized_data: Dict[str, Dict[str, float]] = {
            k: {
                self.VALUE_KEY: self.get_value(k) or 0.0,
                self.WEIGHT_KEY: (self.get_weight(k) or 0.0) / total_weight,
            }
            for k in self.keys()
        }

        return Report(
            data=normalized_data,
            report_filepath=self.report_filepath,
            score_min=self.score_min,
            grade_floor=self.grade_floor,
            score_max=self.score_max,
            grade_norm_func=self.grade_norm_func,
        )

    def get_grade(self) -> float:
        """
        Compute the weighted grade for the report.

        The grade is computed by:
        1. Normalizing weights if not already normalized
        2. Computing weighted sum of all values (scaled to 0-100)
        3. Clamping to grade_floor: if weighted_sum < grade_floor, return grade_floor
        4. Optionally applying grade_norm_func if provided

        Formula::

            weighted_sum = sum(value_i * weight_i)   # after weight normalisation
            grade = max(grade_floor, weighted_sum)

        With the default ``grade_floor=0`` this degenerates to the raw weighted
        sum (0-100).  With e.g. ``grade_floor=40`` a student who scores below 40
        receives exactly 40; a student who scores above 40 receives their actual
        score unchanged.

        :return: The computed grade.
        :rtype: float
        """
        if not self.keys():
            return self.grade_floor

        if self.is_normalized:
            report = self
        else:
            report = self.get_normalized()

        # Compute weighted sum (values are expected to be in 0-100 range)
        weighted: List[float] = [
            w for k in report.keys() for w in (report.get_weighted(k),) if w is not None
        ]
        weighted_sum = sum(weighted)

        # Clamp to grade_floor
        grade = max(self.grade_floor, weighted_sum)

        # Apply normalization function if provided
        if self.grade_norm_func is not None:
            grade = self.grade_norm_func(grade)

        return grade

    def save(self, report_filepath: Optional[str] = None) -> str:
        """
        Save the report state to a JSON file.

        :param report_filepath: The filepath to save to. If None, uses the instance's filepath.
        :type report_filepath: Optional[str]
        :return: The filepath where the report was saved.
        :rtype: str
        :raises AssertionError: If no filepath is provided.
        """
        if report_filepath is not None:
            self.report_filepath = report_filepath

        if self.report_filepath is None:
            raise ValueError("report_filepath must be set before saving")

        with open(self.report_filepath, "w", encoding="utf-8") as f:
            json.dump(self.get_state(), f, indent=4)

        return self.report_filepath

    def load(self, report_filepath: Optional[str] = None) -> "Report":
        """
        Load the report state from a JSON file.

        :param report_filepath: The filepath to load from. If None, uses the instance's filepath.
        :type report_filepath: Optional[str]
        :return: The current instance with loaded state.
        :rtype: Report
        :raises ValueError: If no filepath is provided.
        :raises FileNotFoundError: If the file doesn't exist.
        """
        if report_filepath is not None:
            self.report_filepath = report_filepath

        if self.report_filepath is None:
            raise ValueError("report_filepath must be set before loading")

        with open(self.report_filepath, "r", encoding="utf-8") as f:
            state = json.load(f)

        self.set_state(state)
        return self

    def __repr__(self) -> str:
        """
        Return a string representation of the Report.

        :return: String representation.
        :rtype: str
        """
        return (
            f"{self.__class__.__name__}("
            f"grade={self.grade:.2f}, "
            f"data={self.data}, "
            f"report_filepath={self.report_filepath}"
            f")"
        )

    def __str__(self) -> str:
        """
        Return a JSON string representation of the Report.

        :return: JSON string representation.
        :rtype: str
        """
        json_str = json.dumps(self.get_state(), indent=4)
        return f"{self.__class__.__name__}({json_str})"

    def __len__(self) -> int:
        """
        Return the number of items in the report data.

        :return: Number of items.
        :rtype: int
        """
        return len(self.data)

    def __iter__(self) -> Iterator:
        """
        Return an iterator over the report data keys.

        :return: Iterator over keys.
        :rtype: Iterator
        """
        return iter(self.data)

    def __contains__(self, item: str) -> bool:
        """
        Check if a key is in the report data.

        :param item: The key to check.
        :type item: str
        :return: True if key is in data, False otherwise.
        :rtype: bool
        """
        return item in self.data
