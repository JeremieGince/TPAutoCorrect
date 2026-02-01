# mypy: ignore-errors
import logging
import os
import shutil
import subprocess
import sys
from typing import List, Optional

from . import utils


class Source:
    """
    Represents a source of files, which can be either a local directory or a remote git repository.
    Handles copying, cloning, and managing source files for further processing.
    """

    DEFAULT_SRC_DIRNAME = "src"
    DEFAULT_LOGGING_FUNC = logging.info

    # Git
    DEFAULT_REPO_URL = "https://github.com/{}.git"
    DEFAULT_REPO_BRANCH = "main"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a Source object.

        Args:
            src_path (Optional[str]): Path to the source directory or None.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments for configuration.
        """
        self._src_path = src_path
        self.args = args
        self.kwargs = kwargs

        self._repo_url = kwargs.get("repo_url", kwargs.get("url", None))
        if self.is_remote and self._repo_url is None:
            raise ValueError(
                f"Source {self.src_path} doesn't exist locally but no repo url was provided. "
                f"Please make sure the source exists locally or provide a repo url with the "
                f"'url' or 'repo_url' keyword argument."
            )

        self.repo_branch = kwargs.get("repo_branch", self.DEFAULT_REPO_BRANCH)
        self.repo = None
        self.local_repo_tmp_dirname = kwargs.get("local_repo_tmp_dirname", "tmp_git")

        self.working_dir = kwargs.get("working_dir", None)
        self.working_dirname = kwargs.get("working_dirname", None)

        self.logging_func = kwargs.get("logging_func", self.DEFAULT_LOGGING_FUNC)

    @property
    def src_path(self) -> str:
        """
        Return the source path of the object. This is the path from where to copy the source files.
        This can be the path from a local folder or a remote repo.

        Returns:
            str: The source path of the object.
        """
        if self._src_path is None:
            return self._try_find_default_src_dir()
        return self._src_path

    @property
    def local_path(self) -> Optional[str]:
        """
        Return the local path of the object. This is the path where the source files are copied to.
        Will return None if the current object is not setup yet. This path is the join of the working directory
        and the basename of the source path.

        Returns:
            Optional[str]: The local path of the object.
        """
        if self.working_dir is None:
            return None
        basename = self.working_dirname or os.path.basename(self.src_path)
        return os.path.join(self.working_dir, basename)

    @property
    def repo_url(self) -> Optional[str]:
        """
        Return the remote url of the object or in other words the repo url if the source is remote.

        Returns:
            Optional[str]: The remote url of the object.
        """
        return self._repo_url

    @property
    def repo_name(self) -> Optional[str]:
        """
        Return the repo name of the object. This is the name of the repo if the source is remote.

        Returns:
            Optional[str]: The repo name of the object.
        """
        if self.repo_url is None:
            return None
        return self.repo_url.split("/")[-1].split(".")[0]

    @property
    def is_local(self) -> bool:
        """
        Check if the source exists locally and is not remote.

        Returns:
            bool: True if the source is local, False otherwise.
        """
        return os.path.exists(self.src_path) and (not self.is_remote)

    @property
    def is_remote(self) -> bool:
        """
        Check if the source is remote (i.e., has a repo URL).

        Returns:
            bool: True if the source is remote, False otherwise.
        """
        return self.repo_url is not None

    @property
    def is_setup(self) -> bool:
        """
        Check if the local path is set up (i.e., exists).

        Returns:
            bool: True if the local path exists, False otherwise.
        """
        if self.local_path is None:
            return False
        return os.path.exists(self.local_path)

    @property
    def local_repo_tmp_dirpath(self) -> str:
        """
        Get the path to the temporary directory used for cloning the git repository.

        Returns:
            str: The path to the temporary git repo directory.
        """
        return os.path.join(self.working_dir, self.local_repo_tmp_dirname)

    def _try_find_default_src_dir(self, root: Optional[str] = None) -> Optional[str]:
        """
        Try to find the default source directory.

        Args:
            root (Optional[str]): The root directory to search from.

        Returns:
            Optional[str]: The path to the default source directory.

        Raises:
            ValueError: If the default source directory cannot be found.
        """
        if self._src_path is not None:
            return self._src_path
        dirpath = utils.find_dir(self.DEFAULT_SRC_DIRNAME, root=root)
        if dirpath is None:
            raise ValueError(
                f"Could not find default source directory {self.DEFAULT_SRC_DIRNAME}."
                f"Please provide a source directory with the 'src_path' argument."
            )
        return dirpath

    def copy_to_working_dir(self, overwrite=False):
        """
        Copy the source files to the working directory.

        Args:
            overwrite (bool, optional): Whether to overwrite existing files. Defaults to False.
        """
        if self.is_setup and overwrite:
            utils.try_rmtree(self.local_path, ignore_errors=True)
        if self.is_remote:
            self._clone_repo()
        if self._src_path is None:
            self._src_path = self._try_find_default_src_dir()
        shutil.copytree(self.src_path, self.local_path, dirs_exist_ok=True)

    def _clone_repo(self):
        """
        Clone the remote git repository to a temporary directory.

        Returns:
            git.Repo: The cloned git repository object.
        """
        import git

        if os.path.exists(self.local_repo_tmp_dirpath):
            self.logging_func(
                f"No need to clone repo {self.repo_name} from {self.repo_url} to {self.local_repo_tmp_dirpath}."
                f" Repo already exists."
            )
            self.repo = git.Repo(self.local_repo_tmp_dirpath)
        else:
            self.logging_func(
                f"Cloning repo {self.repo_name} from {self.repo_url} to {self.local_repo_tmp_dirpath} ..."
            )
            self.repo = git.Repo.clone_from(
                self.repo_url, self.local_repo_tmp_dirpath, branch=self.repo_branch
            )
            self.logging_func(
                f"Cloning repo {self.repo_name} from {self.repo_url} to {self.local_repo_tmp_dirpath}. Done."
            )
        self.repo.git.checkout(self.repo_branch)
        self.repo.git.pull()
        if self._src_path is None:
            self._src_path = self._try_find_default_src_dir(
                root=self.local_repo_tmp_dirpath
            )
        else:
            self._src_path = os.path.join(self.local_repo_tmp_dirpath, self.src_path)
        return self.repo

    def setup_at(self, dst_path: str = None, overwrite=False, **kwargs) -> str:
        """
        Set up the source at the specified destination path.

        Args:
            dst_path (str, optional): The destination path. Defaults to None.
            overwrite (bool, optional): Whether to overwrite existing files. Defaults to False.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The destination path.
        """
        dst_path = dst_path or self.working_dir
        self.working_dir = dst_path
        if overwrite:
            self.clear_temporary_files()
        self.copy_to_working_dir(overwrite=overwrite)
        if kwargs.get("debug", False):
            self.logging_func(self)
        return dst_path

    def send_cmd_to_process(self, cmd: str, timeout: Optional[int] = None, **kwargs):
        """
        Send a shell command to a subprocess and return its output.

        Args:
            cmd (str): The command to execute.
            timeout (Optional[int], optional): Timeout for the command. Defaults to None.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The standard output from the command.
        """
        fmt_cmd = f"{cmd}" + ("\n" if not cmd.endswith("\n") else "")
        process = subprocess.Popen(
            fmt_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            universal_newlines=True,
            encoding="utf8",
            errors="ignore",
            cwd=kwargs.get("cwd", os.path.normpath(self.working_dir)),
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return stdout

    def clear_git_repo(self):
        """
        Remove the temporary cloned git repository, if it exists.
        """
        if self.local_repo_tmp_dirpath is None:
            return
        if os.path.exists(self.local_repo_tmp_dirpath):
            from git import rmtree

            try:
                rmtree(self.local_repo_tmp_dirpath)
            except PermissionError:
                self.logging_func(
                    f"Could not remove repo {self.repo_name} at {self.local_repo_tmp_dirpath}. "
                    f"Please remove it manually."
                )

    def clear_temporary_files(self):
        """
        Remove temporary files and directories associated with this source.
        """
        if self.is_setup:
            utils.try_rmtree(self.local_path, ignore_errors=True)
        self.clear_git_repo()

    def extra_repr(self) -> str:
        """
        Return extra information for the string representation.

        Returns:
            str: Extra representation string.
        """
        return ""

    def __repr__(self):
        """
        Return a string representation of the Source object.

        Returns:
            str: String representation.
        """
        _repr = f"{self.__class__.__name__}(src={self.src_path}"
        if self.working_dir is not None:
            _repr += f", working_dir={self.working_dir}"
        if self.is_local:
            _repr += ", is_local=True"
        else:
            _repr += ", is_remote=True"
            _repr += f", url={self.repo_url}"
        _repr += str(self.extra_repr())
        _repr += ")"
        return _repr

    def __del__(self):
        """
        Destructor to close the git repo if it exists.
        """
        try:
            repo = getattr(self, "repo", None)
            if repo is not None:
                repo.close()
        except Exception:
            pass


class SourceCode(Source):
    """
    Represents a source of code, with additional support for virtual environments and requirements installation.
    """

    # Code
    DEFAULT_CODE_ROOT_FOLDER = "."

    # Venv
    DEFAULT_VENV = "venv"
    VENV_SCRIPTS_FOLDER_BY_OS = {
        "win32": r"{}\Scripts",
        "linux": "{}/bin",
        "darwin": "{}/bin",
    }
    VENV_ACTIVATE_CMD_BY_OS = {
        "win32": r"{}\Scripts\activate.bat",
        "linux": "source {}/bin/activate",
        "darwin": "source {}/bin/activate",
    }
    DEFAULT_SETUP_CMDS = "pip install -r requirements.txt"
    DEFAULT_RECREATE_VENV = True

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a SourceCode object.

        Args:
            src_path (Optional[str]): Path to the source code directory.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments for configuration.
        """
        super().__init__(src_path, *args, **kwargs)
        self.code_root_folder = kwargs.get(
            "code_root_folder", self.DEFAULT_CODE_ROOT_FOLDER
        )
        self.venv = kwargs.get("venv", self.DEFAULT_VENV)
        self.reqs_path = kwargs.get("requirements_path", None)
        self.additional_requirements = kwargs.get("additional_requirements", [])

    @property
    def venv_path(self) -> Optional[str]:
        """
        Get the path to the virtual environment.

        Returns:
            Optional[str]: The path to the venv, or None if not set.
        """
        if self.working_dir is None or self.venv is None:
            return None
        return os.path.join(self.working_dir, self.venv)

    @property
    def is_venv_created(self) -> bool:
        """
        Check if the virtual environment exists.

        Returns:
            bool: True if the venv exists, False otherwise.
        """
        return os.path.exists(self.venv_path)

    def add_requirements(self, requirements: List[str]):
        """
        Add additional requirements to be installed.

        Args:
            requirements (List[str]): List of requirement strings.

        Returns:
            SourceCode: The current instance.
        """
        self.additional_requirements.extend(requirements)
        return self

    def find_requirements_path(self) -> Optional[str]:
        """
        Find the path to the requirements.txt file.

        Returns:
            Optional[str]: The path to requirements.txt if found, else None.
        """
        local_root = os.path.join(self.src_path, "..")
        return utils.find_filepath("requirements.txt", root=local_root)

    def setup_at(self, dst_path: str = None, overwrite=True, **kwargs):
        """
        Set up the source code at the specified destination, including venv and requirements.

        Args:
            dst_path (str, optional): The destination path. Defaults to None.
            overwrite (bool, optional): Whether to overwrite existing files. Defaults to True.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The destination path.
        """
        dst_path = super().setup_at(dst_path, overwrite=overwrite)
        venv_stdout = self.maybe_create_venv()
        reqs_stdout = self.install_requirements()
        if kwargs.get("debug", False):
            self.logging_func(f"venv_stdout: {venv_stdout}")
            self.logging_func(f"reqs_stdout: {reqs_stdout}")
        return dst_path

    def maybe_create_venv(self):
        """
        Create or recreate the virtual environment if needed.

        Returns:
            str: The output from the venv creation command.
        """
        stdout = ""
        if os.path.exists(self.venv_path):
            self.logging_func(f"Recreating venv {self.venv} ...")
            shutil.rmtree(self.venv_path)
        if not os.path.exists(self.venv_path):
            self.logging_func(f"Creating venv at {self.venv_path} ...")
            stdout = self.send_cmd_to_process(
                f"python -m venv {self.venv}", cwd=self.working_dir
            )
            self.logging_func(f"Creating venv -> Done. stdout: {stdout}")
        return stdout

    def get_venv_scripts_folder(self) -> str:
        """
        Get the path to the scripts/bin folder of the virtual environment, depending on the OS.

        Returns:
            str: The path to the scripts/bin folder.
        """
        return self.VENV_SCRIPTS_FOLDER_BY_OS[sys.platform].format(self.venv_path)

    def get_venv_python_path(self) -> str:
        """
        Get the path to the Python executable in the virtual environment.

        Returns:
            str: The path to the venv's Python executable.
        """
        return self.get_venv_module_path("python")

    def get_venv_module_path(self, module_name: str) -> str:
        """
        Get the path to a module (e.g., python, pip) in the virtual environment.

        Args:
            module_name (str): The name of the module.

        Returns:
            str: The path to the module executable.
        """
        return os.path.join(self.get_venv_scripts_folder(), module_name)

    def install_requirements(self):
        """
        Install requirements from requirements.txt and any additional requirements.

        Returns:
            str: The output from the pip install command.
        """
        if self.reqs_path is None:
            self.reqs_path = self.find_requirements_path()
        if self.reqs_path is None:
            return "No requirements.txt file found."
        std_out = self.send_cmd_to_process(
            f"{self.get_venv_python_path()} -m pip install -r {self.reqs_path}",
            # cwd=self.working_dir
            cwd=os.getcwd(),
        )
        for req in self.additional_requirements:
            self.send_cmd_to_process(
                f"{self.get_venv_python_path()} -m pip install {req}", cwd=os.getcwd()
            )
        return std_out

    def send_cmd_to_process(self, cmd: str, timeout: Optional[int] = None, **kwargs):
        """
        Send a command to a subprocess, using the venv's Python/pip if available.

        Args:
            cmd (str): The command to execute.
            timeout (Optional[int], optional): Timeout for the command. Defaults to None.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The standard output from the command.
        """
        if self.is_venv_created:
            if cmd.startswith("python"):
                cmd = cmd.replace("python", self.get_venv_python_path())
            if cmd.startswith("pip"):
                cmd = cmd.replace(
                    "pip", os.path.join(self.get_venv_scripts_folder(), "pip")
                )
        return super().send_cmd_to_process(cmd, timeout=timeout, **kwargs)

    def clear_venv(self):
        """
        Remove the virtual environment directory, if it exists.
        """
        if os.path.exists(self.venv_path):
            shutil.rmtree(self.venv_path)

    def clear_temporary_files(self):
        """
        Remove temporary files, including the venv and any git repo.
        """
        super().clear_temporary_files()
        self.clear_venv()

    def extra_repr(self) -> str:
        """
        Return extra information for the string representation.

        Returns:
            str: Extra representation string.
        """
        return f", venv={self.venv_path}, reqs={self.reqs_path}"


class SourceTests(Source):
    """
    Represents a source of test files, typically in a 'tests' directory.
    """

    DEFAULT_SRC_DIRNAME = "tests"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a SourceTests object.

        Args:
            src_path (Optional[str]): Path to the tests directory.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments for configuration.
        """
        super().__init__(src_path, *args, **kwargs)

    def setup_at(self, dst_path: str = None, overwrite=True, **kwargs):
        """
        Set up the test source at the specified destination.

        Args:
            dst_path (str, optional): The destination path. Defaults to None.
            overwrite (bool, optional): Whether to overwrite existing files. Defaults to True.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The destination path.
        """
        dst_path = super().setup_at(dst_path, overwrite=overwrite)
        return dst_path

    def rename_test_files(self, pattern: str = "{}_"):
        """
        Rename test files in the local path according to the given pattern.

        Args:
            pattern (str, optional): The renaming pattern, must contain '{}'. Defaults to '{}_'.

        Raises:
            AssertionError: If the local path does not exist or pattern is invalid.
        """
        assert os.path.exists(self.local_path), (
            f"Path {self.local_path} does not exist."
        )
        assert "{}" in pattern, f"Pattern {pattern} must contain {{}}."
        for root, dirs, files in os.walk(self.local_path):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    new_file = pattern.format(file).replace(".py", "") + ".py"
                    os.rename(os.path.join(root, file), os.path.join(root, new_file))


class SourceMasterCode(SourceCode):
    """
    Represents the master source code, with a dedicated venv and working directory.
    """

    DEFAULT_VENV = "master_venv"
    DEFAULT_WORKING_DIRNAME = "master_src"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a SourceMasterCode object.

        Args:
            src_path (Optional[str]): Path to the master source code directory.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments for configuration.
        """
        kwargs.setdefault("working_dirname", self.DEFAULT_WORKING_DIRNAME)
        super().__init__(src_path, *args, **kwargs)


class SourceMasterTests(SourceTests):
    """
    Represents the master test source, with a dedicated working directory.
    """

    DEFAULT_WORKING_DIRNAME = "master_tests"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a SourceMasterTests object.

        Args:
            src_path (Optional[str]): Path to the master tests directory.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments for configuration.
        """
        kwargs.setdefault("working_dirname", self.DEFAULT_WORKING_DIRNAME)
        super().__init__(src_path, *args, **kwargs)
