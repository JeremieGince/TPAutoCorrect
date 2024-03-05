from typing import Optional, Union, List
import json
import os
import numpy as np
import matplotlib.pyplot as plt
import pythonbasictools as pbt

from .perf_test_case import TestCase
from .report import Report
from .homework_utils import get_report_from_url, format_name
from .utils import push_file_to_git_repo


class Homework:
    def __init__(
            self,
            name: str,
            template_url: Optional[str] = None,
            master_repo_url: Optional[str] = None,
            students_repo_urls: Optional[list] = None,
            weights=None,
            grade_min_value: float = 50.0,
            *,
            additional_tests: Optional[Union[TestCase, List[TestCase]]] = None,
            **kwargs,
    ):
        self.name = name
        self.template_url = template_url
        self.master_repo_url = master_repo_url
        self.students_repo_urls = [] if students_repo_urls is None else students_repo_urls
        self.students_results = {}
        self.weights = weights
        self.grade_min_value = grade_min_value
        self.push_report = kwargs.get("push_report", False)
        self.reports_pdf_folder = kwargs.get("reports_pdf_folder", os.path.join("reports_pdf", self.fmt_name))
        self.report_pdf_keyname = kwargs.get("report_pdf_keyname", "report")
        self.nb_workers = kwargs.get("nb_workers", 0)
        self.short_name = kwargs.get("short_name", self.name)
        self.additional_tests = additional_tests

    @property
    def fmt_name(self):
        """
        Format name for file name.

        :return: str
        """
        return format_name(self.name)

    @property
    def fmt_short_name(self):
        """
        Format short name for file name.

        :return: str
        """
        return format_name(self.short_name)

    def get_all_grades(self):
        return [report.get("grade", np.nan) for _, report in self.students_results.items()]

    def get_stats_on_grades(self):
        grades = self.get_all_grades()
        if len(grades) == 0:
            return {
                "mean": np.nan,
                "median": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
                "count": 0,
            }
        return {
            "mean": np.nanmean(grades),
            "median": np.nanmedian(grades),
            "std": np.nanstd(grades),
            "min": np.nanmin(grades),
            "max": np.nanmax(grades),
            "count": len(grades),
        }

    def __getstate__(self):
        data = self.__dict__.copy()
        data["stats"] = self.get_stats_on_grades()
        return data

    def add_student_repo_url(self, repo_url):
        self.students_repo_urls.append(repo_url)
        return self

    def get_base_grade(self):
        if self.template_url is None:
            base_grade, grade_min_value = 0.0, 0.0
        else:
            base_grade = get_report_from_url(
                repo_url=self.template_url, master_repo_url=self.master_repo_url, weights=self.weights,
                tmp_report_dir=os.path.join("tmp_reports_dir", self.fmt_name, "reference"),
                additional_tests=self.additional_tests,
            ).grade
            grade_min_value = self.grade_min_value
        return base_grade, grade_min_value

    # @pbt.decorators.try_func_n_times(n=2, delay=10.0)
    def auto_grade_student(
            self,
            student_repo_url,
            base_grade,
            grade_min_value,
            lock: pbt.lock.FileLock = None,
            save_filepath=None,
    ) -> Report:
        s_report, report_pdf_path = get_report_from_url(
            repo_url=student_repo_url, master_repo_url=self.master_repo_url, weights=self.weights,
            tmp_report_dir=os.path.join(
                "tmp", self.fmt_short_name, str(self.students_repo_urls.index(student_repo_url))
            ),
            re_report_pdf=True,
            save_report_pdf_to=os.path.join(
                self.reports_pdf_folder, f"{self.get_student_homework_fmt_name_from_url(student_repo_url)}.pdf"
            ),
            report_pdf_keyname=self.report_pdf_keyname,
            push_report=self.push_report,
            additional_tests=self.additional_tests,
        )
        new_report = Report(
            data=s_report.data,
            grade_min=base_grade,
            grade_min_value=grade_min_value,
            grade_max=100.0,
        )
        self.students_results[student_repo_url] = new_report.get_state()
        self.maybe_push_report(student_repo_url)
        if lock is not None and save_filepath is not None:
            with lock:
                self.to_json(save_filepath)
        return new_report

    def auto_grade(self, save_filepath=None):
        base_grade, grade_min_value = self.get_base_grade()
        file_lock = pbt.lock.FileLock(f"{self.fmt_name}_lock.lck")
        pbt.multiprocessing_tools.apply_func_multiprocess(
            self.auto_grade_student,
            iterable_of_args=[
                (s_url, base_grade, grade_min_value, file_lock, save_filepath)
                for s_url in self.students_repo_urls
            ],
            nb_workers=self.nb_workers,
            desc=f"Grading {self.name}",
            unit="student",
        )
        if save_filepath is not None:
            self.to_json(save_filepath)
        return self

    def __repr__(self):
        data = self.students_results
        if not data:
            s_str = str({s_url: None for s_url in self.students_repo_urls})
        else:
            data["stats"] = self.get_stats_on_grades()
            s_str = str(data)
        return f"{self.name}: {s_str}"

    def __str__(self):
        return self.__repr__()

    def maybe_push_report(self, student_repo: str):
        if self.push_report:
            try:
                report_state = self.students_results[student_repo]
                report = Report()
                report.set_state(report_state)
                report.save()
                push_file_to_git_repo(
                    report.report_filepath, student_repo,
                    local_tmp_path=f"tmp_student_repo_{self.get_student_homework_fmt_name_from_url(student_repo)}",
                )
            except Exception as err:
                print(err)
        return self

    def to_json(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = self.__getstate__()
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
        return self

    def generate_tac_cmd(
            self,
            report_dir: str = "tmp_report_dir",
            overwrite: bool = True,
            debug: bool = True,
            add_rm_report_dir: bool = True,
    ) -> str:
        cmd = [
            "python", "-m", "tac",
            "--report-dir", report_dir,
            "--overwrite" if overwrite else "",
            "--debug" if debug else "",
        ]
        base_grade, grade_min_value = self.get_base_grade()
        cmd += ["--grade-min-value", str(grade_min_value)]
        cmd += ["--grade-min", str(base_grade)]
        if self.master_repo_url is not None:
            cmd += ["--master-code-src-url", self.master_repo_url]
            cmd += ["--master-tests-src-url", self.master_repo_url]

        for key, value in self.weights.items():
            cmd += [f"--{key}-weight", str(value)]

        if add_rm_report_dir:
            cmd += ["--rm-report-dir"]
        if self.push_report:
            cmd += ["--push-report-to", "auto"]

        cmd = [c for c in cmd if len(c) > 0]
        return " ".join(cmd)

    def save_tac_cmd(self, filepath: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        cmd = self.generate_tac_cmd()
        with open(filepath, "w") as f:
            f.write(cmd)
        return self

    def plot_grades_distribution(self, save_filepath=None, show=False, **kwargs):
        grades = self.get_all_grades()
        stats = self.get_stats_on_grades()
        fig, ax = kwargs.get("fig", None), kwargs.get("ax", None)
        if fig is None or ax is None:
            fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(grades, bins=kwargs.get("bins", 50))
        ax.set_title(f"{self.name} grades distribution")
        ax.axvline(stats["mean"], color='k', linestyle='dashed', linewidth=1)
        ax.axvline(stats["median"], color='k', linestyle='dashed', linewidth=1)
        ax.axvline(stats["min"], color='k', linestyle='dashed', linewidth=1)
        ax.axvline(stats["max"], color='k', linestyle='dashed', linewidth=1)
        ax.legend(["mean", "median", "min", "max"])
        ax.set_xlabel("Grades [%]")
        ax.set_ylabel("Number of students [-]")
        if save_filepath is not None:
            os.makedirs(os.path.dirname(save_filepath), exist_ok=True)
            fig.savefig(save_filepath)
        if show:
            plt.show()
        return fig, ax

    def get_student_homework_fmt_name_from_url(self, repo_url: str):
        return format_name(repo_url.split("/")[-1])
