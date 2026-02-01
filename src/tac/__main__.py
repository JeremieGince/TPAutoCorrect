import argparse
import sys

from . import (
    Report,
    SourceCode,
    SourceMasterCode,
    SourceMasterTests,
    SourceTests,
    Tester,
)


def parse_args():
    """
    Parse command-line arguments for the TPAutoCorrect tool.

    Returns:
        argparse.Namespace: The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--code-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the code to be tested.",
    )
    parser.add_argument(
        "--code-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the code to be tested.",
    )
    parser.add_argument(
        "--tests-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the tests for the code to be tested.",
    )
    parser.add_argument(
        "--tests-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the tests for the code to be tested.",
    )
    parser.add_argument(
        "--master-code-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the master code to be tested.",
    )
    parser.add_argument(
        "--master-code-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the master code to be tested.",
    )
    parser.add_argument(
        "--master-tests-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the master tests for the code to be tested.",
    )
    parser.add_argument(
        "--master-tests-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the master tests for the code to be tested.",
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default=None,
        help="Path to the directory to save the report.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug messages.",
    )
    parser.add_argument(
        "--push-report-to",
        type=str,
        default=None,
        help="Push report file to a git repository. "
        "If equal to 'auto' the repository of the current project will be used if found.",
    )
    parser.add_argument(
        "--clear-pytest-temporary-files",
        action="store_true",
        help="Clear pytest temporary files.",
    )
    for key, default_weight in Tester.DEFAULT_WEIGHTS.items():
        parser.add_argument(
            f"--{key}-weight",
            type=float,
            default=default_weight,
            help=f"Weight of the {key} test in the final score.",
        )
    parser.add_argument(
        "--rm-report-dir",
        action="store_true",
        help="Remove the report directory. "
        "This option is useful when the report file is pushed to a git repository"
        " and the report directory is no longer needed.",
    )
    parser.add_argument(
        "--grade-min",
        type=float,
        default=Report.DEFAULT_GRADE_MIN,
        help="Minimum grade.",
    )
    parser.add_argument(
        "--grade-min-value",
        type=float,
        default=Report.DEFAULT_GRADE_MIN_VALUE,
        help="Minimum grade value.",
    )
    parser.add_argument(
        "--grade-max",
        type=float,
        default=Report.DEFAULT_GRADE_MAX,
        help="Maximum grade.",
    )
    return parser.parse_args()


def main():
    """
    Main entry point for the TPAutoCorrect tool.

    Parses arguments, sets up sources, runs the tester, handles report generation and optional git push.

    Returns:
        str: The final grade as a formatted string.
    """
    args = parse_args()
    code_source = SourceCode(src_path=args.code_src_path, url=args.code_src_url)
    test_source = SourceTests(src_path=args.tests_src_path, url=args.tests_src_url)
    logging_func = print if args.debug else Tester.DEFAULT_LOGGING_FUNC
    if args.master_code_src_path is None and args.master_code_src_url is None:
        master_code_source = None
    else:
        master_code_source = SourceMasterCode(
            src_path=args.master_code_src_path, url=args.master_code_src_url
        )
    if args.master_tests_src_path is None and args.master_tests_src_url is None:
        master_tests_source = None
    else:
        master_tests_source = SourceMasterTests(
            src_path=args.master_tests_src_path, url=args.master_tests_src_url
        )
    weights = Tester.DEFAULT_WEIGHTS.copy()
    weights.update(
        {
            key: getattr(args, f"{key}_weight", default_weight)
            for key, default_weight in Tester.DEFAULT_WEIGHTS.items()
        }
    )
    report_kwargs = {
        "grade_min": args.grade_min,
        "grade_min_value": args.grade_min_value,
        "grade_max": args.grade_max,
    }
    tester = Tester(
        code_source,
        test_source,
        master_code_src=master_code_source,
        master_tests_src=master_tests_source,
        report_dir=args.report_dir,
        logging_func=logging_func,
        weights=weights,
        report_kwargs=report_kwargs,
    )
    tester.run(
        overwrite=args.overwrite,
        debug=args.debug,
        clear_pytest_temporary_files=args.clear_pytest_temporary_files,
    )
    report = tester.report
    if args.push_report_to is not None:
        try:
            tester.push_report_to(args.push_report_to)
        except Exception as err:
            tester.logging_func(
                f"Error while pushing report to {args.push_report_to}: {err}"
            )
    if args.rm_report_dir:
        tester.rm_report_dir()
    return f"Points {int(report.grade)}/100"


if __name__ == "__main__":
    # Example of command:
    # python -m tac --code-src-path="Example/SimpleTP/src" --tests-src-path="Example/SimpleTP/tests" --debug --overwrite
    sys.exit(main())
