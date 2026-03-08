"""
Pytest configuration for base tests.

Adds the src/ directory to sys.path so test files can import student code.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
