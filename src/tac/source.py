"""
Source code management module for TPAutoCorrect.

This module provides classes for managing source code and test files,
including local and remote (git) sources, virtual environment management,
and dependency installation with uv/pip support.
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from . import utils


class Source:
    """
    Represents a source of files, either a local directory or a remote git repository.

    Handles copying, cloning, and managing source files for testing and evaluation.

    :ivar str DEFAULT_SRC_DIRNAME: Default source directory name.
    :ivar Callable DEFAULT_LOGGING_FUNC: Default logging function.
    :ivar str DEFAULT_REPO_URL: Default repository URL format.
    :ivar str DEFAULT_REPO_BRANCH: Default repository branch.
    :ivar str _src_path: Path to the source directory or None.
    :ivar tuple args: Additional positional arguments.
    :ivar dict kwargs: Additional keyword arguments for configuration.
    :ivar str _repo_url: Repository URL if remote.
    :ivar str repo_branch: Branch of the repository.
    :ivar repo: Git repository object (if cloned).
    :ivar str local_repo_tmp_dirname: Temporary directory name for cloned repo.
    :ivar str working_dir: Working directory where files are copied to.
    :ivar str working_dirname: Name of the working directory.
    :ivar Callable logging_func: Logging function.
    """

    DEFAULT_SRC_DIRNAME = "src"
    DEFAULT_LOGGING_FUNC = logging.info

    # Git configuration
    DEFAULT_REPO_URL = "https://github.com/{}.git"
    DEFAULT_REPO_BRANCH = "main"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a Source object.

        :param src_path: Path to the source directory or None to auto-detect.
        :type src_path: Optional[str]
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments including:
            - repo_url or url: URL of the git repository
            - repo_branch: Branch name (default: "main")
            - local_repo_tmp_dirname: Directory for temporary git clone
            - working_dir: Working directory for files
            - working_dirname: Name for the working directory
            - logging_func: Function for logging messages
        :raises ValueError: If source is remote but no repo_url provided.
        """
        self._src_path = src_path
        self.args = args
        self.kwargs = kwargs

        self._repo_url = kwargs.get("repo_url", kwargs.get("url", None))

        # Validate remote source
        if self.is_remote and self._repo_url is None:
            raise ValueError(
                f"Source {self.src_path} doesn't exist locally but no repo url was provided. "
                f"Please ensure the source exists locally or provide a repo url with the "
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
        Return the source path of the object.

        This is the path from where to copy the source files.
        Can be a local folder or a path within a remote repo.

        :return: The source path of the object.
        :rtype: str
        """
        if self._src_path is None:
            return self._try_find_default_src_dir()
        return self._src_path

    @property
    def local_path(self) -> Optional[str]:
        """
        Return the local path where files are copied to.

        This is the working path where source files are located after setup.
        Returns None if the source hasn't been set up yet.

        :return: The local path of the object.
        :rtype: Optional[str]
        """
        if self.working_dir is None:
            return None
        basename = self.working_dirname or os.path.basename(self.src_path)
        return os.path.join(self.working_dir, basename)

    @property
    def repo_url(self) -> Optional[str]:
        """
        Return the remote URL of the git repository if source is remote.

        :return: The remote URL or None if source is local.
        :rtype: Optional[str]
        """
        return self._repo_url

    @property
    def repo_name(self) -> Optional[str]:
        """
        Return the repository name extracted from the URL.

        :return: The repository name or None if source is local.
        :rtype: Optional[str]
        """
        if self.repo_url is None:
            return None
        return self.repo_url.split("/")[-1].split(".")[0]

    @property
    def is_local(self) -> bool:
        """
        Check if the source exists locally and is not remote.

        :return: True if the source is local, False otherwise.
        :rtype: bool
        """
        return os.path.exists(self.src_path) and (not self.is_remote)

    @property
    def is_remote(self) -> bool:
        """
        Check if the source is remote (i.e., has a repo URL).

        :return: True if the source is remote, False otherwise.
        :rtype: bool
        """
        return self.repo_url is not None

    @property
    def is_setup(self) -> bool:
        """
        Check if the local path is set up (i.e., exists).

        :return: True if the local path exists, False otherwise.
        :rtype: bool
        """
        if self.local_path is None:
            return False
        return os.path.exists(self.local_path)

    @property
    def local_repo_tmp_dirpath(self) -> str:
        """
        Get the path to the temporary directory used for cloning the git repository.

        :return: The path to the temporary git repo directory.
        :rtype: str
        :raises ValueError: If working_dir is not set.
        """
        if self.working_dir is None:
            raise ValueError(
                "working_dir must be set before accessing local_repo_tmp_dirpath"
            )
        return os.path.join(self.working_dir, self.local_repo_tmp_dirname)

    def _try_find_default_src_dir(self, root: Optional[str] = None) -> str:
        """
        Try to find the default source directory.

        :param root: The root directory to search from.
        :type root: Optional[str]
        :return: The path to the default source directory.
        :rtype: str
        :raises ValueError: If the default source directory cannot be found.
        """
        if self._src_path is not None:
            return self._src_path

        dirpath = utils.find_dir(self.DEFAULT_SRC_DIRNAME, root=root)

        if dirpath is None:
            raise ValueError(
                f"Could not find default source directory '{self.DEFAULT_SRC_DIRNAME}'. "
                f"Please provide a source directory with the 'src_path' argument."
            )

        return dirpath

    def copy_to_working_dir(self, overwrite: bool = False) -> None:
        """
        Copy the source files to the working directory.

        If the source is remote, clones the repository first.

        :param overwrite: Whether to overwrite existing files. Defaults to False.
        :type overwrite: bool
        :raises FileNotFoundError: If the source path does not exist after setup.
        """
        if self.is_setup and overwrite:
            utils.try_rmtree(self.local_path, ignore_errors=True)

        if self.is_remote:
            self._clone_repo()

        if self._src_path is None:
            self._src_path = self._try_find_default_src_dir()

        if not os.path.exists(self.src_path):
            raise FileNotFoundError(
                f"Source path '{self.src_path}' does not exist. "
                f"If using a remote repository, ensure the path exists in the repo."
            )

        shutil.copytree(self.src_path, self.local_path, dirs_exist_ok=True)

    def _clone_repo(self):
        """
        Clone the remote git repository to a temporary directory.

        :return: The cloned git repository object.
        :rtype: git.Repo
        :raises ImportError: If GitPython is not installed.
        """
        import git

        if os.path.exists(self.local_repo_tmp_dirpath):
            self.logging_func(
                f"Repo {self.repo_name} already exists at {self.local_repo_tmp_dirpath}. "
                f"Reusing existing clone."
            )
            self.repo = git.Repo(self.local_repo_tmp_dirpath)
        else:
            self.logging_func(
                f"Cloning repo {self.repo_name} from {self.repo_url} "
                f"to {self.local_repo_tmp_dirpath}..."
            )
            self.repo = git.Repo.clone_from(
                self.repo_url,
                self.local_repo_tmp_dirpath,
                branch=self.repo_branch,
            )
            self.logging_func(f"Clone complete for {self.repo_name}")

        # Update src_path to point to the cloned repo
        if self._src_path is None:
            self._src_path = self._try_find_default_src_dir(
                root=self.local_repo_tmp_dirpath
            )
        else:
            # Re-root src_path under the cloned repo, preserving any
            # subdirectory structure the caller specified.  Strip any leading
            # path components that look like the repo root (i.e. start with
            # the local_repo_tmp_dirpath prefix) so we don't double-prefix.
            src = Path(self._src_path)
            if src.is_absolute():
                # If somehow already absolute, keep it as-is.
                pass
            else:
                self._src_path = str(Path(self.local_repo_tmp_dirpath) / src)

        return self.repo

    def setup_at(self, dst_path: Optional[str] = None, overwrite: bool = True) -> str:
        """
        Set up the source at the specified destination path.

        :param dst_path: The destination path. Defaults to None.
        :type dst_path: Optional[str]
        :param overwrite: Whether to overwrite existing files. Defaults to True.
        :type overwrite: bool
        :return: The destination path where files were set up.
        :rtype: str
        """
        self.working_dir = dst_path or os.getcwd()
        self.copy_to_working_dir(overwrite=overwrite)
        return self.local_path

    def send_cmd_to_process(
        self, cmd: str, timeout: Optional[int] = None, **kwargs
    ) -> str:
        """
        Send a command to a subprocess.

        :param cmd: The command to execute.
        :type cmd: str
        :param timeout: Timeout for the command in seconds. Defaults to None.
        :type timeout: Optional[int]
        :param kwargs: Additional keyword arguments including 'cwd' for working directory.
        :return: The standard output from the command.
        :rtype: str
        :raises subprocess.TimeoutExpired: If the command times out.
        :raises subprocess.CalledProcessError: If the command fails.
        """
        cwd = kwargs.get("cwd", self.working_dir or os.getcwd())

        self.logging_func(f"Executing command: {cmd}")

        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            self.logging_func(
                f"Command failed (exit {result.returncode}): {cmd}\n"
                f"stderr: {result.stderr.strip()}"
            )
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return result.stdout

    def clear_temporary_files(self) -> None:
        """
        Remove temporary files, including any cloned git repository.
        """
        if self.is_remote and os.path.exists(self.local_repo_tmp_dirpath):
            utils.try_rmtree(self.local_repo_tmp_dirpath)

    def extra_repr(self) -> str:
        """
        Return extra information for the string representation.

        :return: Extra representation string.
        :rtype: str
        """
        return ""

    def __repr__(self) -> str:
        """
        Return a string representation of the Source instance.

        :return: String representation.
        :rtype: str
        """
        try:
            src_path = self.src_path
        except (ValueError, Exception):
            src_path = self._src_path
        return (
            f"{self.__class__.__name__}("
            f"src_path={src_path}, "
            f"repo_url={self.repo_url}, "
            f"local_path={self.local_path}"
            f"{self.extra_repr()}"
            f")"
        )

    __str__ = __repr__


class SourceCode(Source):
    """
    Represents source code with virtual environment and dependency management.

    Extends Source with capabilities for creating virtual environments
    and installing requirements using uv or pip as fallback.

    :ivar str DEFAULT_VENV: Default virtual environment directory name.
    :ivar dict VENV_SCRIPTS_FOLDER_BY_OS: Platform-specific paths to venv scripts/bin.
    :ivar str venv: Virtual environment directory name.
    :ivar str reqs_path: Path to requirements.txt file.
    :ivar list additional_requirements: Additional packages to install.
    :ivar bool use_uv: Whether to use uv for package installation.
    """

    DEFAULT_VENV = "venv"
    # Delegate to the canonical table in utils to keep a single source of truth.
    VENV_SCRIPTS_FOLDER_BY_OS = utils.VENV_SCRIPTS_FOLDER_BY_OS

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a SourceCode object.

        :param src_path: Path to the source code directory.
        :type src_path: Optional[str]
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments including:
            - venv: Virtual environment directory name
            - reqs_path: Path to requirements.txt
            - additional_requirements: List of extra packages to install
            - use_uv: Whether to use uv package manager (default: True)
        """
        super().__init__(src_path, *args, **kwargs)
        self.venv = kwargs.get("venv", self.DEFAULT_VENV)
        self.reqs_path = kwargs.get("reqs_path", None)
        self.additional_requirements: List[str] = kwargs.get(
            "additional_requirements", []
        )
        self.use_uv = kwargs.get("use_uv", True)

    @property
    def venv_path(self) -> Optional[str]:
        """
        Get the full path to the virtual environment directory.

        :return: Path to the virtual environment or None if working_dir not set.
        :rtype: Optional[str]
        """
        if self.working_dir is None:
            return None
        return os.path.join(self.working_dir, self.venv)

    @property
    def is_venv_created(self) -> bool:
        """
        Check if the virtual environment exists.

        :return: True if venv exists, False otherwise.
        :rtype: bool
        """
        return self.venv_path is not None and os.path.exists(self.venv_path)

    def _find_dep_file(self, filename: str) -> Optional[str]:
        """
        Find a dependency file (e.g. ``pyproject.toml``, ``requirements.txt``) in the
        source tree.

        Search order:
        1. The cloned repo root (if remote and already cloned)
        2. The source path directory
        3. The parent of the source path

        :param filename: Filename to search for.
        :type filename: str
        :return: Absolute path to the file, or None if not found.
        :rtype: Optional[str]
        """
        search_locations = []

        # If remote, search in cloned repo first
        if self.is_remote and os.path.exists(self.local_repo_tmp_dirpath):
            search_locations.append(self.local_repo_tmp_dirpath)

        # Search in source path and its parent
        if os.path.exists(self.src_path):
            search_locations.append(self.src_path)
            search_locations.append(os.path.dirname(self.src_path))

        for location in search_locations:
            found = utils.find_filepath(filename, root=location)
            if found:
                return found

        return None

    def find_pyproject_path(self) -> Optional[str]:
        """
        Find the ``pyproject.toml`` file in the source tree.

        Delegates to :meth:`_find_dep_file`.

        :return: Path to pyproject.toml or None if not found.
        :rtype: Optional[str]
        """
        return self._find_dep_file("pyproject.toml")

    def find_requirements_path(self) -> Optional[str]:
        """
        Find the ``requirements.txt`` file in the source tree.

        Delegates to :meth:`_find_dep_file`.

        :return: Path to requirements.txt or None if not found.
        :rtype: Optional[str]
        """
        return self._find_dep_file("requirements.txt")

    def _copy_dependency_files(self) -> None:
        """
        Copy pyproject.toml and requirements.txt to working directory if they exist.

        This ensures dependency files are available for installation.
        """
        if self.working_dir is None:
            return

        # Find and copy pyproject.toml
        pyproject_path = self.find_pyproject_path()
        if pyproject_path:
            dest = os.path.join(self.working_dir, "pyproject.toml")
            if not os.path.exists(dest):
                shutil.copy2(pyproject_path, dest)
                self.logging_func(f"Copied pyproject.toml to {dest}")

        # Find and copy requirements.txt
        reqs_path = self.find_requirements_path()
        if reqs_path:
            dest = os.path.join(self.working_dir, "requirements.txt")
            if not os.path.exists(dest):
                shutil.copy2(reqs_path, dest)
                self.logging_func(f"Copied requirements.txt to {dest}")

    def setup_at(
        self, dst_path: Optional[str] = None, overwrite: bool = True, **kwargs
    ) -> str:
        """
        Set up the source code at the specified destination, including venv and requirements.

        :param dst_path: The destination path. Defaults to None.
        :type dst_path: Optional[str]
        :param overwrite: Whether to overwrite existing files. Defaults to True.
        :type overwrite: bool
        :param kwargs: Additional keyword arguments including 'debug' for verbose output.
        :return: The destination path.
        :rtype: str
        """
        dst_path = super().setup_at(dst_path, overwrite=overwrite)

        # Copy dependency files to working directory
        self._copy_dependency_files()

        # Skip venv creation and requirements installation if the venv already
        # exists and the caller did not request an overwrite.
        if self.is_venv_created and not overwrite:
            self.logging_func(
                f"Venv already exists at {self.venv_path}, skipping creation."
            )
        else:
            venv_stdout = self.recreate_venv()
            reqs_stdout = self.install_requirements()

            if kwargs.get("debug", False):
                self.logging_func(f"venv creation output: {venv_stdout}")
                self.logging_func(f"requirements installation output: {reqs_stdout}")

        return dst_path

    def recreate_venv(self) -> str:
        """
        Destroy (if present) and recreate the virtual environment.

        :return: The output from the venv creation command.
        :rtype: str
        """
        stdout = ""

        if self.venv_path is None:
            raise ValueError("working_dir must be set before creating venv")

        if os.path.exists(self.venv_path):
            self.logging_func(f"Recreating venv at {self.venv_path}...")
            shutil.rmtree(self.venv_path)

        if not os.path.exists(self.venv_path):
            self.logging_func(f"Creating venv at {self.venv_path}...")
            stdout = self.send_cmd_to_process(
                f"{sys.executable} -m venv {self.venv}", cwd=self.working_dir
            )
            self.logging_func(f"Venv creation complete")

        return stdout

    def get_venv_scripts_folder(self) -> str:
        """
        Get the path to the scripts/bin folder of the virtual environment.

        Platform-specific (Scripts on Windows, bin on Unix).

        :return: The path to the scripts/bin folder.
        :rtype: str
        :raises ValueError: If platform is not supported or venv_path is None.
        """
        if self.venv_path is None:
            raise ValueError("venv_path is not set")

        if sys.platform not in self.VENV_SCRIPTS_FOLDER_BY_OS:
            raise ValueError(f"Unsupported platform: {sys.platform}")

        return self.VENV_SCRIPTS_FOLDER_BY_OS[sys.platform].format(self.venv_path)

    def get_venv_python_path(self) -> str:
        """
        Get the path to the Python executable in the virtual environment.

        :return: The path to the venv's Python executable.
        :rtype: str
        """
        return self.get_venv_module_path("python")

    def get_venv_module_path(self, module_name: str) -> str:
        """
        Get the path to a module (e.g., python, pip, pytest) in the virtual environment.

        :param module_name: The name of the module.
        :type module_name: str
        :return: The path to the module executable.
        :rtype: str
        """
        return os.path.join(self.get_venv_scripts_folder(), module_name)

    def install_requirements(self) -> str:
        """
        Install requirements using pyproject.toml (preferred with uv) or requirements.txt (fallback).

        Strategy:
        - With uv: Use pyproject.toml if available, else requirements.txt
        - With pip: Use requirements.txt if available, else pyproject.toml

        Also installs any additional_requirements specified.

        :return: The output from the installation command.
        :rtype: str
        """
        std_out = ""

        # Find dependency files in working directory
        pyproject_path = None
        reqs_path = None

        if self.working_dir:
            # Check for files in working directory first
            working_pyproject = os.path.join(self.working_dir, "pyproject.toml")
            working_reqs = os.path.join(self.working_dir, "requirements.txt")

            if os.path.exists(working_pyproject):
                pyproject_path = working_pyproject
            if os.path.exists(working_reqs):
                reqs_path = working_reqs

        # If not found in working dir, search source tree
        if not pyproject_path:
            pyproject_path = self.find_pyproject_path()
        if not reqs_path and self.reqs_path is None:
            reqs_path = self.find_requirements_path()
        elif self.reqs_path:
            reqs_path = self.reqs_path

        # Install dependencies based on what's available and whether we're using uv
        installed = False

        if self.use_uv and utils.check_uv_available():
            # With uv: prefer pyproject.toml
            if pyproject_path:
                self.logging_func(
                    f"Installing from pyproject.toml with uv: {pyproject_path}"
                )
                try:
                    result = utils.install_from_pyproject(
                        pyproject_path, venv_path=self.venv_path, use_uv=True
                    )
                    std_out = result.stdout
                    installed = True
                    self.logging_func("Dependencies installed from pyproject.toml")
                except Exception as e:
                    self.logging_func(f"Error installing from pyproject.toml: {e}")

            # Fallback to requirements.txt with uv
            if not installed and reqs_path:
                self.logging_func(
                    f"Installing from requirements.txt with uv: {reqs_path}"
                )
                try:
                    result = utils.install_requirements(
                        reqs_path, venv_path=self.venv_path, use_uv=True
                    )
                    std_out = result.stdout
                    installed = True
                    self.logging_func("Dependencies installed from requirements.txt")
                except Exception as e:
                    self.logging_func(f"Error installing from requirements.txt: {e}")

        # With pip or as final fallback: prefer requirements.txt
        if not installed:
            if reqs_path:
                self.logging_func(
                    f"Installing from requirements.txt with pip: {reqs_path}"
                )
                try:
                    result = utils.install_requirements(
                        reqs_path,
                        venv_path=self.venv_path,
                        use_uv=False,  # Force pip
                    )
                    std_out = result.stdout
                    installed = True
                    self.logging_func("Dependencies installed from requirements.txt")
                except Exception as e:
                    self.logging_func(f"Error installing from requirements.txt: {e}")
            elif pyproject_path:
                self.logging_func(
                    f"Installing from pyproject.toml with pip: {pyproject_path}"
                )
                try:
                    result = utils.install_from_pyproject(
                        pyproject_path,
                        venv_path=self.venv_path,
                        use_uv=False,  # Force pip
                    )
                    std_out = result.stdout
                    installed = True
                    self.logging_func("Dependencies installed from pyproject.toml")
                except Exception as e:
                    self.logging_func(f"Error installing from pyproject.toml: {e}")

        if not installed:
            self.logging_func(
                "No dependency files found (pyproject.toml or requirements.txt)"
            )
            std_out = "No dependency files found."

        # Install additional requirements
        for req in self.additional_requirements:
            self.logging_func(f"Installing additional requirement: {req}")
            try:
                result = utils.install_package(
                    req, venv_path=self.venv_path, use_uv=self.use_uv
                )
                self.logging_func(f"Installed {req}")
            except Exception as e:
                self.logging_func(f"Error installing {req}: {e}")

        return std_out

    def send_cmd_to_process(
        self, cmd: str, timeout: Optional[int] = None, **kwargs
    ) -> str:
        """
        Send a command to a subprocess, using the venv's Python/pip if available.

        :param cmd: The command to execute.
        :type cmd: str
        :param timeout: Timeout for the command. Defaults to None.
        :type timeout: Optional[int]
        :param kwargs: Additional keyword arguments.
        :return: The standard output from the command.
        :rtype: str
        """
        if self.is_venv_created:
            if cmd.startswith("python"):
                cmd = cmd.replace("python", self.get_venv_python_path(), 1)
            if cmd.startswith("pip"):
                cmd = cmd.replace("pip", self.get_venv_module_path("pip"), 1)

        return super().send_cmd_to_process(cmd, timeout=timeout, **kwargs)

    def clear_venv(self) -> None:
        """
        Remove the virtual environment directory, if it exists.
        """
        if self.venv_path and os.path.exists(self.venv_path):
            shutil.rmtree(self.venv_path)

    def clear_temporary_files(self) -> None:
        """
        Remove temporary files, including the venv and any git repo.
        """
        super().clear_temporary_files()
        self.clear_venv()

    def extra_repr(self) -> str:
        """
        Return extra information for the string representation.

        :return: Extra representation string.
        :rtype: str
        """
        return f", venv={self.venv_path}, reqs={self.reqs_path}"


class SourceTests(Source):
    """
    Represents a source of test files, typically in a 'tests' directory.

    :ivar str DEFAULT_SRC_DIRNAME: Default source directory name for tests.
    """

    DEFAULT_SRC_DIRNAME = "tests"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a SourceTests object.

        :param src_path: Path to the tests directory.
        :type src_path: Optional[str]
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments for configuration.
        """
        super().__init__(src_path, *args, **kwargs)

    def setup_at(
        self, dst_path: Optional[str] = None, overwrite: bool = True, **kwargs
    ) -> str:
        """
        Set up the test source at the specified destination.

        :param dst_path: The destination path. Defaults to None.
        :type dst_path: Optional[str]
        :param overwrite: Whether to overwrite existing files. Defaults to True.
        :type overwrite: bool
        :param kwargs: Additional keyword arguments.
        :return: The destination path.
        :rtype: str
        """
        return super().setup_at(dst_path, overwrite=overwrite)

    def rename_test_files(self, pattern: str = "{}_") -> None:
        """
        Rename test files in the local path according to the given pattern.

        Useful for disambiguating test files from different sources.

        :param pattern: The renaming pattern, must contain '{}'. Defaults to '{}_'.
        :type pattern: str
        :raises AssertionError: If the local path does not exist or pattern is invalid.
        """
        if not os.path.exists(self.local_path):
            raise ValueError(f"Path {self.local_path} does not exist.")

        if "{}" not in pattern:
            raise ValueError(f"Pattern {pattern} must contain {{}}.")

        for root, dirs, files in os.walk(self.local_path):
            for file in files:
                if file.startswith("test_") and file.endswith(".py"):
                    new_file = pattern.format(file).replace(".py", "") + ".py"
                    old_path = os.path.join(root, file)
                    new_path = os.path.join(root, new_file)
                    os.rename(old_path, new_path)


class SourceSuppTests(SourceTests):
    """
    Student supplementary tests (``supp_tests/`` inside the student repo).

    These are run against the student's own ``src/`` with coverage enabled.
    """

    DEFAULT_SRC_DIRNAME = "supp_tests"
    DEFAULT_WORKING_DIRNAME = "supp_tests"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        kwargs.setdefault("working_dirname", self.DEFAULT_WORKING_DIRNAME)
        super().__init__(src_path, *args, **kwargs)


class SourceBaseTests(SourceTests):
    """
    Master base tests (``base_tests/`` inside the master repo).

    These are run against the student's ``src/`` without coverage.
    """

    DEFAULT_SRC_DIRNAME = "base_tests"
    DEFAULT_WORKING_DIRNAME = "master_tests/base_tests"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        kwargs.setdefault("working_dirname", self.DEFAULT_WORKING_DIRNAME)
        super().__init__(src_path, *args, **kwargs)


class SourceHiddenTests(SourceTests):
    """
    Master hidden tests (``hidden_tests/`` inside the master repo).

    These are run against the student's ``src/`` without coverage.
    """

    DEFAULT_SRC_DIRNAME = "hidden_tests"
    DEFAULT_WORKING_DIRNAME = "master_tests/hidden_tests"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        kwargs.setdefault("working_dirname", self.DEFAULT_WORKING_DIRNAME)
        super().__init__(src_path, *args, **kwargs)


class SourceMasterCode(SourceCode):
    """
    Represents the master/reference source code.

    Uses a dedicated venv and working directory to avoid conflicts
    with student code.

    :ivar str DEFAULT_VENV: Default virtual environment directory name for master code.
    :ivar str DEFAULT_WORKING_DIRNAME: Default working directory name for master code.
    """

    DEFAULT_VENV = "master_venv"
    DEFAULT_WORKING_DIRNAME = "master_src"

    def __init__(self, src_path: Optional[str] = None, *args, **kwargs):
        """
        Initialize a SourceMasterCode object.

        :param src_path: Path to the master source code directory.
        :type src_path: Optional[str]
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments for configuration.
        """
        kwargs.setdefault("working_dirname", self.DEFAULT_WORKING_DIRNAME)
        super().__init__(src_path, *args, **kwargs)
