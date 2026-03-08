# Pull Request — `dev` → `main`

## Summary

This PR is a major overhaul of the `src/tac/` package. It introduces two new
modules, a three-suite test model, a cleaner grade formula, a full public API
surface, and a large collection of bug fixes accumulated since the last PR.

---

## New modules

### `src/tac/grade.py`

New module for managing student YAML rubrics (`notes.yaml`) from a TAC
`Report` object.

- `make_notes_template(max_points, schema)` — generates a blank `notes.yaml`
  string from a configurable rubric schema (defaults to the PHQ404 schema:
  100 pts total, Code 60 pts, Rapport 40 pts).
- `update_notes_yaml(filepath, report, key_to_item, schema)` — reads an
  existing `notes.yaml` (or creates one from template), writes the
  auto-gradable scores from a `Report`, and recomputes category subtotals.
- Internal helpers: `_round_score`, `_update_item_field`,
  `_recompute_category_subtotal`, `_render_schema`, `_apply_max_points_overrides`.

### `src/tac/homework.py`

New module providing `Homework`, a GitHub Classroom batch-grading orchestrator.

- Constructor accepts `name`, `template_url`, `master_repo_url`,
  `classroom_id`, `weights`, `grade_floor`, `cache_dir`.
- `clone_template_repo()` / `clone_master_repo()` — clones or reuses cached
  repositories.
- `get_base_grade()` — computes the template repository grade (cached to disk
  as `report.json`); returns `(base_grade, grade_floor, reference_report_state)`.
- `clone_students_repos()` — clones all student repos via
  `gh classroom clone student-repos` and flattens the nested directory structure
  GitHub Classroom creates.
- `auto_grade_student(student_repo_path, reference_report_state)` — grades a
  single student: runs `get_report()`, applies `grade_floor`, calls
  `update_notes_yaml()`, saves intermediate JSON.
- `auto_grade(nb_workers)` — full batch pipeline with optional
  `ThreadPoolExecutor` parallelism.
- `plot_grades_distribution(save_path)` — histogram with mean/median/min/max
  markers; optionally saves PNG at 300 dpi.
- `get_stats_on_grades()`, `to_json()`, `__getstate__()`, `__repr__`.

---

## Breaking changes

### `src/tac/source.py` — three-suite test model

`SourceMasterTests` has been removed and replaced by three focused classes:

| Old | New |
|-----|-----|
| `SourceMasterTests` | `SourceBaseTests` — public test suite from master repo |
| *(none)* | `SourceHiddenTests` — hidden test suite from master repo |
| `SourceTests` | `SourceSuppTests` — supplementary tests submitted by the student |

The constructor parameter `url=` has been renamed to `repo_url=` across all
`Source` subclasses.

`SourceCode` gains a `use_uv: bool` parameter. When `True`, the virtual
environment is created and dependencies installed using `uv` instead of `pip`.

Removed methods: `Source.__del__`, `Source.clear_git_repo`,
`SourceCode.add_requirements`. Renamed method: `SourceCode.maybe_create_venv`
→ `SourceCode.recreate_venv`.

### `src/tac/tester.py` — new metric keys

| Old attribute / key | New |
|---------------------|-----|
| `tests_src` | `supp_tests_src` |
| `master_tests_src` | `base_tests_src` + `hidden_tests_src` |
| `PERCENT_PASSED_KEY` | `SUPP_TESTS_KEY` |
| `MASTER_PERCENT_PASSED_KEY` | `BASE_TESTS_KEY`, `HIDDEN_TESTS_KEY` |

The tester now runs three independent pytest subprocesses (one per suite) with
timeout support. Removed internal methods: `_run_pytest`, `_run_master_pytest`,
`move_temp_files_to_report_dir`, `_find_temp_filepath`, `temp_files` property.

### `src/tac/report.py` — renamed constants and new grade formula

All grade-scale constants have been renamed for clarity:

| Old | New |
|-----|-----|
| `DEFAULT_GRADE_MIN` | `DEFAULT_SCORE_MIN` |
| `DEFAULT_GRADE_MAX` | `DEFAULT_SCORE_MAX` |
| `DEFAULT_GRADE_MIN_VALUE` | `DEFAULT_GRADE_FLOOR` |

Constructor kwargs renamed accordingly: `grade_min` → `score_min`,
`grade_max` → `score_max`, `grade_min_value` → `grade_floor`.

The old grade scaling formula has been replaced:

```python
# Old
grade = (grade_max - grade_min_value) * (grade - grade_min) / grade_scale + grade_min_value

# New
grade = max(grade_floor, weighted_sum)   # weighted_sum is already in 0–100
```

A student who scores above `grade_floor` receives their raw weighted score. A
student who scores below receives exactly `grade_floor`.

`*args` / `self.args` / `self.kwargs` removed from `Report.__init__`.
`get_state()` / `set_state()` updated to persist the new fields.

### `src/tac/__main__.py` — renamed CLI flags

| Old flag | New flag |
|----------|----------|
| `--grade-min` | `--score-min` |
| `--grade-max` | `--score-max` |
| `--grade-min-value` | `--grade-floor` |

New flag: `--no-uv` disables the `uv` package manager.

### `src/tac/__init__.py` — updated public API

`SourceMasterTests` removed from exports; `SourceBaseTests`, `SourceHiddenTests`,
`SourceSuppTests` added. New exports: `Homework`, `make_notes_template`,
`update_notes_yaml`, `get_report`, `get_report_with_pdf`. An explicit `__all__`
list has been added.

---

## Bug fixes

### `src/tac/report.py`

- **`get_value` / `get_weight`** — previously called `self.get(key, default)`
  then immediately accessed `result[VALUE_KEY]`, which raised `TypeError`
  whenever `default` was a non-dict non-`None` value. Fixed by calling
  `self.get(key)` and returning `default` explicitly when the entry is `None`.
- **`get_grade` sum over `None`** — `get_weighted()` can return `None`;
  `sum()` over a list containing `None` raises `TypeError`. Fixed by filtering
  `None` values before summing.
- **`__setitem__` raw-tuple storage** — tuples passed as values were stored
  verbatim in `self.data` instead of being unpacked into
  `{VALUE_KEY: ..., WEIGHT_KEY: ...}` dicts, making `get_value` / `get_weight`
  fail on any key set via `report[key] = (val, weight)`.
- **`normalize_weights_` / `get_normalized` ZeroDivisionError** — no guard
  existed for zero total weight; now raises `ValueError`.
- **`self.data = None` default** — `data=None` left `self.data` as `None`
  until `_initialize_data_` was called; `self.data` now defaults to `{}`.
- **`grade_norm_func` silently lost on `load()`** — now a `UserWarning` is
  issued and `grade_norm_func` is explicitly reset to `None`.

### `src/tac/utils.py`

- **`try_rmtree`** — `shutil.rmtree(ignore_errors=True)` silences the
  `onerror` callback entirely (Python ignores `onerror` when
  `ignore_errors=True`). Fixed by always passing `onerror=shutil_onerror` and
  catching errors conditionally.
- **`get_report_pdf_from_dir`** — `os.makedirs(os.path.dirname(save_filepath))`
  crashes when `save_filepath` is a bare filename because `dirname` returns
  `""`. Fixed with an `if parent:` guard.
- **`rm_filetypes_from_root`** — called `try_rmtree()` (directory removal) on
  individual files; changed to `os.remove()`.
- **`add_path` / `add_to_path`** — mutated the original `sys.path` list object
  in-place, affecting other threads. Fixed by copying (`sys.path = sys.path[:]`)
  before mutation.
- **`PathImport.path_import`** — did not guard `spec is None` before calling
  `spec.loader.exec_module()`, causing `AttributeError` on missing modules.
- **`push_report=True` silently dropped** — `get_report_with_pdf` accepted a
  `push_report` parameter but never used it. Fixed by calling
  `auto_corrector.push_report_to()` after `auto_corrector.run()` when
  `push_report=True`.

### `src/tac/tester.py`

- **Collection-error detection** — when pytest encounters an `ImportError`
  during collection, `pytest-json-report` writes
  `{"summary": {"total": 0, "collected": N}}` with no `"errors"` key. The
  previous check looked for an `"errors"` key and missed this case. Fixed:
  collection error is now detected as `collected > 0 and total == 0`.
- **Absent test suite weight** — when `master_repo_path=None` or a suite
  directory is not found, the suite was assigned `weight=configured_value`
  with `value=0.0`, which dragged the weighted average down even though no
  tests were run. Fixed: absent suites now use `weight=0.0` so they are
  excluded from grade normalisation entirely.
- **Timeout handling** — pytest timeout now catches `subprocess.TimeoutExpired`
  and returns a synthetic `CompletedProcess(returncode=-1)`.
- **Coverage path filtering** — venv paths were included in coverage
  measurement; now filtered out.
- **Remote `supp_tests` never set up** — `setup_at()` checked only
  `supp_tests_src.is_local` before calling `supp_tests_src.setup_at()`.
  When sources come from a git repository `is_remote=True` and
  `is_local=False`, so the supp tests were silently skipped and both
  `supp_tests_passed` and `code_coverage` scored 0. Fixed by mirroring the
  existing `base_tests_src` logic: check `is_local or is_remote`.

### `src/tac/perf_test_case.py`

- **`physical lines` KeyError** — `result.counters["physical lines"]` raised
  `KeyError` on empty directories; changed to `.get("physical lines", 0)`.

### `src/tac/__init__.py`

- **`importlib_metadata`** (third-party backport) replaced with
  `importlib.metadata` (stdlib, Python ≥ 3.8), wrapped in `try/except` so
  `__version__` degrades gracefully to `"unknown"` on uninstalled checkouts.

### `src/tac/__main__.py`

- **`sys.exit(main())`** — if `main()` returned a non-integer string such as
  `"Points 85/100"`, `sys.exit` would print it to stderr. Fixed:
  `sys.exit(main() or 0)`.
- **Weight argument names** — weight flags were generated as
  `--code_coverage-weight` (mixed underscore/hyphen) because `key` already
  contained underscores. Fixed: `key.replace('_', '-')` applied when building
  the flag name.

---

## Enhancements

### `src/tac/source.py`

- `is_subpath_in_path()` rewritten with `Path.relative_to()` to eliminate
  false positives from naive string containment on overlapping path names.
- `_clone_repo()` path structure corrected.
- `_find_dep_file(filename)` deduplicates `find_pyproject_path()` /
  `find_requirements_path()`.
- `SourceCode.setup_at()` skips venv creation if it already exists and
  `overwrite=False`.

### `src/tac/perf_test_case.py`

- `PEP8TestCase` now accepts `max_line_length` and `ignore` per-instance,
  making style checks configurable without subclassing.
- Error message now reports error-code counts (`"E501:3, W291:1"`) rather than
  full error text.
- `TestResult.__repr__` and `PEP8TestCase.__repr__` added.

### `src/tac/utils.py`

- `VENV_SCRIPTS_FOLDER_BY_OS` constant added (maps OS name → `Scripts`/`bin`).
- `get_report(repo_path, ...)` — high-level convenience function that runs the
  full correction pipeline and returns a `Report`.
- `get_report_with_pdf(repo_path, ...)` — same, also returns the PDF path.
- `format_name(name)` — normalises a string to a filesystem-safe identifier.
- `get_git_repo_branch(working_dir, search_parent_directories=True)` — new
  utility function (analogous to the existing `get_git_repo_url()`) that uses
  `gitpython` to return the name of the currently active branch of the git
  repository at the given path, or `None` on any failure.

### `src/tac/report.py`

- `get_normalized()` now propagates `score_min`, `grade_floor`, `score_max`,
  `grade_norm_func`, and `report_filepath` to the returned instance.
- Full type-annotation pass: all method signatures annotated with
  `Dict`, `List`, `Tuple`, `KeysView`, `Iterator`, `Any`, etc.
- `save()` / `load()` use `ValueError` instead of `assert`; all file I/O uses
  `encoding="utf-8"`.

### `src/tac/__main__.py`

- `ArgumentParser` now passes `formatter_class=argparse.ArgumentDefaultsHelpFormatter`
  so `--help` displays defaults.
- `tester.run()` is wrapped in `try/except`; errors are printed to `stderr`;
  `--debug` triggers `traceback.print_exc()`.
- Final grade printed with a `===` banner for visibility.
- `logging_func` and `use_uv` threaded through to all `Source` constructors.

### `Example/SimpleTP/auto_correct.py`

- **`auto_correct_from_git()`** — replaced the hardcoded `tac.__url__` (which
  always pointed at the upstream `JeremieGince/TPAutoCorrect` repo) with
  `tac.tac_utils.get_git_repo_url(os.path.dirname(__file__))` so the correct
  fork/remote is detected at runtime.
- Added `repo_branch = tac.tac_utils.get_git_repo_branch(os.path.dirname(__file__))`
  and passed it to all three sources (`SourceCode`, `SourceSuppTests`,
  `SourceBaseTests`), so the branch used for cloning matches the currently
  checked-out branch (e.g. `dev`) rather than defaulting to `main`.

### `README.md`

- Replaced sparse placeholder content with full documentation: project
  overview, grading-metric table, expected directory layout, quick-start
  examples (minimal, explicit sources, git sources), and a public API
  reference covering `Source` subclasses, `Tester`, `Report`, grade
  utilities, and `Homework`.
- Corrected Python badge label from `python-3.9` to `python-3.9+`.

### `pyproject.toml`

- Added `matplotlib>=3.9.4` to `[dependencies]` (required by
  `Homework.plot_grades_distribution()`).
- Normalised indentation in `[dependency-groups]`, `[build-system]`,
  `[tool.coverage.report]`, `[tool.pytest.ini_options]`, and
  `[tool.mypy.overrides]` sections (4-space → 2-space, inline tables).

### `setup.py`

- `long_description` now reads `README.md` at build time via `pathlib`
  instead of the non-functional `"file: README.md"` string literal.
- `python_requires` bumped from `>=3.8` to `>=3.9` to match `pyproject.toml`.
- Normalised string quoting (double quotes throughout).

### `.gitignore`

- Added `uv.lock` to the ignore list.
