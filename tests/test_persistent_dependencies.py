"""Offline dependency bootstrap regressions; no Stash API or plugin jobs."""
# Modified by rzp-labs, 2026-10-11. GNU AGPL version 3; see LICENSE.
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import venv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import librarymanager_dependencies as dependencies


class PersistentDependenciesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "plugins"
        self.plugin = self.root / "librarymanager"
        self.plugin.mkdir(parents=True)
        self.environment = self.root / "community/PythonToolsInstaller/venv"

    def make_environment(self):
        venv.EnvBuilder(with_pip=False).create(self.environment)
        interpreter = self.environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        raw = subprocess.check_output([str(interpreter), "-B", "-I", "-c",
                                       "import sysconfig; print(sysconfig.get_path('purelib'))"], text=True)
        purelib = Path(raw.strip()).resolve()
        package = purelib / "stashapi"
        package.mkdir()
        # Match stashapp-tools' namespace package (no __init__.py).
        (package / "stashapp.py").write_text("import requests\nclass StashInterface: pass\n")
        (purelib / "requests.py").write_text("SOURCE = 'persistent'\n")
        (purelib / "watchdog.py").write_text("raise AssertionError('must retain bundled watchdog')\n")
        return purelib

    def run_isolated(self, script):
        result = subprocess.run([sys.executable, "-B", "-I", "-S", "-c", script],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def bootstrap_script(self, body):
        return ("import sys, importlib.util\nfrom pathlib import Path\n"
                + "sys.path.insert(0, " + repr(str(ROOT)) + ")\n"
                + "from librarymanager_dependencies import ensure_stashapi\n"
                + body)

    def test_real_persisted_namespace_import_preserves_system_and_bundled_modules(self):
        purelib = self.make_environment()
        system = Path(self.temp.name) / "system"
        system.mkdir()
        (system / "gradio_client.py").write_text("SOURCE = 'system'\n")
        script = self.bootstrap_script(
            "sys.path.append(" + repr(str(system)) + ")\n"
            + "before = list(sys.path)\n"
            + "assert importlib.util.find_spec('stashapi') is None\n"
            + "added = ensure_stashapi(" + repr(str(self.plugin)) + ")\n"
            + "from stashapi.stashapp import StashInterface\nimport requests,gradio_client,watchdog\n"
            + "assert added == Path(" + repr(str(purelib)) + ")\n"
            + "assert requests.SOURCE == 'persistent' and gradio_client.SOURCE == 'system'\n"
            + "assert Path(watchdog.__file__).resolve().is_relative_to(Path(" + repr(str(ROOT)) + "))\n"
            + "assert all(path in sys.path for path in before)\n"
            + "assert ensure_stashapi(" + repr(str(self.plugin)) + ") is None\n")
        self.run_isolated(script)
        # A second interpreter without the bootstrap remains unaffected.
        self.run_isolated("import importlib.util; assert importlib.util.find_spec('stashapi') is None")

    def test_three_entrypoints_import_in_separate_processes_after_replacement(self):
        self.make_environment()
        files = ["librarymanager_dependencies.py", "librarymanager.py", "librarymanager_core.py",
                 "librarymanager_reconciliation.py", "librarymanager_monitor.py", "librarymanager_startup.py"]
        for name in files:
            shutil.copy2(ROOT / name, self.plugin / name)
        shutil.copytree(ROOT / "watchdog", self.plugin / "watchdog")
        for generation in range(2):
            for name in ["librarymanager", "librarymanager_monitor", "librarymanager_startup"]:
                with self.subTest(generation=generation, entrypoint=name):
                    self.run_isolated("import sys; sys.path.insert(0, " + repr(str(self.plugin)) + ")\n"
                                      + "import " + name + "\nfrom stashapi.stashapp import StashInterface\n")
        # Each invocation has fresh ephemeral sys.path while the dependency tree persists.

    def test_existing_system_installation_does_not_probe_persistent_environment(self):
        with patch.object(dependencies.importlib.util, "find_spec", return_value=object()), \
             patch.object(dependencies, "_candidate_environments") as discovery:
            self.assertIsNone(dependencies.ensure_stashapi(self.plugin))
            discovery.assert_not_called()

    def test_existing_broken_import_is_not_hidden_by_persistent_fallback(self):
        self.make_environment()
        system = Path(self.temp.name) / "broken-system"
        (system / "stashapi").mkdir(parents=True)
        (system / "stashapi/__init__.py").write_text("")
        (system / "stashapi/stashapp.py").write_text("import missing_transitive_dependency\n")
        script = self.bootstrap_script(
            "sys.path.insert(0, " + repr(str(system)) + ")\n"
            + "assert ensure_stashapi(" + repr(str(self.plugin)) + ") is None\n"
            + "try:\n from stashapi.stashapp import StashInterface\n"
            + "except ModuleNotFoundError as e:\n assert e.name == 'missing_transitive_dependency'\n"
            + "else:\n raise AssertionError('broken system import was masked')\n")
        self.run_isolated(script)

    def test_missing_and_incomplete_environments_are_actionable(self):
        with patch.object(dependencies.importlib.util, "find_spec", return_value=None):
            with self.assertRaisesRegex(dependencies.DependencyEnvironmentError, "no persistent.*Install or repair"):
                dependencies.ensure_stashapi(self.plugin)
            self.environment.mkdir(parents=True)
            with self.assertRaisesRegex(dependencies.DependencyEnvironmentError, "incomplete"):
                dependencies.ensure_stashapi(self.plugin)

    def test_ambiguous_layout_is_rejected(self):
        self.environment.mkdir(parents=True)
        (self.root / "PythonToolsInstaller/venv").mkdir(parents=True)
        with patch.object(dependencies.importlib.util, "find_spec", return_value=None):
            with self.assertRaisesRegex(dependencies.DependencyEnvironmentError, "multiple persistent"):
                dependencies.ensure_stashapi(self.plugin)

    def test_standard_community_consumer_layout_is_discovered(self):
        self.environment.mkdir(parents=True)
        consumer = self.root / "community/watchtower"
        consumer.mkdir()
        self.assertEqual(dependencies._candidate_environments(consumer), [self.environment])

    def test_redirected_environment_is_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        self.environment.parent.mkdir(parents=True)
        self.environment.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(dependencies.DependencyEnvironmentError, "redirects outside"):
            dependencies._candidate_environments(self.plugin)

    def test_broken_interpreter_and_invalid_probe_are_actionable(self):
        self.make_environment()
        for failure in [OSError("broken executable"), subprocess.TimeoutExpired("probe",10),
                        subprocess.CalledProcessError(1,"probe")]:
            with self.subTest(failure=type(failure).__name__), patch.object(dependencies.subprocess,"run",side_effect=failure):
                with self.assertRaisesRegex(dependencies.DependencyEnvironmentError,"could not be validated"):
                    dependencies._validated_site_directory(self.environment)
        with patch.object(dependencies.subprocess,"run",return_value=subprocess.CompletedProcess([],0,"not JSON")):
            with self.assertRaisesRegex(dependencies.DependencyEnvironmentError,"could not be validated"):
                dependencies._validated_site_directory(self.environment)

    def test_incompatible_version_and_escaping_purelib_are_rejected(self):
        purelib = self.make_environment()
        data={"version":list(sys.version_info[:2]),"prefix":str(self.environment),"purelib":str(purelib)}
        for key,value,message in [("version",[sys.version_info.major,sys.version_info.minor+1],"incompatible"),
                                  ("purelib",str(self.root),"outside"),("prefix",str(self.root),"outside")]:
            with self.subTest(key=key):
                changed=dict(data,**{key:value})
                with patch.object(dependencies.subprocess,"run",return_value=subprocess.CompletedProcess([],0,json.dumps(changed))):
                    with self.assertRaisesRegex(dependencies.DependencyEnvironmentError,message):
                        dependencies._validated_site_directory(self.environment)

    def test_matching_future_minor_uses_dynamic_sysconfig_path(self):
        purelib=self.make_environment()
        future=purelib.parent.parent / "python3.99/site-packages"
        (future / "stashapi").mkdir(parents=True)
        (future / "stashapi/stashapp.py").write_text("class StashInterface: pass\n")
        data={"version":[3,99],"prefix":str(self.environment),"purelib":str(future)}
        with patch.object(dependencies.sys,"version_info",(3,99,0)), \
             patch.object(dependencies.subprocess,"run",return_value=subprocess.CompletedProcess([],0,json.dumps(data))):
            self.assertEqual(dependencies._validated_site_directory(self.environment),future)

    def test_missing_or_broken_persisted_package_reports_original_cause(self):
        purelib=self.make_environment()
        (purelib / "stashapi/stashapp.py").unlink()
        with self.assertRaisesRegex(dependencies.DependencyEnvironmentError,"does not contain"):
            dependencies._validated_site_directory(self.environment)
        (purelib / "stashapi/stashapp.py").write_text("import missing_persisted_dependency\n")
        self.run_isolated(self.bootstrap_script(
            "try:\n ensure_stashapi(" + repr(str(self.plugin)) + ")\n"
            + "except RuntimeError as e:\n assert 'persisted stashapp-tools installation has an import failure' in str(e)\n"
            + " assert e.__cause__.name == 'missing_persisted_dependency'\n"
            + "else:\n raise AssertionError('broken persisted dependency was hidden')\n"))


if __name__ == "__main__":
    unittest.main()
