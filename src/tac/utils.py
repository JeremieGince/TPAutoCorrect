import os
import shutil
import sys
from contextlib import contextmanager
from importlib import util as importlib_util
from typing import List, Optional, Union


def find_filepath(filename: str, root: Optional[str] = None) -> Optional[str]:
    """
    Find the first occurrence of a file with the given filename in the directory tree starting at root.

    :param filename: The name of the file to search for.
    :type filename: str
    :param root: The root directory to start searching from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: The full path to the file if found, otherwise None.
    :rtype: Optional[str]
    """
    root = root or os.getcwd()
    for root, dirs, files in os.walk(root):
        for file in files:
            if file == filename:
                return os.path.join(root, file)
    return None


def find_dir(dirname: str, root: Optional[str] = None) -> Optional[str]:
    """
    Find the first occurrence of a directory with the given name in the directory tree starting at root.

    :param dirname: The name of the directory to search for.
    :type dirname: str
    :param root: The root directory to start searching from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: The full path to the directory if found, otherwise None.
    :rtype: Optional[str]
    """
    root = root or os.getcwd()
    for root, dirs, files in os.walk(root):
        for _dir in dirs:
            if _dir == dirname:
                return os.path.join(root, _dir)
    return None


def shutil_onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat

    # Is the error an access error?
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def rm_file(filepath: Optional[str] = None):
    """
    Remove a file if it exists.

    :param filepath: The path to the file to remove. If None, does nothing.
    :type filepath: Optional[str], optional
    :raises ValueError: If the path exists but is not a file.
    """
    if filepath is None:
        return
    if not os.path.exists(filepath):
        return
    if not os.path.isfile(filepath):
        raise ValueError(f"filepath must be a file, got {filepath}")
    try:
        os.remove(filepath)
    except PermissionError:
        shutil_onerror(os.remove, filepath, None)


def try_rmtree(path: str, ignore_errors: bool = True):
    """
    Attempt to remove a directory tree, ignoring errors if specified.

    :param path: The directory path to remove.
    :type path: str
    :param ignore_errors: Whether to ignore errors. Defaults to True.
    :type ignore_errors: bool, optional
    """
    try:
        shutil.rmtree(path, ignore_errors=ignore_errors, onerror=shutil_onerror)
    except FileNotFoundError:
        pass


def try_rm_trees(paths: Union[str, List[str]], ignore_errors: bool = True):
    """
    Remove one or more directory trees.

    :param paths: A single path or a list of paths to remove.
    :type paths: Union[str, List[str]]
    :param ignore_errors: Whether to ignore errors. Defaults to True.
    :type ignore_errors: bool, optional
    """
    if isinstance(paths, str):
        paths = [paths]
    for path in paths:
        try_rmtree(path, ignore_errors=ignore_errors)


def rm_direnames_from_root(dirnames: Union[str, List[str]], root: Optional[str] = None):
    """
    Remove directories with specified names from the directory tree starting at root.

    :param dirnames: Directory name or list of names to remove.
    :type dirnames: Union[str, List[str]]
    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: Always returns True.
    :rtype: bool
    """
    if isinstance(dirnames, str):
        dirnames = [dirnames]
    root = root or os.getcwd()
    for root, dirs, files in os.walk(root):
        for dir in dirs:
            if dir in dirnames:
                try_rmtree(os.path.join(root, dir))
    return True


def rm_filetypes_from_root(filetypes: Union[str, List[str]], root: Optional[str] = None):
    """
    Remove files with specified extensions from the directory tree starting at root.

    :param filetypes: File extension or list of extensions to remove.
    :type filetypes: Union[str, List[str]]
    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: Always returns True.
    :rtype: bool
    """
    if isinstance(filetypes, str):
        filetypes = [filetypes]
    root = root or os.getcwd()
    for root, dirs, files in os.walk(root):
        for file in files:
            if any([file.endswith(filetype) for filetype in filetypes]):
                try_rmtree(os.path.join(root, file))
    return True


def rm_pycache(root: Optional[str] = None):
    """
    Remove all __pycache__ directories from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: Always returns True.
    :rtype: bool
    """
    return rm_direnames_from_root("__pycache__", root=root)


def rm_pyc_files(root: Optional[str] = None):
    """
    Remove all .pyc files from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: Always returns True.
    :rtype: bool
    """
    return rm_filetypes_from_root(".pyc", root=root)


def rm_pyo_files(root: Optional[str] = None):
    """
    Remove all .pyo files from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: Always returns True.
    :rtype: bool
    """
    return rm_filetypes_from_root(".pyo", root=root)


def rm_pytest_cache(root: Optional[str] = None):
    """
    Remove all .pytest_cache directories from the directory tree starting at root.

    :param root: Root directory to start from. Defaults to current working directory.
    :type root: Optional[str], optional
    :return: Always returns True.
    :rtype: bool
    """
    return rm_direnames_from_root(".pytest_cache", root=root)


def reindent_json_file(filepath: str, indent: int = 4, dont_exist_ok: bool = True):
    """
    Reformat a JSON file with the specified indentation.

    :param filepath: Path to the JSON file.
    :type filepath: str
    :param indent: Number of spaces for indentation. Defaults to 4.
    :type indent: int, optional
    :param dont_exist_ok: If True, do nothing if file does not exist. If False, raise FileNotFoundError.
    :type dont_exist_ok: bool, optional
    :return: The filepath if successful, otherwise None.
    :rtype: Optional[str]
    """
    import json

    if not os.path.exists(filepath):
        if dont_exist_ok:
            return None
        raise FileNotFoundError(f"File {filepath} does not exist")
    if not os.path.isfile(filepath):
        raise ValueError(f"File {filepath} must be a file.")

    with open(filepath, "r") as f:
        data = json.load(f)
    with open(filepath, "w") as f:
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
    for root, dirs, files in os.walk(dirpath):
        for file in files:
            if file == filename:
                return True
    return False


def is_subpath_in_path(subpath: str, path: str) -> bool:
    """
    Check if subpath is a substring of path after resolving absolute paths.

    :param subpath: The subpath to check.
    :type subpath: str
    :param path: The path to check within.
    :type path: str
    :return: True if subpath is in path, False otherwise.
    :rtype: bool
    """
    subpath = os.path.abspath(subpath)
    path = os.path.abspath(path)
    return subpath in path


@contextmanager
def add_to_path(p):
    """
    Context manager to temporarily add a directory to sys.path.

    :param p: The path to add to sys.path.
    :type p: str
    """
    import sys

    old_path = sys.path
    old_modules = sys.modules
    sys.modules = old_modules.copy()
    sys.path = sys.path[:]
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
        :param filepath: The path to the Python file to import.
        :type filepath: str
        """
        self.filepath = os.path.abspath(os.path.normpath(filepath))
        self._module: Optional[str] = None
        self._spec: Optional[str] = None
        self.added_sys_modules: List[str] = []

    @property
    def module_name(self):
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

    def add_sys_module(self, module_name: str, module):
        """
        Add a module to sys.modules.

        :param module_name: The name to use in sys.modules.
        :type module_name: str
        :param module: The module object.
        :return: self
        """
        self.added_sys_modules.append(module_name)
        sys.modules[module_name] = module
        return self

    def remove_sys_module(self, module_name: str):
        """
        Remove a module from sys.modules.

        :param module_name: The name to remove from sys.modules.
        :type module_name: str
        :return: self
        """
        if module_name in self.added_sys_modules:
            self.added_sys_modules.remove(module_name)
        if module_name in sys.modules:
            sys.modules.pop(module_name)
        return self

    def clear_sys_modules(self):
        """
        Remove all modules added by this instance from sys.modules.

        :return: self
        """
        for module_name in self.added_sys_modules:
            if module_name in sys.modules:
                sys.modules.pop(module_name)
        self.added_sys_modules = []
        return self

    def add_sibling_modules(self, sibling_dirname: Optional[str] = None):
        """
        Import and add all sibling Python modules in the same directory to sys.modules.

        :param sibling_dirname: Directory to search for sibling modules. Defaults to the file's directory.
        :type sibling_dirname: Optional[str], optional
        :return: self
        """
        sibling_dirname = sibling_dirname or os.path.dirname(self.filepath)
        skip_pyfiles = [os.path.basename(self.filepath), "__init__.py", "__main__.py"]
        for current, subdir, files in os.walk(sibling_dirname):
            for file_py in files:
                python_file = os.path.join(current, file_py)
                if (not file_py.endswith(".py")) or (file_py in skip_pyfiles):
                    continue
                (module, spec) = self.path_import(python_file)
                self.add_sys_module(spec.name, module)
        return self

    def get_module_name(self, filepath: Optional[str] = None):
        """
        Get the module name from a file path.

        :param filepath: The file path. Defaults to self.filepath.
        :type filepath: Optional[str], optional
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
        :type absolute_path: Optional[str], optional
        :return: The imported module and its spec.
        :rtype: Tuple[module, spec]
        """
        absolute_path = absolute_path or self.filepath
        spec = importlib_util.spec_from_file_location(self.get_module_name(absolute_path), absolute_path)
        module: str = importlib_util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(module)  # type: ignore
        self._module, self._spec = module, spec  # type: ignore
        return module, spec

    def __repr__(self):
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
    """
    module = get_module_from_file(filepath)
    obj = getattr(module, obj_name)
    return obj


def push_file_to_git_repo(
    filepath: str,
    repo_url: str,
    repo_branch: str = "main",
    local_tmp_path: str = "tmp_repo",
    rm_tmp_repo: bool = True,
):
    """
    Push a file to a remote git repository.

    :param filepath: The path to the file to push.
    :type filepath: str
    :param repo_url: The URL of the remote git repository.
    :type repo_url: str
    :param repo_branch: The branch to push to. Defaults to "main".
    :type repo_branch: str, optional
    :param local_tmp_path: Temporary local path for the repo clone. Defaults to "tmp_repo".
    :type local_tmp_path: str, optional
    :param rm_tmp_repo: Whether to remove the temporary repo after pushing. Defaults to True.
    :type rm_tmp_repo: bool, optional
    :return: True if successful.
    :rtype: bool
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
    :type search_parent_directories: bool, optional
    :return: The remote URL if found, otherwise None.
    :rtype: Optional[str]
    """
    try:
        import git

        repo = git.Repo(working_dir, search_parent_directories=search_parent_directories)
        return repo.remotes.origin.url
    except Exception:
        return None
