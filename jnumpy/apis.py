from __future__ import annotations
from jnumpy.envars import TyPython_directory, SessionCtx
from jnumpy.utils import escape_to_julia_rawstr, invoke_interpreted_julia
from jnumpy.init import JuliaError, exec_julia
import contextlib
import subprocess
import pathlib


def include_src(src_file: str, current_file_path: str = "./__init__.py"):
    """
    include julia module in src_file
    Arguments:
      src_file:
        the path of julia file releative to file path.
      file_path(option):
        should be `__file__`, empty in repl mode.
    """
    # activate project before include module
    project_dir = pathlib.Path(current_file_path).absolute().parent
    src_abspath = project_dir.joinpath(src_file)
    from jnumpy import exec_julia

    exec_julia(r"include({})".format(escape_to_julia_rawstr(src_abspath.as_posix())))


@contextlib.contextmanager
def activate_project_nocheck(project_dir: str):
    exec_julia(
        f"InitTools.activate_project({escape_to_julia_rawstr(project_dir)},"
        f"{escape_to_julia_rawstr(TyPython_directory)}; check=false)",
        use_gil=False,
    )
    try:
        yield
    finally:
        exec_julia(
            f"InitTools.activate_project({escape_to_julia_rawstr(SessionCtx.DEFAULT_PROJECT_DIR)},"
            f"{escape_to_julia_rawstr(TyPython_directory)}; check=false)",
            use_gil=False,
        )


@contextlib.contextmanager
def activate_project_checked(project_dir: str):
    exec_julia(
        f"InitTools.activate_project({escape_to_julia_rawstr(project_dir)},"
        f"{escape_to_julia_rawstr(TyPython_directory)})",
        use_gil=False,
    )
    try:
        yield
    finally:
        exec_julia(
            f"InitTools.activate_project({escape_to_julia_rawstr(SessionCtx.DEFAULT_PROJECT_DIR)},"
            f"{escape_to_julia_rawstr(TyPython_directory)})",
            use_gil=False,
        )


def get_project_name_no_exc(project_dir: str):
    """!!!This function can return empty string!"""
    try:
        name = invoke_interpreted_julia(
            SessionCtx.JULIA_EXE,
            [
                "-e",
                rf'import TOML; TOML.parsefile(joinpath({escape_to_julia_rawstr(project_dir)}, "Project.toml"))["name"] |> println',
            ],
        )
    except subprocess.CalledProcessError:
        raise RuntimeError(
            f"{project_dir} does not have a Project.toml with a top-level"
            f"entry 'name = xxx' and the '[deps]' section."
        )
    if isinstance(name, bytes):
        jl_module_name = name.decode("utf-8").strip()
        return jl_module_name


def get_project_name_checked(project_dir: str):
    jl_module_name = get_project_name_no_exc(project_dir)
    if not jl_module_name:
        raise IOError(f"failed to get julia module name at {project_dir}.")
    return jl_module_name


def init_project(package_entry_filepath):
    project_dir = pathlib.Path(package_entry_filepath).absolute().parent.as_posix()
    try:
        with activate_project_nocheck(project_dir):
            jl_module_name = get_project_name_checked(project_dir)
            exec_julia(
                "import {0};TyPython.CPython.init();{0}.init()".format(jl_module_name)
            )
    except JuliaError:
        with activate_project_checked(project_dir):
            jl_module_name = get_project_name_checked(project_dir)
            exec_julia(
                f"InitTools.setup_environment({escape_to_julia_rawstr(TyPython_directory)})",
                use_gil=True,
            )
            exec_julia(
                f"InitTools.force_resolve({escape_to_julia_rawstr(TyPython_directory)})",
                use_gil=True,
            )
            exec_julia(
                "import {0};TyPython.CPython.init();{0}.init()".format(jl_module_name)
            )
