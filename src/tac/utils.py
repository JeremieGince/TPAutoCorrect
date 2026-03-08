"""
Utility functions for the TPAutoCorrect package.

This module provides various helper functions for file operations, git operations,
module imports, and package management with uv/pip fallback support.
"""

import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from importlib import util as importlib_util
from pathlib import Path
from typing import List, Optional, Tuple, Union


def check_uv_available() -> bool:
    """
    Check if uv package manager is available in the system.

    :return: True if uv is available, False otherwise.
    :rtype: bool
    """
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_package(
    package: str,
    venv_path: Optional[str] = None,
    use_uv: bool = True,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """
    Install a Python package using uv or pip as fallback.

    :param package: Package name or requirement specification.
    :type package: str
    :param venv_path: Path to virtual environment. If None, installs globally.
    :type venv_path: Optional[str]
    :param use_uv: Whether to attempt using uv first. Defaults to True.
    :type use_uv: bool
    :param timeout: Command timeout in seconds. Defaults to 300.
    :type timeout: int
    :return: CompletedProcess object from subprocess.
    :rtype: subprocess.CompletedProcess
    :raises subprocess.CalledProcessError: If both uv and pip fail.
    """
    if use_uv and check_uv_available():
        try:
            if venv_path:
                cmd = ["uv", "pip", "install", "--python", venv_path, package]
            else:
                cmd = ["uv", "pip", "install", package]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
            return result
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"uv install failed: {e}. Falling back to pip...")

    # Fallback to pip
    if venv_path:
        python_path = _get_venv_python_path(venv_path)
        cmd = [python_path, "-m", "pip", "install", package]
    else:
        cmd = [sys.executable, "-m", "pip", "install", package]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    return result


def install_from_pyproject(
    pyproject_path: str,
    venv_path: Optional[str] = None,
    use_uv: bool = True,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """
    Install packages from pyproject.toml using uv or pip as fallback.

    :param pyproject_path: Path to pyproject.toml file.
    :type pyproject_path: str
    :param venv_path: Path to virtual environment. If None, installs globally.
    :type venv_path: Optional[str]
    :param use_uv: Whether to attempt using uv first. Defaults to True.
    :type use_uv: bool
    :param timeout: Command timeout in seconds. Defaults to 600.
    :type timeout: int
    :return: CompletedProcess object from subprocess.
    :rtype: subprocess.CompletedProcess
    :raises FileNotFoundError: If pyproject.toml doesn't exist.
    :raises subprocess.CalledProcessError: If both uv and pip fail.
    """
    if not os.path.exists(pyproject_path):
        raise FileNotFoundError(f"pyproject.toml not found: {pyproject_path}")

    project_dir = os.path.dirname(pyproject_path)

    if use_uv and check_uv_available():
        try:
            # uv can install from pyproject.toml directory
            if venv_path:
                cmd = ["uv", "pip", "install", "--python", venv_path, "-e", project_dir]
            else:
                cmd = ["uv", "pip", "install", "-e", project_dir]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
            return result
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"uv install failed: {e}. Falling back to pip...")

    # Fallback to pip
    if venv_path:
        python_path = _get_venv_python_path(venv_path)
        cmd = [python_path, "-m", "pip", "install", "-e", project_dir]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-e", project_dir]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    return result


def install_requirements(
    requirements_path: str,
    venv_path: Optional[str] = None,
    use_uv: bool = True,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """
    Install packages from requirements.txt using uv or pip as fallback.

    :param requirements_path: Path to requirements.txt file.
    :type requirements_path: str
    :param venv_path: Path to virtual environment. If None, installs globally.
    :type venv_path: Optional[str]
    :param use_uv: Whether to attempt using uv first. Defaults to True.
    :type use_uv: bool
    :param timeout: Command timeout in seconds. Defaults to 600.
    :type timeout: int
    :return: CompletedProcess object from subprocess.
    :rtype: subprocess.CompletedProcess
    :raises FileNotFoundError: If requirements file doesn't exist.
    :raises subprocess.CalledProcessError: If both uv and pip fail.
    """
    if not os.path.exists(requirements_path):
        raise FileNotFoundError(f"Requirements file not found: {requirements_path}")

    if use_uv and check_uv_available():
        try:
            if venv_path:
                cmd = [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    venv_path,
                    "-r",
                    requirements_path,
                ]
            else:
                cmd = ["uv", "pip", "install", "-r", requirements_path]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
            return result
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"uv install failed: {e}. Falling back to pip...")

    # Fallback to pip
    if venv_path:
        python_path = _get_venv_python_path(venv_path)
        cmd = [python_path, "-m", "pip", "install", "-r", requirements_path]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "-r", requirements_path]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    return result


# Platform-specific path to the scripts/bin directory inside a venv.
# Format-string: use ``VENV_SCRIPTS_FOLDER_BY_OS[sys.platform].format(venv_path)``.
VENV_SCRIPTS_FOLDER_BY_OS: dict = {
    "win32": "{}/Scripts",
    "linux": "{}/bin",
    "darwin": "{}/bin",
}


def _get_venv_python_path(venv_path: str) -> str:
    """
    Get the Python executable path for a virtual environment.

    Uses :data:`VENV_SCRIPTS_FOLDER_BY_OS` for platform detection.

    :param venv_path: Path to the virtual environment.
    :type venv_path: str
    :return: Path to the Python executable.
    :rtype: str
    """
    scripts_folder = VENV_SCRIPTS_FOLDER_BY_OS.get(sys.platform, "{}/bin").format(venv_path)
    exe = "python.exe" if sys.platform == "win32" else "python"
    return os.path.join(scripts_folder, exe)


def find_filepath(filename: str, root: Optional[str] = None) -> Optional[str]:
    """
    Find the first occurrence of a file with the given filename in the directory tree.

    :param filename: The name of the file to search for.
    :type filename: str
    :param root: The root directory to start searching from. Defaults to current working directory.
    :type root: Optional[str]
    :return: The full path to the file if found, otherwise None.
    :rtype: Optional[str]
    """
    root = root or os.getcwd()
    for dirpath, dirnames, files in os.walk(root):
        if filename in files:
            return os.path.join(dirpath, filename)
    return None


def find_dir(dirname: str, root: Optional[str] = None) -> Optional[str]:
    """
    Find the first occurrence of a directory with the given name in the directory tree.

    :param dirname: The name of the directory to search for.
    :type dirname: str
    :param root: The root directory to start searching from. Defaults to current working directory.
    :type root: Optional[str]
    :return: The full path to the directory if found, otherwise None.
    :rtype: Optional[str]
    """
    root = root or os.getcwd()
    for dirpath, dirnames, files in os.walk(root):
        if dirname in dirnames:
            return os.path.join(dirpath, dirname)
    return None


def shutil_onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.
    If the error is for another reason it re-raises the error.

    Usage: ``shutil.rmtree(path, onerror=shutil_onerror)``

    :param func: Function that raised the error.
    :type func: callable
    :param path: Path that caused the error.
    :type path: str
    :param exc_info: Exception information.
    :type exc_info: tuple
    """
    import stat

    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise exc_info[1].with_traceback(exc_info[2])


def rm_file(filepath: Optional[str] = None) -> None:
    """
    Remove a file if it exists.

    :param filepath: The path to the file to remove. If None, does nothing.
    :type filepath: Optional[str]
    :raises ValueError: If the path exists but is not a file.
    """
    if filepath is None or not os.path.exists(filepath):
        return

    if not os.path.isfile(filepath):
        raise ValueError(f"filepath must be a file, got {filepath}")

    try:
        os.remove(filepath)
    except PermissionError:
        import sys

        shutil_onerror(os.remove, filepath, sys.exc_info())


def try_rmtree(path: str, ignore_errors: bool = True) -> None:
    """
    Attempt to remove a directory tree, ignoring errors if specified.

    :param path: The directory path to remove.
    :type path: str
    :param ignore_errors: Whether to ignore errors. Defaults to True.
    :type ignore_errors: bool
    """
    try:
        shutil.rmtree(path, onerror=shutil_onerror)
    except FileNotFoundError:
        pass
    except Exception:
        if not ignore_errors:
            raise


def try_rm_trees(paths: Union[str, List[str]], ignore_errors: bool = True) -> None:
    """
    Remove one or more directory trees.

    :param paths: A single path or a list of paths to remove.
    :type paths: Union[str, List[str]]
    :param ignore_errors: Whether to ignore errors. Defaults to True.
    :type ignore_errors: bool
    """
    if isinstance(paths, str):
        paths = [paths]
    for path in paths:
        try_rmtree(path, ignore_errors=ignore_errors)


def rm_direnames_from_root(dirnames: Union[str, List[str]], root: Optional[str] = None) -> bool:
    """
    Remove directories with specified names from the directory tree starting at root.

    :param dirnames: Directory name or list of names to remove.
    :type dirnames: Union[str, List[str]]
    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str]
    :return: Always returns True.
    :rtype: bool
    """
    if isinstance(dirnames, str):
        dirnames = [dirnames]
    root = root or os.getcwd()
    for dirpath, dirs, files in os.walk(root):
        for dirname in dirs:
            if dirname in dirnames:
                try_rmtree(os.path.join(dirpath, dirname))
    return True


def rm_filetypes_from_root(filetypes: Union[str, List[str]], root: Optional[str] = None) -> bool:
    """
    Remove files with specified extensions from the directory tree starting at root.

    :param filetypes: File extension or list of extensions to remove.
    :type filetypes: Union[str, List[str]]
    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str]
    :return: Always returns True.
    :rtype: bool
    """
    if isinstance(filetypes, str):
        filetypes = [filetypes]
    root = root or os.getcwd()
    for dirpath, dirs, files in os.walk(root):
        for file in files:
            if any(file.endswith(filetype) for filetype in filetypes):
                rm_file(os.path.join(dirpath, file))
    return True


def rm_pycache(root: Optional[str] = None) -> bool:
    """
    Remove all __pycache__ directories from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str]
    :return: Always returns True.
    :rtype: bool
    """
    return rm_direnames_from_root("__pycache__", root=root)


def rm_pyc_files(root: Optional[str] = None) -> bool:
    """
    Remove all .pyc files from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str]
    :return: Always returns True.
    :rtype: bool
    """
    return rm_filetypes_from_root(".pyc", root=root)


def rm_pyo_files(root: Optional[str] = None) -> bool:
    """
    Remove all .pyo files from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str]
    :return: Always returns True.
    :rtype: bool
    """
    return rm_filetypes_from_root(".pyo", root=root)


def rm_pytest_cache(root: Optional[str] = None) -> bool:
    """
    Remove all .pytest_cache directories from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str]
    :return: Always returns True.
    :rtype: bool
    """
    return rm_direnames_from_root(".pytest_cache", root=root)


def reindent_json_file(filepath: str, indent: int = 4, dont_exist_ok: bool = True) -> Optional[str]:
    """
    Reformat a JSON file with the specified indentation.

    :param filepath: Path to the JSON file.
    :type filepath: str
    :param indent: Number of spaces for indentation. Defaults to 4.
    :type indent: int
    :param dont_exist_ok: If True, do nothing if file does not exist. If False, raise FileNotFoundError.
    :type dont_exist_ok: bool
    :return: The filepath if successful, otherwise None.
    :rtype: Optional[str]
    :raises FileNotFoundError: If file doesn't exist and dont_exist_ok is False.
    :raises ValueError: If filepath is not a file.
    """
    if not os.path.exists(filepath):
        if dont_exist_ok:
            return None
        raise FileNotFoundError(f"File {filepath} does not exist")

    if not os.path.isfile(filepath):
        raise ValueError(f"File {filepath} must be a file.")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)

    return filepath


def is_file_in_dir(filename: str, dirpath: str) -> bool:
    """
    Check if a file with the given name exists in the directory tree.

    :param filename: The name of the file to search for.
    :type filename: str
    :param dirpath: The directory path to search in.
    :type dirpath: str
    :return: True if the file is found, False otherwise.
    :rtype: bool
    """
    return find_filepath(filename, root=dirpath) is not None


def is_subpath_in_path(subpath: str, path: str) -> bool:
    """
    Check if subpath is contained within path or vice-versa using proper path-prefix semantics.

    :param subpath: The subpath to check.
    :type subpath: str
    :param path: The main path.
    :type path: str
    :return: True if one path is a prefix of the other, False otherwise.
    :rtype: bool
    """
    subpath_p = Path(os.path.abspath(subpath))
    path_p = Path(os.path.abspath(path))
    try:
        subpath_p.relative_to(path_p)
        return True
    except ValueError:
        pass
    try:
        path_p.relative_to(subpath_p)
        return True
    except ValueError:
        return False


@contextmanager
def add_path(p: str):
    """
    Temporarily add a path to sys.path and sys.modules.

    :param p: Path to add.
    :type p: str
    :yields: None
    """
    old_path = sys.path[:]
    old_modules = sys.modules.copy()
    sys.path.insert(0, p)
    try:
        yield
    finally:
        sys.path = old_path
        sys.modules = old_modules


class PathImport:
    """
    Utility class for importing Python modules from file paths.

    :param filepath: The path to the Python file to import.
    :type filepath: str
    """

    def __init__(self, filepath: str):
        """
        Initialize PathImport with a file path.

        :param filepath: The path to the Python file to import.
        :type filepath: str
        """
        self.filepath = os.path.abspath(os.path.normpath(filepath))
        self._module: Optional[object] = None
        self._spec: Optional[object] = None
        self.added_sys_modules: List[str] = []

    @property
    def module_name(self) -> str:
        """
        The module name derived from the file path.

        :return: The module name.
        :rtype: str
        """
        return self.get_module_name(self.filepath)

    @property
    def module(self):
        """
        The imported module object.

        :return: The imported module.
        """
        if self._module is None:
            self._module, self._spec = self.path_import()
        return self._module

    @property
    def spec(self):
        """
        The importlib spec object for the module.

        :return: The importlib spec object.
        """
        if self._spec is None:
            self._module, self._spec = self.path_import()
        return self._spec

    def add_sys_module(self, module_name: str, module) -> "PathImport":
        """
        Add a module to sys.modules.

        :param module_name: The name to use in sys.modules.
        :type module_name: str
        :param module: The module object.
        :return: self for method chaining.
        :rtype: PathImport
        """
        self.added_sys_modules.append(module_name)
        sys.modules[module_name] = module
        return self

    def remove_sys_module(self, module_name: str) -> "PathImport":
        """
        Remove a module from sys.modules.

        :param module_name: The name to remove from sys.modules.
        :type module_name: str
        :return: self for method chaining.
        :rtype: PathImport
        """
        if module_name in self.added_sys_modules:
            self.added_sys_modules.remove(module_name)
        if module_name in sys.modules:
            sys.modules.pop(module_name)
        return self

    def clear_sys_modules(self) -> "PathImport":
        """
        Remove all modules added by this instance from sys.modules.

        :return: self for method chaining.
        :rtype: PathImport
        """
        for module_name in self.added_sys_modules:
            if module_name in sys.modules:
                sys.modules.pop(module_name)
        self.added_sys_modules = []
        return self

    def add_sibling_modules(self, sibling_dirname: Optional[str] = None) -> "PathImport":
        """
        Import and add all sibling Python modules in the same directory to sys.modules.

        :param sibling_dirname: Directory to search for sibling modules. Defaults to the file's directory.
        :type sibling_dirname: Optional[str]
        :return: self for method chaining.
        :rtype: PathImport
        """
        sibling_dirname = sibling_dirname or os.path.dirname(self.filepath)
        skip_pyfiles = [os.path.basename(self.filepath), "__init__.py", "__main__.py"]

        for current, subdirs, files in os.walk(sibling_dirname):
            for file_py in files:
                if not file_py.endswith(".py") or file_py in skip_pyfiles:
                    continue

                python_file = os.path.join(current, file_py)
                module, spec = self.path_import(python_file)
                self.add_sys_module(spec.name, module)

        return self

    def get_module_name(self, filepath: Optional[str] = None) -> str:
        """
        Get the module name from a file path.

        :param filepath: The file path. Defaults to self.filepath.
        :type filepath: Optional[str]
        :return: The module name.
        :rtype: str
        """
        filepath = filepath or self.filepath
        filename = os.path.basename(filepath)
        module_name = filename.rsplit(".", 1)[0]
        return module_name

    def path_import(self, absolute_path: Optional[str] = None):
        """
        Import a module from a file path.

        :param absolute_path: The absolute path to the file. Defaults to self.filepath.
        :type absolute_path: Optional[str]
        :return: The imported module and its spec.
        :rtype: tuple
        """
        absolute_path = absolute_path or self.filepath
        spec = importlib_util.spec_from_file_location(self.get_module_name(absolute_path), absolute_path)

        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {absolute_path}")

        module = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module, self._spec = module, spec
        return module, spec

    def __repr__(self) -> str:
        """
        Return a string representation of the PathImport instance.

        :return: String representation.
        :rtype: str
        """
        return f"{self.__class__.__name__}(filepath={self.filepath})"


def get_module_from_file(filepath: str):
    """
    Import and return a module from a file path, handling sibling imports if necessary.

    :param filepath: The path to the Python file.
    :type filepath: str
    :return: The imported module object.
    """
    path_import = PathImport(filepath)
    try:
        module, spec = path_import.path_import()
    except (ImportError, ModuleNotFoundError):
        path_import.add_sibling_modules()
        module, spec = path_import.path_import()
    return module


def import_obj_from_file(obj_name: str, filepath: str):
    """
    Import an object by name from a Python file.

    :param obj_name: The name of the object to import.
    :type obj_name: str
    :param filepath: The path to the Python file.
    :type filepath: str
    :return: The imported object.
    :raises AttributeError: If the object doesn't exist in the module.
    """
    module = get_module_from_file(filepath)
    return getattr(module, obj_name)


def push_file_to_git_repo(
    filepath: str,
    repo_url: str,
    repo_branch: str = "main",
    local_tmp_path: str = "tmp_repo",
    rm_tmp_repo: bool = True,
) -> bool:
    """
    Push a file to a remote git repository.

    :param filepath: The path to the file to push.
    :type filepath: str
    :param repo_url: The URL of the remote git repository.
    :type repo_url: str
    :param repo_branch: The branch to push to. Defaults to "main".
    :type repo_branch: str
    :param local_tmp_path: Temporary local path for the repo clone. Defaults to "tmp_repo".
    :type local_tmp_path: str
    :param rm_tmp_repo: Whether to remove the temporary repo after pushing. Defaults to True.
    :type rm_tmp_repo: bool
    :return: True if successful.
    :rtype: bool
    :raises ImportError: If GitPython is not installed.
    """
    import git
    from git import rmtree

    repo = git.Repo.clone_from(repo_url, local_tmp_path)
    repo.git.checkout(repo_branch)

    file_basename = os.path.basename(filepath)
    new_filepath = os.path.join(local_tmp_path, file_basename)
    shutil.copy(filepath, new_filepath)

    repo.git.add(file_basename)
    repo.git.commit("-m", f"Add {file_basename}")
    repo.git.push("origin", repo_branch)

    if rm_tmp_repo:
        rmtree(local_tmp_path)

    return True


def get_git_repo_url(working_dir: str, search_parent_directories: bool = True) -> Optional[str]:
    """
    Get the remote URL of the git repository for a given working directory.

    :param working_dir: The directory to search for a git repository.
    :type working_dir: str
    :param search_parent_directories: Whether to search parent directories. Defaults to True.
    :type search_parent_directories: bool
    :return: The remote URL if found, otherwise None.
    :rtype: Optional[str]
    """
    try:
        import git

        repo = git.Repo(working_dir, search_parent_directories=search_parent_directories)
        return repo.remotes.origin.url
    except Exception:
        return None


def get_git_repo_branch(
    working_dir: str,
    search_parent_directories: bool = True,
) -> Optional[str]:
    """
    Get the currently active branch of the git repository at the given path.

    :param working_dir: The directory to search for a git repository.
    :type working_dir: str
    :param search_parent_directories: Whether to search parent directories. Defaults to True.
    :type search_parent_directories: bool
    :return: The active branch name if found, otherwise None.
    :rtype: Optional[str]
    """
    try:
        import git

        repo = git.Repo(working_dir, search_parent_directories=search_parent_directories)
        return repo.active_branch.name
    except Exception:
        return None


def format_name(name: str) -> str:
    """
    Format a name to be filesystem-safe.

    Removes special characters, spaces, and non-ASCII characters.

    :param name: The name to format.
    :type name: str
    :return: The formatted name.
    :rtype: str
    """
    fmt_name = os.path.normpath(name)
    fmt_name = fmt_name.replace(" ", "_")
    fmt_name = fmt_name.replace(":", "")
    fmt_name = fmt_name.encode("ascii", "ignore").decode("ascii")
    return fmt_name


def get_report(
    repo_path: str,
    *,
    master_repo_path: Optional[str] = None,
    weights: Optional[dict] = None,
    push_report: bool = False,
    tmp_report_dir: str = "tmp_report_dir",
    logging_func=print,
    overwrite: bool = False,
    debug: bool = True,
    clear_temporary_files: bool = False,
    clear_pytest_temporary_files: bool = False,
    **kwargs,
):
    """
    Generate an auto-correction report for a student repository.

    Always returns a :class:`~tac.Report` object.  If you also need the PDF
    report path, use :func:`get_report_with_pdf` instead.

    The student repository is expected to have the layout::

        repo/
            src/
            tests/
                supp_tests/   ← student supplementary tests (run with coverage)

    The master repository is expected to have::

        master_repo/
            src/
            tests/
                base_tests/   ← run against student src/ (no coverage)
                hidden_tests/ ← run against student src/ (no coverage)

    :param repo_path: Path to the student repository.
    :type repo_path: str
    :param master_repo_path: Path to the master repository for reference.
    :type master_repo_path: Optional[str]
    :param weights: Weights for different grading criteria.
    :type weights: Optional[dict]
    :param push_report: Whether to push the report to the repository.
    :type push_report: bool
    :param tmp_report_dir: Temporary directory for report generation.
    :type tmp_report_dir: str
    :param logging_func: Logging function. Defaults to ``print``.
    :type logging_func: Callable
    :param overwrite: Passed to :meth:`Tester.run`. Defaults to False.
    :type overwrite: bool
    :param debug: Passed to :meth:`Tester.run`. Defaults to True.
    :type debug: bool
    :param clear_temporary_files: Passed to :meth:`Tester.run`. Defaults to False.
    :type clear_temporary_files: bool
    :param clear_pytest_temporary_files: Passed to :meth:`Tester.run`. Defaults to False.
    :type clear_pytest_temporary_files: bool
    :param kwargs: Additional keyword arguments forwarded to the underlying tester.
    :return: The report object.
    :rtype: tac.Report
    """
    report, _ = get_report_with_pdf(
        repo_path,
        master_repo_path=master_repo_path,
        weights=weights,
        push_report=push_report,
        tmp_report_dir=tmp_report_dir,
        logging_func=logging_func,
        overwrite=overwrite,
        debug=debug,
        clear_temporary_files=clear_temporary_files,
        clear_pytest_temporary_files=clear_pytest_temporary_files,
        _skip_pdf=True,
        **kwargs,
    )
    return report


def get_report_with_pdf(
    repo_path: str,
    *,
    master_repo_path: Optional[str] = None,
    weights: Optional[dict] = None,
    push_report: bool = False,
    tmp_report_dir: str = "tmp_report_dir",
    logging_func=print,
    overwrite: bool = False,
    debug: bool = True,
    clear_temporary_files: bool = False,
    clear_pytest_temporary_files: bool = False,
    _skip_pdf: bool = False,
    **kwargs,
) -> Tuple:
    """
    Generate an auto-correction report and locate the PDF for a student repository.

    Returns a ``(report, pdf_path)`` tuple.  ``pdf_path`` is ``None`` when the PDF
    cannot be found or when the internal ``_skip_pdf`` flag is set (used by
    :func:`get_report`).

    See :func:`get_report` for the full parameter documentation.

    :return: Tuple of ``(Report, Optional[str])`` where the second element is the
        path to the PDF report (or None).
    :rtype: Tuple[tac.Report, Optional[str]]
    """
    import tac

    repo_path = str(Path(repo_path).resolve())

    code_source = tac.SourceCode(
        src_path=os.path.join(repo_path, "src"),
        logging_func=logging_func,
    )
    supp_tests_source = tac.SourceSuppTests(
        src_path=os.path.join(repo_path, "tests", "supp_tests"),
        logging_func=logging_func,
    )

    if master_repo_path is None:
        master_code_source = None
        base_tests_source = None
        hidden_tests_source = None
    else:
        master_repo_path = str(Path(master_repo_path).resolve())
        master_code_source = tac.SourceMasterCode(
            src_path=os.path.join(master_repo_path, "src"),
            logging_func=logging_func,
            local_repo_tmp_dirname="tmp_master_repo",
        )
        base_tests_source = tac.SourceBaseTests(
            src_path=os.path.join(master_repo_path, "tests", "base_tests"),
            logging_func=logging_func,
            local_repo_tmp_dirname="tmp_master_repo",
        )
        hidden_tests_source = tac.SourceHiddenTests(
            src_path=os.path.join(master_repo_path, "tests", "hidden_tests"),
            logging_func=logging_func,
            local_repo_tmp_dirname="tmp_master_repo",
        )

    default_weights = {
        tac.Tester.PEP8_KEY: 20.0,
        tac.Tester.SUPP_TESTS_KEY: 20.0,
        tac.Tester.CODE_COVERAGE_KEY: 20.0,
        tac.Tester.BASE_TESTS_KEY: 20.0,
        tac.Tester.HIDDEN_TESTS_KEY: 20.0,
    }
    weights = {**default_weights, **(weights or {})}

    auto_corrector = tac.Tester(
        code_source,
        supp_tests_source,
        base_tests_src=base_tests_source,
        hidden_tests_src=hidden_tests_source,
        master_code_src=master_code_source,
        report_dir=tmp_report_dir,
        logging_func=logging_func,
        weights=weights,
    )

    auto_corrector.run(
        overwrite=overwrite,
        debug=debug,
        clear_temporary_files=clear_temporary_files,
        clear_pytest_temporary_files=clear_pytest_temporary_files,
    )

    if push_report:
        auto_corrector.push_report_to()

    report_pdf: Optional[str] = None
    if not _skip_pdf:
        report_pdf = get_report_pdf_from_dir(
            tmp_report_dir,
            report_keyname=kwargs.get("report_pdf_keyname", "report"),
            search_in_children=True,
            save_filepath=kwargs.get("save_report_pdf_to"),
        )

    return auto_corrector.report, report_pdf


def get_report_pdf_from_dir(
    report_dir: str,
    *,
    report_keyname: str = "report",
    search_in_children: bool = True,
    save_filepath: Optional[str] = None,
    **kwargs,
) -> Optional[str]:
    """
    Find and optionally copy a PDF report from a directory.

    :param report_dir: Directory to search for the PDF.
    :type report_dir: str
    :param report_keyname: Keyword to match in the PDF filename.
    :type report_keyname: str
    :param search_in_children: Whether to search subdirectories.
    :type search_in_children: bool
    :param save_filepath: Optional path to copy the PDF to.
    :type save_filepath: Optional[str]
    :param kwargs: Additional keyword arguments.
    :return: Path to the found PDF, or None if not found.
    :rtype: Optional[str]
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
                pdf_path = os.path.join(root, file)

                if save_filepath is not None:
                    save_filepath = str(save_filepath)
                    parent = os.path.dirname(save_filepath)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    shutil.copy2(pdf_path, save_filepath)

                return pdf_path

        if not search_in_children:
            break

    return None
