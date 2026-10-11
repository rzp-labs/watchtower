# Modified by rzp-labs, 2026-10-11. GNU AGPL version 3; see LICENSE.
import importlib.util
import io
from pathlib import Path
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("package_plugin", Path(__file__).parents[1] / "scripts/package_plugin.py")
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)

class PackageSafetyTests(unittest.TestCase):
    def entries(self):
        return [("100644", name) for name in pack.ROOT_FILES]

    def test_private_tracked_files_and_development_files_are_not_packaged(self):
        names = pack.package_names(self.entries() + [("100644", name) for name in ["librarymanager.sqlite3", "config.yml", "manifest", "activity-report.json", "tests/test_ui.mjs", ".github/workflows/package.yml"]])
        self.assertEqual({name for _, name in names}, pack.ROOT_FILES)

    def test_runtime_file_within_selected_tree_is_rejected(self):
        for name in ["assets/private.sqlite3", "watchdog/runtime.json", "assets/.secret", "watchdog/file.pyc"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                pack.package_names(self.entries() + [("100644", name)])

    def test_symlink_and_path_traversal_are_rejected(self):
        for entry in [("120000", "assets/escape"), ("100644", "../config.yml"), ("100644", "/config.yml")]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                pack.package_names(self.entries() + [entry])

    def test_package_requires_license_and_all_runtime_code(self):
        for omitted in ["LICENSE", "NOTICE.md", "librarymanager.js", "librarymanager.yml", "librarymanager_core.py", "librarymanager_dependencies.py"]:
            with self.subTest(omitted=omitted), self.assertRaises(ValueError):
                pack.package_names([entry for entry in self.entries() if entry[1] != omitted])

    def test_zip_is_reproducible_preserves_paths_and_mode(self):
        files = [("100755", "librarymanager.py", b"fixture"), ("100644", "LICENSE", b"license")]
        timestamp = (2026, 10, 11, 0, 0, 0)
        first = pack.zip_bytes(files, timestamp)
        self.assertEqual(first, pack.zip_bytes(list(reversed(files)), timestamp))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertEqual(archive.namelist(), ["LICENSE", "librarymanager.py"])
            self.assertEqual(archive.read("librarymanager.py"), b"fixture")
            self.assertEqual(archive.getinfo("librarymanager.py").external_attr >> 16, 0o100755)

if __name__ == "__main__": unittest.main()
