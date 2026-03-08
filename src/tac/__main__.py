"""
Command-line interface for TPAutoCorrect.

This module provides a CLI for running automated grading on student code.
"""

import argparse
import sys

from . import (
    Report,
    SourceBaseTests,
    SourceCode,
    SourceHiddenTests,
    SourceMasterCode,
    SourceSuppTests,
    Tester,
)


def parse_args():
    """
    Parse command-line arguments for the TPAutoCorrect tool.

    :return: The parsed command-line arguments.
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser(
        description="TPAutoCorrect - Automated homework grading tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Student code and tests
    parser.add_argument(
        "--code-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the student code to be tested.",
    )
    parser.add_argument(
        "--code-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the student code.",
    )
    parser.add_argument(
        "--tests-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the tests for the student code.",
    )
    parser.add_argument(
        "--tests-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the tests.",
    )

    # Master code and tests
    parser.add_argument(
        "--master-code-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the master/reference code.",
    )
    parser.add_argument(
        "--master-code-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the master code.",
    )
    parser.add_argument(
        "--master-tests-src-path",
        type=str,
        default=None,
        help="Path to the directory containing the master tests.",
    )
    parser.add_argument(
        "--master-tests-src-url",
        type=str,
        default=None,
        help="URL to the git repository containing the master tests.",
    )

    # Report configuration
    parser.add_argument(
        "--report-dir",
        type=str,
        default=None,
        help="Path to the directory to save the report and temporary files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files during setup.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with verbose output.",
    )

    # Git operations
    parser.add_argument(
        "--push-report-to",
        type=str,
        default=None,
        help="Push report file to a git repository. " "Use 'auto' to auto-detect from the current project.",
    )
    parser.add_argument(
        "--clear-pytest-temporary-files",
        action="store_true",
        help="Clear pytest temporary files after running.",
    )

    # Metric weights
    for key, default_weight in Tester.DEFAULT_WEIGHTS.items():
        parser.add_argument(
            f"--{key.replace('_', '-')}-weight",
            type=float,
            default=default_weight,
            help=f"Weight of the {key} metric in the final score (0-100).",
        )

    # Cleanup
    parser.add_argument(
        "--rm-report-dir",
        action="store_true",
        help="Remove the report directory after completion. " "Useful when pushing reports to git.",
    )

    # Grade configuration
    parser.add_argument(
        "--score-min",
        type=float,
        default=Report.DEFAULT_SCORE_MIN,
        help="Input weighted-sum zero-point (maps to --grade-floor).",
    )
    parser.add_argument(
        "--grade-floor",
        type=float,
        default=Report.DEFAULT_GRADE_FLOOR,
        help="Output grade when weighted sum equals --score-min.",
    )
    parser.add_argument(
        "--score-max",
        type=float,
        default=Report.DEFAULT_SCORE_MAX,
        help="Input weighted-sum ceiling.",
    )

    # Package manager
    parser.add_argument(
        "--no-uv",
        action="store_true",
        help="Disable uv package manager and use only pip.",
    )

    return parser.parse_args()


def main():
    """
    Main entry point for the TPAutoCorrect CLI.

    Parses arguments, sets up sources, runs the tester, and handles
    report generation and optional git push.

    :return: Final grade message.
    :rtype: str
    """
    args = parse_args()

    # Determine whether to use uv
    use_uv = not args.no_uv

    # Setup logging function
    logging_func = print if args.debug else Tester.DEFAULT_LOGGING_FUNC

    # Create student sources
    code_source = SourceCode(
        src_path=args.code_src_path,
        url=args.code_src_url,
        logging_func=logging_func,
        use_uv=use_uv,
    )

    test_source = SourceSuppTests(
        src_path=args.tests_src_path,
        url=args.tests_src_url,
        logging_func=logging_func,
    )

    # Create master sources if provided
    if args.master_code_src_path or args.master_code_src_url:
        master_code_source = SourceMasterCode(
            src_path=args.master_code_src_path,
            url=args.master_code_src_url,
            logging_func=logging_func,
            use_uv=use_uv,
        )
    else:
        master_code_source = None

    if args.master_tests_src_path or args.master_tests_src_url:
        import os

        master_tests_root = args.master_tests_src_path
        base_tests_source = SourceBaseTests(
            src_path=os.path.join(master_tests_root, "base_tests") if master_tests_root else None,
            url=args.master_tests_src_url,
            logging_func=logging_func,
        )
        hidden_tests_source = SourceHiddenTests(
            src_path=os.path.join(master_tests_root, "hidden_tests") if master_tests_root else None,
            url=args.master_tests_src_url,
            logging_func=logging_func,
        )
    else:
        base_tests_source = None
        hidden_tests_source = None

    # Build weights from arguments
    weights = {}
    for key in Tester.DEFAULT_WEIGHTS.keys():
        arg_name = f"{key}_weight".replace("-", "_")
        if hasattr(args, arg_name):
            weights[key] = getattr(args, arg_name)

    # Build report configuration
    report_kwargs = {
        "score_min": args.score_min,
        "grade_floor": args.grade_floor,
        "score_max": args.score_max,
    }

    # Create tester
    tester = Tester(
        code_source,
        test_source,
        master_code_src=master_code_source,
        base_tests_src=base_tests_source,
        hidden_tests_src=hidden_tests_source,
        report_dir=args.report_dir,
        logging_func=logging_func,
        weights=weights,
        report_kwargs=report_kwargs,
    )

    # Run tests
    try:
        tester.run(
            overwrite=args.overwrite,
            debug=args.debug,
            clear_pytest_temporary_files=args.clear_pytest_temporary_files,
        )

        report = tester.report

        # Push report if requested
        if args.push_report_to is not None:
            try:
                tester.push_report_to(args.push_report_to)
            except Exception as err:
                logging_func(f"Error pushing report to {args.push_report_to}: {err}")

        # Remove report directory if requested
        if args.rm_report_dir:
            tester.rm_report_dir()

        # Print final grade
        grade_message = f"Points {int(report.grade)}/100"
        print(f"\n{'=' * 50}")
        print(f"FINAL GRADE: {grade_message}")
        print(f"{'=' * 50}\n")

        return grade_message

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        if args.debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Example usage:
    # python -m tac --code-src-path="Example/SimpleTP/src" --tests-src-path="Example/SimpleTP/tests" --debug --overwrite
    sys.exit(main() or 0)
