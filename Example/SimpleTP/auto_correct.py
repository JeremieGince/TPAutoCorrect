import os
import sys

try:
    import tac
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    import tac


def auto_correct_default():
    """
    Run the auto-correction process using default settings.

    :returns: None

    :description:
        Creates a Tester instance with a default report directory,
        runs the tests, and prints the report.
    """
    auto_corrector = tac.Tester(report_dir="report_dir_default")
    auto_corrector.run(overwrite=False, debug=True)
    print(auto_corrector.report)


def auto_correct():
    """
    Run the auto-correction process with explicit code, test, and master test sources.

    :returns: None

    :description:
        Sets up SourceCode, SourceSuppTests, and SourceBaseTests,
        runs the tests, and prints the report.
    """
    code_source = tac.SourceCode(logging_func=print)
    print(code_source)
    supp_tests_source = tac.SourceSuppTests(logging_func=print)
    print(supp_tests_source)
    base_tests_source = tac.SourceBaseTests(
        os.path.join(os.path.dirname(__file__), "base_tests"), logging_func=print
    )
    print(base_tests_source)
    auto_corrector = tac.Tester(
        code_source,
        supp_tests_source,
        base_tests_src=base_tests_source,
        report_dir="report_dir",
    )
    auto_corrector.run(overwrite=False, debug=True)
    print(auto_corrector.report)


def auto_correct_from_git():
    """
    Run the auto-correction process using sources from a git repository.

    :returns: None

    :description:
        Sets up SourceCode, SourceSuppTests, and SourceBaseTests from git URLs,
        runs the tests, and prints the report.
    """
    path_to_example = os.path.join(".", "Example", "SimpleTP")
    repo_url = tac.__url__
    code_source = tac.SourceCode(
        os.path.join(path_to_example, "src"), repo_url=repo_url, logging_func=print
    )
    print(code_source)
    supp_tests_source = tac.SourceSuppTests(
        os.path.join(path_to_example, "supp_tests"),
        repo_url=repo_url,
        logging_func=print,
    )
    print(supp_tests_source)
    base_tests_source = tac.SourceBaseTests(
        os.path.join(path_to_example, "base_tests"),
        repo_url=repo_url,
        logging_func=print,
    )
    print(base_tests_source)
    auto_corrector = tac.Tester(
        code_source,
        supp_tests_source,
        base_tests_src=base_tests_source,
        report_dir="report_dir_git",
    )
    auto_corrector.run(overwrite=False, debug=True)
    print(auto_corrector.report)


if __name__ == "__main__":
    auto_correct_default()
    auto_correct()
    auto_correct_from_git()
