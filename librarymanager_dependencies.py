"""Watchtower-local discovery of persisted PythonTools dependencies.

Modified by rzp-labs, 2026-10-11. GNU AGPL version 3; see LICENSE.
No installation, global interpreter selection or environment mutation occurs here.
"""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import site
import subprocess
import sys


class DependencyEnvironmentError(RuntimeError):
    """An installed persistent dependency environment cannot be used safely."""


def _failure(reason):
    version = ".".join(map(str, sys.version_info[:2]))
    return DependencyEnvironmentError(
        "Watchtower cannot load stashapp-tools: " + reason + ". "
        "Install or repair PythonToolsInstaller's persistent venv for Python "
        + version + ", then retry Watchtower. The system interpreter is unchanged."
    )


def _candidate_environments(plugin_dir):
    # Standard standalone and community layouts only, never an unbounded search.
    roots = (plugin_dir.parent, plugin_dir.parent.parent)
    candidates = {root / suffix / "venv" for root in roots
                  for suffix in (Path("PythonToolsInstaller"),
                                 Path("community/PythonToolsInstaller"))}
    found = []
    for path in candidates:
        if not path.exists() and not path.is_symlink():
            continue
        if path.resolve() != path:
            raise _failure("the persisted environment redirects outside the expected plugin layout")
        found.append(path)
    return sorted(set(found))


def _validated_site_directory(environment):
    interpreter = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not (environment / "pyvenv.cfg").is_file() or not interpreter.is_file():
        raise _failure("the PythonToolsInstaller environment is incomplete")
    probe = (
        "import json,sys,sysconfig; print(json.dumps({"
        "'version':list(sys.version_info[:2]),'prefix':sys.prefix,"
        "'purelib':sysconfig.get_path('purelib')}))"
    )
    try:
        result = subprocess.run([str(interpreter), "-B", "-I", "-c", probe],
                                capture_output=True, text=True, timeout=10, check=True)
        data = json.loads(result.stdout)
        version = data["version"]
        prefix = Path(data["prefix"]).resolve()
        purelib = Path(data["purelib"]).resolve(strict=True)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
        raise _failure("the PythonToolsInstaller interpreter could not be validated") from exc
    if version != list(sys.version_info[:2]):
        raise _failure("the persisted environment uses an incompatible Python version")
    if prefix != environment or not purelib.is_relative_to(environment) or not purelib.is_dir():
        raise _failure("the persisted package directory is outside its validated environment")
    if not (purelib / "stashapi" / "stashapp.py").is_file():
        raise _failure("the persisted environment does not contain stashapp-tools")
    return purelib


def ensure_stashapi(plugin_dir=None):
    """Expose persisted dependencies only if stashapi is absent from this process.

    An existing but broken installation is left to raise its original import error.
    Never hide a transitive import failure by trying a different installation.
    Child Python entrypoints call this themselves; sys.path is not inherited.
    """
    if "stashapi" in sys.modules or importlib.util.find_spec("stashapi") is not None:
        return None
    plugin_dir = Path(plugin_dir or __file__).resolve()
    if plugin_dir.is_file():
        plugin_dir = plugin_dir.parent
    environments = _candidate_environments(plugin_dir)
    if not environments:
        raise _failure("no persistent PythonToolsInstaller environment was found")
    if len(environments) != 1:
        raise _failure("multiple persistent PythonToolsInstaller environments were found")
    purelib = _validated_site_directory(environments[0])
    # Append through the normal site mechanism: system dependencies remain visible
    # and existing plugin-local modules (including bundled watchdog) keep priority.
    site.addsitedir(str(purelib))
    importlib.invalidate_caches()
    try:
        importlib.import_module("stashapi.stashapp")
    except ImportError as exc:
        raise _failure("the persisted stashapp-tools installation has an import failure") from exc
    return purelib
