# TAC: TP Auto Correct

[![Star on GitHub](https://img.shields.io/github/stars/JeremieGince/TPAutoCorrect.svg?style=social)](https://github.com/JeremieGince/TPAutoCorrect/stargazers)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

![Tests Workflow](https://github.com/JeremieGince/TPAutoCorrect/actions/workflows/tests.yml/badge.svg)
![Dist Workflow](https://github.com/JeremieGince/TPAutoCorrect/actions/workflows/build_dist.yml/badge.svg)
![Code coverage](https://raw.githubusercontent.com/JeremieGince/TPAutoCorrect/coverage-badge/coverage.svg?raw=true)

Automated homework grading and testing framework for programming assignments. TAC runs student code against multiple test suites, measures code coverage, checks PEP8 compliance, and produces a weighted grade report — all from a single `Tester.run()` call.

# Installation

| Method     | Commands                                                                                                                                                                            |
|------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **PyPi**   | `pip install tac`                                                                                                                                                                   |
| **source** | `pip install git+https://github.com/JeremieGince/TPAutoCorrect`                                                                                                                     |
| **wheel**  | 1. Download the `.whl` file [here](https://github.com/JeremieGince/TPAutoCorrect/tree/main/dist);<br> 2. Copy the path of this file on your computer; <br> 3. `pip install [path].whl` |

### Last unstable version

To install the last unstable version, download the latest `.whl` file and follow the wheel instructions above.

# Overview

TAC evaluates student submissions across four metrics, each carrying a configurable weight:

| Metric key            | Description                                               | Default weight |
|-----------------------|-----------------------------------------------------------|----------------|
| `code_coverage`       | Mean line coverage from `supp_tests` + `base_tests` runs  | 1.0            |
| `supp_tests_passed`   | Pass-rate of student supplementary tests (`supp_tests/`)  | 1.0            |
| `base_tests_passed`   | Pass-rate of instructor base tests (`base_tests/`)        | 1.0            |
| `hidden_tests_passed` | Pass-rate of instructor hidden tests (`hidden_tests/`)    | 1.0            |
| `PEP8`                | PEP8 compliance score via pycodestyle                     | 1.0            |

The final grade is the normalized weighted average of all active metrics (0–100).

# Expected Directory Layout

TAC expects the following structure inside a student repository (or any working directory):

```
project/
├── src/                  # student source code  (SourceCode)
├── supp_tests/           # student supplementary tests  (SourceSuppTests)
├── base_tests/           # instructor base tests  (SourceBaseTests)
└── hidden_tests/         # instructor hidden tests  (SourceHiddenTests)
```

Each directory name is the default that the corresponding `Source` subclass searches for automatically. Custom paths can always be passed explicitly.

# Quick Start

### Minimal — auto-detect everything

```python
import tac

tester = tac.Tester(report_dir="report_dir")
tester.run(overwrite=False, debug=True)
print(tester.report)
```

### Explicit sources

```python
import tac

code_src        = tac.SourceCode(src_path="student/src")
supp_tests_src  = tac.SourceSuppTests(src_path="student/supp_tests")
base_tests_src  = tac.SourceBaseTests(src_path="master/base_tests")
hidden_tests_src = tac.SourceHiddenTests(src_path="master/hidden_tests")

tester = tac.Tester(
    code_src,
    supp_tests_src,
    base_tests_src=base_tests_src,
    hidden_tests_src=hidden_tests_src,
    report_dir="report_dir",
    weights={
        "code_coverage":       1.0,
        "supp_tests_passed":   1.0,
        "base_tests_passed":   2.0,
        "hidden_tests_passed": 2.0,
        "PEP8":                0.5,
    },
)
tester.run(overwrite=True, debug=True)
print(tester.report)         # grade, per-metric scores
```

### Sources from a git repository

```python
import tac

repo_url = "https://github.com/student/repo"

tester = tac.Tester(
    tac.SourceCode("repo/src", repo_url=repo_url),
    tac.SourceSuppTests("repo/supp_tests", repo_url=repo_url),
    base_tests_src=tac.SourceBaseTests("master/base_tests"),
    report_dir="report_dir_git",
)
tester.run(overwrite=True)
```

A full working example is available in [`Example/SimpleTP/auto_correct.py`](Example/SimpleTP/auto_correct.py).

# Public API

## Source classes

All source classes share the same constructor signature:

```python
Source(src_path=None, *, repo_url=None, repo_branch="main", logging_func=logging.info, ...)
```

| Class                | Default dir searched | Purpose                              |
|----------------------|----------------------|--------------------------------------|
| `Source`             | `src/`               | Base class                           |
| `SourceCode`         | `src/`               | Student source code (creates a venv) |
| `SourceMasterCode`   | `src/`               | Reference/instructor source code     |
| `SourceTests`        | `tests/`             | Generic test source (base class)     |
| `SourceSuppTests`    | `supp_tests/`        | Student supplementary tests          |
| `SourceBaseTests`    | `base_tests/`        | Instructor base tests                |
| `SourceHiddenTests`  | `hidden_tests/`      | Instructor hidden tests              |

## Tester

```python
tac.Tester(
    code_src=None,           # SourceCode — student code
    supp_tests_src=None,     # SourceSuppTests — student tests (positional)
    *,
    base_tests_src=None,     # SourceBaseTests — instructor base tests
    hidden_tests_src=None,   # SourceHiddenTests — instructor hidden tests
    master_code_src=None,    # SourceMasterCode — reference code
    report_dir=None,         # output directory (default: ./report_dir)
    weights=None,            # dict of metric weights
    pytest_timeout=60,       # per-suite pytest timeout in seconds
    **kwargs,
)
```

Key methods:

| Method                  | Description                                          |
|-------------------------|------------------------------------------------------|
| `run(**kwargs)`         | Full pipeline: setup → tests → coverage → PEP8      |
| `setup_at(**kwargs)`    | Copy sources to `report_dir` and create venv         |
| `push_report_to(url)`   | Push the JSON report back to a git repository        |
| `rm_report_dir()`       | Delete the report directory                          |

## Report

The `tester.report` object is a `tac.Report` instance:

```python
report.grade          # float — final weighted grade (0–100)
report.data           # dict  — per-metric {value, weight} entries
report.save(path)     # write to JSON
report.load(path)     # restore from JSON
```

`Report` constructor options: `score_min`, `score_max`, `grade_floor`, `grade_norm_func`.

## Grade utilities

```python
# Generate a blank notes.yaml rubric template
tac.make_notes_template(max_points={"Tests cachés (pytest)": 20})

# Fill auto-gradable fields in an existing notes.yaml from a report
tac.update_notes_yaml("notes.yaml", report)
```

## Homework (batch grading)

`tac.Homework` manages grading of an entire GitHub Classroom assignment:

```python
hw = tac.Homework(
    name="TP1",
    template_url="https://github.com/org/tp1-template",
    master_repo_url="https://github.com/org/tp1-master",
    classroom_id="tp1-2024",
    weights={"base_tests_passed": 2.0, "hidden_tests_passed": 2.0},
)
```

# Important Links

- Documentation: [https://JeremieGince.github.io/TPAutoCorrect/](https://JeremieGince.github.io/TPAutoCorrect/)
- GitHub: [https://github.com/JeremieGince/TPAutoCorrect/](https://github.com/JeremieGince/TPAutoCorrect/)

# Found a bug or have a feature request?

[Click here to create a new issue.](https://github.com/JeremieGince/TPAutoCorrect/issues/new)

# License

[Apache License 2.0](LICENSE)

# Citation

```
@misc{tac_Gince2023,
  title={TAC: TP Auto Correct},
  author={Jérémie Gince},
  year={2023},
  publisher={Université de Sherbrooke},
  url={https://github.com/JeremieGince/TPAutoCorrect},
}
```
