import os
import shutil
import sys
from contextlib import contextmanager
from importlib import util as importlib_util
from typing import List, Optional, Union


def find_filepath(filename: str, root: Optional[str] = None) -> Optional[str]:
    root = root or os.getcwd()
    for root, dirs, files in os.walk(root):
        for file in files:
            if file == filename:
                return os.path.join(root, file)
    return None


def find_dir(dirname: str, root: Optional[str] = None) -> Optional[str]:
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
    try:
        shutil.rmtree(path, ignore_errors=ignore_errors, onerror=shutil_onerror)
    except FileNotFoundError:
        pass


def try_rm_trees(paths: Union[str, List[str]], ignore_errors: bool = True):
    if isinstance(paths, str):
        paths = [paths]
    for path in paths:
        try_rmtree(path, ignore_errors=ignore_errors)


def rm_direnames_from_root(dirnames: Union[str, List[str]], root: Optional[str] = None):
    if isinstance(dirnames, str):
        dirnames = [dirnames]
    root = root or os.getcwd()
    for root, dirs, files in os.walk(root):
        for dir in dirs:
            if dir in dirnames:
                try_rmtree(os.path.join(root, dir))
    return True


def rm_filetypes_from_root(
    filetypes: Union[str, List[str]], root: Optional[str] = None
):
    if isinstance(filetypes, str):
        filetypes = [filetypes]
    root = root or os.getcwd()
    for root, dirs, files in os.walk(root):
        for file in files:
            if any([file.endswith(filetype) for filetype in filetypes]):
                try_rmtree(os.path.join(root, file))
    return True


def rm_pycache(root: Optional[str] = None):
    return rm_direnames_from_root("__pycache__", root=root)


def rm_pyc_files(root: Optional[str] = None):
    return rm_filetypes_from_root(".pyc", root=root)


def rm_pyo_files(root: Optional[str] = None):
    return rm_filetypes_from_root(".pyo", root=root)


def rm_pytest_cache(root: Optional[str] = None):
    return rm_direnames_from_root(".pytest_cache", root=root)


def reindent_json_file(filepath: str, indent: int = 4, dont_exist_ok: bool = True):
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
    for root, dirs, files in os.walk(dirpath):
        for file in files:
            if file == filename:
                return True
    return False


def is_subpath_in_path(subpath: str, path: str) -> bool:
    subpath = os.path.abspath(subpath)
    path = os.path.abspath(path)
    return subpath in path


@contextmanager
def add_to_path(p):
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
    def __init__(self, filepath: str):
        self.filepath = os.path.abspath(os.path.normpath(filepath))
        self._module = None
        self._spec = None
        self.added_sys_modules = []

    @property
    def module_name(self):
        return self.get_module_name(self.filepath)

    @property
    def module(self):
        if self._module is None:
            self._module, self._spec = self.path_import()
        return self._module

    @property
    def spec(self):
        if self._spec is None:
            self._module, self._spec = self.path_import()
        return self._spec

    def add_sys_module(self, module_name: str, module):
        self.added_sys_modules.append(module_name)
        sys.modules[module_name] = module
        return self

    def remove_sys_module(self, module_name: str):
        if module_name in self.added_sys_modules:
            self.added_sys_modules.remove(module_name)
        if module_name in sys.modules:
            sys.modules.pop(module_name)
        return self

    def clear_sys_modules(self):
        for module_name in self.added_sys_modules:
            if module_name in sys.modules:
                sys.modules.pop(module_name)
        self.added_sys_modules = []
        return self

    def add_sibling_modules(self, sibling_dirname: Optional[str] = None):
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
        filepath = filepath or self.filepath
        filename = os.path.basename(filepath)
        module_name = filename.rsplit(".", 1)[0]
        return module_name

    def path_import(self, absolute_path: Optional[str] = None):
        absolute_path = absolute_path or self.filepath
        spec = importlib_util.spec_from_file_location(
            self.get_module_name(absolute_path), absolute_path
        )
        module = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self._module, self._spec = module, spec
        return module, spec

    def __repr__(self):
        return f"{self.__class__.__name__}(filepath={self.filepath})"


def get_module_from_file(filepath: str):
    path_import = PathImport(filepath)
    try:
        module, spec = path_import.path_import()
    except (ImportError, ModuleNotFoundError) as err:
        path_import.add_sibling_modules()
        module, spec = path_import.path_import()
    return module


def import_obj_from_file(obj_name: str, filepath: str):
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


def get_git_repo_url(
    working_dir: str, search_parent_directories: bool = True
) -> Optional[str]:
    try:
        import git

        repo = git.Repo(
            working_dir, search_parent_directories=search_parent_directories
        )
        return repo.remotes.origin.url
    except Exception:
        return None
