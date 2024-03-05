import os
import shutil
from typing import Optional

from .source import SourceCode, SourceTests, SourceMasterCode, SourceMasterTests
from .tester import Tester


def get_report_from_url(
        repo_url: str,
        *,
        master_repo_url: Optional[str] = None,
        path_to_root=".",
        weights=None,
        push_report: bool = False,
        re_report_pdf: bool = False,
        tmp_report_dir: str = "tmp_report_dir",
        **kwargs,
):
    code_source = SourceCode(os.path.join(path_to_root, "src"), url=repo_url, logging_func=print)
    tests_source = SourceTests(os.path.join(path_to_root, "tests"), url=repo_url, logging_func=print)
    if master_repo_url is None:
        master_code_source, master_tests_source = None, None
    else:
        master_code_source = SourceMasterCode(
            os.path.join(path_to_root, "src"), url=master_repo_url,
            logging_func=print, local_repo_tmp_dirname="tmp_master_repo"
        )
        master_tests_source = SourceMasterTests(
            os.path.join(path_to_root, "tests"), url=master_repo_url,
            logging_func=print, local_repo_tmp_dirname="tmp_master_repo"
        )
    default_weights = {
        Tester.PEP8_KEY: 10.0,
        Tester.PERCENT_PASSED_KEY: 10.0,
        Tester.CODE_COVERAGE_KEY: 20.0,
        Tester.MASTER_PERCENT_PASSED_KEY: 30.0,
    }
    if weights is None:
        weights = {}
    weights = {**default_weights, **weights}

    auto_corrector = Tester(
        code_source, tests_source,
        master_code_src=master_code_source,
        master_tests_src=master_tests_source,
        report_dir=tmp_report_dir,
        logging_func=print,
        weights=weights,
        additional_tests=kwargs.get("additional_tests"),
    )
    auto_corrector.run(
        overwrite=False,
        debug=True,
        clear_temporary_files=False,
        clear_pytest_temporary_files=False,
    )
    if push_report:
        auto_corrector.push_report_to(repo_url)
    report_pdf = None
    if re_report_pdf:
        report_pdf = get_report_pdf_from_dir(
            tmp_report_dir,
            report_keyname=kwargs.get("report_pdf_keyname"),
            search_in_children=True,
            save_filepath=kwargs.get("save_report_pdf_to"),
        )
    auto_corrector.rm_report_dir()
    if re_report_pdf:
        return auto_corrector.report, report_pdf
    return auto_corrector.report


def get_report_pdf_from_dir(
        report_dir: str,
        *,
        report_keyname: str = "report",
        search_in_children: bool = True,
        save_filepath: Optional[str] = None,
        **kwargs,
) -> Optional[str]:
    r"""
    Get the path to the report PDF file from the report directory and return
    this path. If the file is not found, return None.

    :param report_dir: The folder where the report is located.
    :type report_dir: str
    :param report_keyname: A partial name of the report file to identify it.
    :type report_keyname: str
    :param search_in_children: If True, search in the children folders of the
        report directory.
    :type search_in_children: bool
    :param save_filepath: If not None, copy the report file to this path.
    :type save_filepath: str
    :param kwargs: Additional arguments to pass to the function.

    :keyword lower_report_keyname: If True, convert the report keyname to lower and
        compare it to the lower case of the file name.

    :return: The path to the report PDF file or None if the file is not found.
    """
    lower_report_keyname = kwargs.get("lower_report_keyname", True)
    if lower_report_keyname:
        report_keyname = report_keyname.lower()
    if not os.path.isdir(report_dir):
        return None
    for root, dirs, files in os.walk(report_dir):
        for file in files:
            fmt_str_file = file.lower() if lower_report_keyname else file
            if report_keyname in fmt_str_file and file.endswith(".pdf"):
                if save_filepath is not None:
                    os.makedirs(os.path.dirname(save_filepath), exist_ok=True)
                    shutil.copy2(os.path.join(root, file), save_filepath)
                return os.path.join(root, file)
        if not search_in_children:
            break
    return None


def format_name(name: str) -> str:
    fmt_name = os.path.normpath(name)
    fmt_name = fmt_name.replace(' ', '_')
    fmt_name = fmt_name.replace(':', '')
    fmt_name = fmt_name.encode('ascii', 'ignore').decode('ascii')
    return fmt_name

