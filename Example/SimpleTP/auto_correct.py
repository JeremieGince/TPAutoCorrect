import sys
import os
try:
    import tac
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    import tac


def auto_correct_default():
    auto_corrector = tac.Tester(report_dir="report_dir_default")
    auto_corrector.run(overwrite=False, debug=True)
    print(auto_corrector.report)


def auto_correct():
    code_source = tac.SourceCode(logging_func=print)
    print(code_source)
    tests_source = tac.SourceTests(logging_func=print)
    print(tests_source)
    master_tests_source = tac.SourceTests(os.path.join(os.path.dirname(__file__), "master_tests"), logging_func=print)
    print(master_tests_source)
    auto_corrector = tac.Tester(
        code_source, tests_source,
        master_tests_src=master_tests_source,
        report_dir="report_dir",
    )
    auto_corrector.run(overwrite=False, debug=True)
    print(auto_corrector.report)


def auto_correct_from_git():
    path_to_example = os.path.join(".", "Example", "SimpleTP")
    repo_url = tac.__url__
    code_source = tac.SourceCode(os.path.join(path_to_example, "src"), url=repo_url, logging_func=print)
    print(code_source)
    tests_source = tac.SourceTests(os.path.join(path_to_example, "tests"), url=repo_url, logging_func=print)
    print(tests_source)
    master_tests_source = tac.SourceTests(
        os.path.join(path_to_example, "master_tests"), url=repo_url, logging_func=print
    )
    print(master_tests_source)
    auto_corrector = tac.Tester(
        code_source, tests_source,
        master_tests_src=master_tests_source,
        report_dir="report_dir_git",
    )
    auto_corrector.run(overwrite=False, debug=True)
    print(auto_corrector.report)


if __name__ == "__main__":
    auto_correct_default()
    auto_correct()
    auto_correct_from_git()

