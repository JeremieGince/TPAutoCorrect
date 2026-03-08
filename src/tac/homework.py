"""
Homework management module for GitHub Classroom integration.

This module provides the Homework class for managing programming assignments
in GitHub Classroom, including automatic grading of multiple student repositories,
statistics tracking, and grade visualization.
"""

import json
import logging
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import numpy as np
import pythonbasictools as pbt
from .grade import update_notes_yaml
from .report import Report
from .utils import format_name, get_report, get_report_with_pdf


class Homework:
    """
    Manage, grade, and analyze a homework assignment for GitHub Classroom.

    A Homework instance represents a single assignment and encapsulates:
    - Assignment metadata (name, URLs, weights)
    - Cached template and master repositories
    - Student repositories and grading results
    - Utilities for grading, reporting, and statistics

    Template and master repositories are cloned once and reused across
    students and grading runs for efficiency.

    :ivar str name: Full name of the homework assignment.
    :ivar str short_name: Short name for the homework (used in file paths).
    :ivar str template_url: URL of the template repository.
    :ivar str master_repo_url: URL of the master/reference repository.
    :ivar str classroom_id: GitHub Classroom assignment identifier.
    :ivar dict weights: Grading weights for different metrics.
    :ivar float grade_floor: Output grade floor (sanity-check reference only).
    :ivar bool push_report: Whether to push reports back to student repos.
    :ivar Optional[int] nb_workers: Number of parallel workers (None = sequential).
    :ivar str reports_pdf_folder: Directory for storing PDF reports.
    :ivar str report_pdf_keyname: Keyword to search for in PDF filenames.
    :ivar Path cache_dir: Directory for caching cloned repositories.
    :ivar Path reference_dir: Directory for reference/template data.
    :ivar dict students_results: Dictionary of student grades and results.
    :ivar list students_repos_names: List of student repository names.
    :ivar Callable logging_func: Logging function for messages.
    :ivar str template_repo_path: Path to the cached template repository.
    :ivar str master_repo_path: Path to the cached master repository.
    """

    def __init__(
        self,
        name: str,
        template_url: Optional[str] = None,
        master_repo_url: Optional[str] = None,
        classroom_id: Optional[str] = None,
        weights: Optional[Dict[str, float]] = None,
        grade_floor: float = 50.0,
        cache_dir: str = ".hw_cache",
        **kwargs,
    ):
        """
        Initialize a Homework assignment.

        :param name: Full name of the homework assignment.
        :type name: str
        :param template_url: URL of the template repository.
        :type template_url: Optional[str]
        :param master_repo_url: URL of the master repository.
        :type master_repo_url: Optional[str]
        :param classroom_id: GitHub Classroom assignment identifier.
        :type classroom_id: Optional[str]
        :param weights: Grading weights passed to TAC. Defaults to None.
        :type weights: Optional[Dict[str, float]]
        :param grade_floor: Output grade floor (sanity-check reference only). Defaults to 50.0.
        :type grade_floor: float
        :param cache_dir: Directory for caching repositories. Defaults to ".hw_cache".
        :type cache_dir: str
        :param kwargs: Additional keyword arguments including:
            - short_name: Short name for the homework
            - push_report: Whether to push reports to student repos
            - nb_workers: Number of parallel workers (None or 0 = sequential)
            - reports_pdf_folder: Directory for PDF reports
            - report_pdf_keyname: Keyword for finding PDF reports
            - logging_func: Custom logging function
        """
        self.name = name
        self.short_name = kwargs.get("short_name", name)

        self.template_url = template_url
        self.master_repo_url = master_repo_url
        self.classroom_id = classroom_id

        self.weights = weights or {}
        self.grade_floor = grade_floor

        self.push_report = kwargs.get("push_report", False)
        self.nb_workers: Optional[int] = kwargs.get("nb_workers", None)

        self.reports_pdf_folder = kwargs.get(
            "reports_pdf_folder",
            os.path.join("data/reports_pdf", self.fmt_name),
        )
        self.report_pdf_keyname = kwargs.get("report_pdf_keyname", "report")

        # Setup cache directories
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.reference_dir = self.cache_dir / "reference" / self.fmt_name

        # Initialize results storage
        self.students_results: Dict[str, dict] = {}
        self.students_repos_names: List[str] = []
        self.students_repos_dirpath: Optional[str] = None

        self.logging_func = kwargs.get("logging_func", logging.info)

        # Setup repository paths
        if self.template_url is not None:
            self.template_repo_path = str(
                self.cache_dir
                / "template"
                / self._repo_name_from_url(self.template_url)
            )

        if self.master_repo_url is not None:
            self.master_repo_path = str(
                self.cache_dir
                / "master"
                / self._repo_name_from_url(self.master_repo_url)
            )

    # ------------------------------------------------------------------
    # Properties and formatting helpers
    # ------------------------------------------------------------------

    @property
    def fmt_name(self) -> str:
        """
        Return a filesystem-safe formatted homework name.

        Removes spaces, special characters, and non-ASCII characters.

        :return: Formatted homework name.
        :rtype: str
        """
        return format_name(self.name)

    @property
    def fmt_short_name(self) -> str:
        """
        Return a filesystem-safe formatted short name.

        :return: Formatted short name.
        :rtype: str
        """
        return format_name(self.short_name)

    @staticmethod
    def _repo_name_from_url(url: str) -> str:
        """
        Extract and format a repository name from a URL.

        :param url: Git repository URL.
        :type url: str
        :return: Formatted repository name.
        :rtype: str
        """
        return format_name(Path(url).stem)

    # ------------------------------------------------------------------
    # Repository cache management
    # ------------------------------------------------------------------

    def _clone_or_update_repo(
        self,
        repo_url: str,
        target_dir: Path,
        update: bool = True,
    ) -> None:
        """
        Clone a repository if missing, otherwise optionally pull updates.

        :param repo_url: Git repository URL.
        :type repo_url: str
        :param target_dir: Local path for the repository.
        :type target_dir: Path
        :param update: Pull updates if repository already exists. Defaults to True.
        :type update: bool
        :raises subprocess.CalledProcessError: If git command fails.
        """
        if target_dir.exists():
            if update:
                self.logging_func(f"Updating repository at {target_dir}")
                subprocess.run(
                    ["git", "-C", str(target_dir), "pull"],
                    check=True,
                    capture_output=True,
                )
            else:
                self.logging_func(f"Using cached repository at {target_dir}")
        else:
            self.logging_func(f"Cloning {repo_url} into {target_dir}")
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", repo_url, str(target_dir)],
                check=True,
                capture_output=True,
            )

    def clone_template_repo(self, update: bool = True) -> Optional[str]:
        """
        Clone or reuse the template repository.

        The template repository contains the starter code provided to students.

        :param update: Pull updates if repository already exists. Defaults to True.
        :type update: bool
        :return: Local path to the template repository, or None if no template URL.
        :rtype: Optional[str]
        """
        if self.template_url is None:
            return None

        path = self.cache_dir / "template" / self._repo_name_from_url(self.template_url)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._clone_or_update_repo(self.template_url, path, update)
        self.template_repo_path = str(path)
        return self.template_repo_path

    def clone_master_repo(self, update: bool = True) -> Optional[str]:
        """
        Clone or reuse the master repository.

        The master repository contains the reference implementation.

        :param update: Pull updates if repository already exists. Defaults to True.
        :type update: bool
        :return: Local path to the master repository, or None if no master URL.
        :rtype: Optional[str]
        """
        if self.master_repo_url is None:
            return None

        path = (
            self.cache_dir / "master" / self._repo_name_from_url(self.master_repo_url)
        )
        path.parent.mkdir(parents=True, exist_ok=True)

        self._clone_or_update_repo(self.master_repo_url, path, update)
        self.master_repo_path = str(path)
        return self.master_repo_path

    # ------------------------------------------------------------------
    # Grade utilities and statistics
    # ------------------------------------------------------------------

    def get_all_grades(self) -> List[float]:
        """
        Return all student grades.

        :return: List of grades, with NaN for students without grades.
        :rtype: List[float]
        """
        return [
            report.get("grade", np.nan) for report in self.students_results.values()
        ]

    def get_stats_on_grades(self) -> Dict[str, float]:
        """
        Compute statistics on student grades.

        :return: Dictionary with mean, median, std, min, max, and count.
        :rtype: Dict[str, float]
        """
        grades = self.get_all_grades()

        if not grades:
            return {
                "mean": np.nan,
                "median": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
                "count": 0,
            }

        return {
            "mean": float(np.nanmean(grades)),
            "median": float(np.nanmedian(grades)),
            "std": float(np.nanstd(grades)),
            "min": float(np.nanmin(grades)),
            "max": float(np.nanmax(grades)),
            "count": len(grades),
        }

    # ------------------------------------------------------------------
    # Base grade computation
    # ------------------------------------------------------------------

    def get_base_grade(
        self, force: bool = False
    ) -> Tuple[float, float, Optional[dict]]:
        """
        Return the base grade computed from the template repository.

        The base grade is computed once and cached to disk. It represents
        the grade of the starter code before students make changes.

        The reference report is cached and recomputed only if:
        - it does not exist, or
        - force=True

        :param force: Force recomputation of the reference report. Defaults to False.
        :type force: bool
        :return: Tuple of (base_grade, grade_floor, reference_report_state).
                 reference_report_state is None when template_url is not set.
        :rtype: Tuple[float, float, Optional[dict]]
        """
        if self.template_url is None:
            return 0.0, 0.0, None

        self.reference_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.reference_dir / "report.json"

        # Load cached reference if available
        if report_path.exists() and not force:
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    state = json.load(f)

                report = Report()
                report.set_state(state)

                self.logging_func("Using cached reference report")
                return report.grade, self.grade_floor, report.get_state()

            except Exception as e:
                self.logging_func(f"Error loading cached report: {e}. Recomputing...")

        # Recompute reference
        self.logging_func("Computing reference report from template")

        self.clone_template_repo()
        self.clone_master_repo()

        run_dir = self.reference_dir / "run"
        run_dir.mkdir(parents=True, exist_ok=True)

        report, _ = get_report_with_pdf(
            repo_path=self.template_repo_path,
            master_repo_path=getattr(self, "master_repo_path", None),
            weights=self.weights,
            tmp_report_dir=str(run_dir),
        )

        # Cache the report
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report.get_state(), f, indent=4)

        return report.grade, self.grade_floor, report.get_state()

    # ------------------------------------------------------------------
    # Student repositories management
    # ------------------------------------------------------------------

    def clone_students_repos(
        self,
        classroom_id: Optional[str] = None,
        students_repos_dir: str = "homeworks",
    ) -> str:
        """
        Clone student repositories using GitHub Classroom CLI.

        Requires the GitHub CLI (gh) and classroom extension to be installed.
        Repositories are cloned once and reused across grading runs.

        Installation:
            gh extension install github/gh-classroom

        :param classroom_id: GitHub Classroom assignment identifier. Uses self.classroom_id if None.
        :type classroom_id: Optional[str]
        :param students_repos_dir: Target directory for student repositories.
        :type students_repos_dir: str
        :return: Path to the student repositories directory.
        :rtype: str
        :raises subprocess.CalledProcessError: If gh classroom command fails.
        """
        classroom_id = classroom_id or self.classroom_id

        if classroom_id is None:
            raise ValueError(
                "classroom_id must be provided either in __init__ or as argument"
            )

        parent = Path(students_repos_dir).resolve() / self.fmt_short_name
        parent.mkdir(parents=True, exist_ok=True)

        if any(parent.iterdir()):
            self.logging_func(f"Using existing student repos in {parent}")
        else:
            self.logging_func("Cloning student repositories via GitHub Classroom")

            # Clone using gh classroom
            subprocess.run(
                ["gh", "classroom", "clone", "student-repos", "-a", classroom_id],
                cwd=parent,
                check=True,
            )

            # GitHub Classroom creates a nested directory, flatten it
            inner_dirs = [p for p in parent.iterdir() if p.is_dir()]

            for inner in inner_dirs:
                for repo in inner.iterdir():
                    if repo.is_dir():
                        shutil.move(str(repo), parent / repo.name)
                inner.rmdir()

        self.students_repos_dirpath = str(parent)
        self.students_repos_names = [p.name for p in parent.iterdir() if p.is_dir()]

        self.logging_func(
            f"Found {len(self.students_repos_names)} student repositories"
        )
        return self.students_repos_dirpath

    # ------------------------------------------------------------------
    # Automatic grading
    # ------------------------------------------------------------------

    def auto_grade_student(
        self,
        student_repo_path: Path,
        base_grade: float,
        grade_floor: float,
        reference_report_state: Optional[dict] = None,
        lock: Optional[pbt.lock.FileLock] = None,
        save_filepath: Optional[str] = None,
    ) -> Report:
        """
        Automatically grade a single student repository.

        :param student_repo_path: Path to the student's repository.
        :type student_repo_path: Path
        :param base_grade: Base grade from template evaluation (used for sanity logging only).
        :type base_grade: float
        :param grade_floor: Grade floor (used for sanity logging only).
        :type grade_floor: float
        :param reference_report_state: State dict of the reference (template) report to embed.
        :type reference_report_state: Optional[dict]
        :param lock: Optional file lock for concurrent writes.
        :type lock: Optional[pbt.lock.FileLock]
        :param save_filepath: JSON file to save intermediate results.
        :type save_filepath: Optional[str]
        :return: Final TAC report with adjusted grades.
        :rtype: Report
        """
        student_repo_path = Path(student_repo_path)
        self.logging_func(f"Grading student: {student_repo_path.name}")

        # Setup temporary directory for this student
        tmp_dir = (
            Path("homeworks_corrected") / self.fmt_short_name / student_repo_path.name
        )
        tmp_dir.mkdir(parents=True, exist_ok=True)

        # Get student report
        try:
            s_report = cast(
                Report,
                get_report(
                    repo_path=str(student_repo_path),
                    master_repo_path=getattr(self, "master_repo_path", None),
                    weights=self.weights,
                    tmp_report_dir=str(tmp_dir),
                    push_report=self.push_report,
                ),
            )
        except Exception as e:
            self.logging_func(f"Error grading {student_repo_path.name}: {e}")
            # Create a failed report
            s_report = Report(data={})

        # Create final report with grade adjustments.
        # grade_floor sets the minimum grade a student can receive (e.g. 40.0).
        # The formula maps weighted_sum=0 → grade_floor and weighted_sum=100 → 100.
        final_report = Report(
            data=s_report.data,
            score_min=0.0,
            grade_floor=self.grade_floor,
            score_max=100.0,
        )

        if final_report.grade < base_grade:
            self.logging_func(
                f"Warning: {student_repo_path.name} scored {final_report.grade:.2f} "
                f"which is below the template base grade ({base_grade:.2f})."
            )

        # Store results, embedding the reference report for comparison
        result_entry = final_report.get_state()
        if reference_report_state is not None:
            result_entry["reference_report"] = reference_report_state
        self.students_results[student_repo_path.name] = result_entry

        # Update the Code section of the student's notes.yaml with auto-graded scores
        notes_path = student_repo_path / "notes.yaml"
        try:
            update_notes_yaml(notes_path, final_report)
        except Exception as e:
            self.logging_func(
                f"Warning: could not update notes.yaml for {student_repo_path.name}: {e}"
            )

        # Clean up temporary files left by the grading run
        self._cleanup_tmp_dir(tmp_dir)

        # Save intermediate results if requested
        if lock and save_filepath:
            with lock:
                self.to_json(str(save_filepath))

        self.logging_func(
            f"Completed grading {student_repo_path.name}: {final_report.grade:.2f}/100"
        )

        return final_report

    def _cleanup_tmp_dir(self, tmp_dir: Path) -> None:
        """
        Clean up temporary files from a student's grading directory.

        Removes __pycache__, .pytest_cache, and other temporary files
        to prevent interference between students.

        :param tmp_dir: Temporary directory to clean.
        :type tmp_dir: Path
        """
        if not tmp_dir.exists():
            return

        try:
            # Remove Python cache directories
            for cache_dir in ["__pycache__", ".pytest_cache"]:
                for root, dirs, files in os.walk(tmp_dir):
                    if cache_dir in dirs:
                        cache_path = Path(root) / cache_dir
                        shutil.rmtree(cache_path, ignore_errors=True)

            # Remove .pyc files
            for root, dirs, files in os.walk(tmp_dir):
                for file in files:
                    if file.endswith(".pyc"):
                        os.remove(Path(root) / file)

        except Exception as e:
            self.logging_func(f"Warning: Could not clean tmp dir: {e}")

    def auto_grade(
        self,
        save_filepath: Optional[str] = None,
        classroom_id: Optional[str] = None,
        force_base_grade: bool = False,
    ) -> "Homework":
        """
        Automatically grade all student repositories.

        This method:
        1. Computes the base grade from the template
        2. Clones all student repositories
        3. Grades each student repository
        4. Saves results to a JSON file

        :param save_filepath: JSON file to save grading results.
        :type save_filepath: Optional[str]
        :param classroom_id: GitHub Classroom assignment ID. Uses self.classroom_id if None.
        :type classroom_id: Optional[str]
        :param force_base_grade: Force recomputation of the base grade. Defaults to False.
        :type force_base_grade: bool
        :return: Self for method chaining.
        :rtype: Homework
        """
        self.logging_func(f"Starting auto-grading for {self.name}")

        # Get base grade
        base_grade, grade_floor, reference_report_state = self.get_base_grade(
            force=force_base_grade
        )
        self.logging_func(f"Base grade: {base_grade:.2f}/100")

        # Clone student repositories
        self.clone_students_repos(classroom_id or self.classroom_id)

        if self.students_repos_dirpath is None:
            raise RuntimeError(
                "students_repos_dirpath is not set after clone_students_repos(). "
                "Ensure clone_students_repos() completes successfully before grading."
            )

        # Setup file lock for concurrent access
        lock = pbt.lock.FileLock(f"{self.fmt_name}.lock")
        repos = Path(self.students_repos_dirpath)

        # Grade each student
        student_repos = [p for p in repos.iterdir() if p.is_dir()]
        self.logging_func(f"Grading {len(student_repos)} students")

        if self.nb_workers is not None and self.nb_workers > 0:
            with ThreadPoolExecutor(max_workers=self.nb_workers) as executor:
                futures = {
                    executor.submit(
                        self.auto_grade_student,
                        repo,
                        base_grade,
                        grade_floor,
                        reference_report_state,
                        lock,
                        save_filepath,
                    ): repo
                    for repo in student_repos
                }
                for i, future in enumerate(as_completed(futures), 1):
                    repo = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        self.logging_func(f"Error grading {repo.name}: {e}")
                    self.logging_func(f"Progress: {i}/{len(student_repos)}")
        else:
            for i, repo in enumerate(student_repos, 1):
                self.logging_func(f"Progress: {i}/{len(student_repos)}")
                self.auto_grade_student(
                    repo,
                    base_grade,
                    grade_floor,
                    reference_report_state,
                    lock,
                    save_filepath,
                )

        # Save final results
        if save_filepath:
            self.to_json(save_filepath)
            self.logging_func(f"Results saved to {save_filepath}")

        # Print summary statistics
        stats = self.get_stats_on_grades()
        self.logging_func(
            f"Grading complete! Mean: {stats['mean']:.2f}, "
            f"Median: {stats['median']:.2f}, "
            f"Count: {stats['count']}"
        )

        return self

    # ------------------------------------------------------------------
    # TAC command generation (for debugging)
    # ------------------------------------------------------------------

    def save_tac_cmd(self, filepath: str) -> None:
        """
        Save the TAC command that would be used for grading.

        Useful for debugging and manual testing.

        :param filepath: Path to save the command.
        :type filepath: str
        """
        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)

        cmd_parts = [
            "python -m tac",
            "--code-src-path='student/src'",
            "--tests-src-path='student/tests'",
        ]

        if self.master_repo_url:
            cmd_parts.extend(
                [
                    "--master-code-src-path='master/src'",
                    "--master-tests-src-path='master/tests'",
                ]
            )

        # Add weights
        for key, weight in self.weights.items():
            cmd_parts.append(f"--{key.replace('_', '-')}-weight={weight}")

        cmd_parts.extend(
            [
                f"--grade-floor={self.grade_floor}",
                "--debug",
            ]
        )

        cmd = " \\\n    ".join(cmd_parts)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(cmd + "\n")

        self.logging_func(f"TAC command saved to {filepath}")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def __getstate__(self) -> Dict:
        """
        Return a JSON-serializable representation of the object.

        :return: Serializable state dictionary.
        :rtype: Dict
        """
        data = self.__dict__.copy()

        # Remove non-serializable items
        data.pop("logging_func", None)

        # Convert Path objects to strings
        data["cache_dir"] = str(self.cache_dir)
        data["reference_dir"] = str(self.reference_dir)
        data["template_repo_path"] = getattr(self, "template_repo_path", None)
        data["master_repo_path"] = getattr(self, "master_repo_path", None)

        # Add statistics
        data["stats"] = self.get_stats_on_grades()

        return data

    def to_json(self, filepath: str) -> "Homework":
        """
        Serialize the homework state to a JSON file.

        :param filepath: Output file path.
        :type filepath: str
        :return: Self for method chaining.
        :rtype: Homework
        """
        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.__getstate__(), f, indent=4)

        return self

    # ------------------------------------------------------------------
    # Plotting and visualization
    # ------------------------------------------------------------------

    def plot_grades_distribution(
        self,
        save_filepath: Optional[str] = None,
        show: bool = False,
        bins: int = 50,
    ) -> Tuple[Figure, Axes]:
        """
        Plot the distribution of student grades.

        Creates a histogram with vertical lines for mean, median, min, and max.

        :param save_filepath: Path to save the plot. If None, plot is not saved.
        :type save_filepath: Optional[str]
        :param show: Whether to display the plot. Defaults to False.
        :type show: bool
        :param bins: Number of histogram bins. Defaults to 50.
        :type bins: int
        :return: Matplotlib figure and axes.
        :rtype: Tuple[plt.Figure, plt.Axes]
        """
        grades = self.get_all_grades()
        stats = self.get_stats_on_grades()

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(grades, bins=bins, edgecolor="black", alpha=0.7)

        # Add vertical lines for statistics
        colors = {"mean": "red", "median": "green", "min": "blue", "max": "orange"}
        for key, color in colors.items():
            if not np.isnan(stats[key]):
                ax.axvline(
                    stats[key],
                    linestyle="--",
                    color=color,
                    label=f"{key.capitalize()}: {stats[key]:.2f}",
                    linewidth=2,
                )

        ax.set_title(
            f"{self.name} – Grade Distribution", fontsize=14, fontweight="bold"
        )
        ax.set_xlabel("Grade [%]", fontsize=12)
        ax.set_ylabel("Number of Students", fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)

        if save_filepath:
            parent = os.path.dirname(save_filepath)
            if parent:
                os.makedirs(parent, exist_ok=True)
            fig.savefig(save_filepath, dpi=300, bbox_inches="tight")
            self.logging_func(f"Grade distribution saved to {save_filepath}")

        if show:
            plt.show()

        return fig, ax

    # ------------------------------------------------------------------
    # String representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        """
        Return a string representation of the homework.

        :return: String representation.
        :rtype: str
        """
        if not self.students_results:
            return f"Homework(name='{self.name}', students=0, status='not graded')"

        stats = self.get_stats_on_grades()
        return (
            f"Homework(name='{self.name}', "
            f"students={stats['count']}, "
            f"mean={stats['mean']:.2f}, "
            f"median={stats['median']:.2f})"
        )

    __str__ = __repr__
