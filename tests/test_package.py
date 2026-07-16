from pathlib import Path, PurePosixPath
import stat
import tomllib
import unittest
from zipfile import ZipFile

from surface_layer_studio.constants import ADDON_ID, ADDON_VERSION


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "surface_layer_studio"
PACKAGE = ROOT / "dist" / "surface_layer_studio-1.0.0.zip"


class ExtensionPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PACKAGE.is_file():
            raise unittest.SkipTest("Build the extension package before package inspection")
        cls.archive = ZipFile(PACKAGE)
        cls.names = cls.archive.namelist()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "archive"):
            cls.archive.close()

    def test_archive_integrity_and_safe_paths(self):
        self.assertIsNone(self.archive.testzip())
        self.assertEqual(len(self.names), len({name.casefold() for name in self.names}))
        for info in self.archive.infolist():
            path = PurePosixPath(info.filename)
            self.assertFalse(path.is_absolute(), info.filename)
            self.assertNotIn("..", path.parts, info.filename)
            self.assertNotIn("\\", info.filename)
            mode = info.external_attr >> 16
            self.assertFalse(stat.S_ISLNK(mode), info.filename)

    def test_manifest_and_runtime_are_at_archive_root(self):
        self.assertIn("blender_manifest.toml", self.names)
        self.assertIn("__init__.py", self.names)
        manifest = tomllib.loads(self.archive.read("blender_manifest.toml").decode("utf-8"))
        self.assertEqual(manifest["id"], ADDON_ID)
        self.assertEqual(manifest["version"], ".".join(map(str, ADDON_VERSION)))
        self.assertEqual(manifest["type"], "add-on")
        self.assertEqual(manifest["blender_version_min"], "4.5.0")

    def test_no_build_or_workspace_debris(self):
        forbidden_parts = {"__pycache__", ".git", ".tools", "tests", "artifacts", "dist"}
        forbidden_suffixes = {".pyc", ".pyo", ".blend", ".blend1", ".log"}
        for name in self.names:
            path = PurePosixPath(name)
            self.assertFalse(forbidden_parts.intersection(path.parts), name)
            self.assertNotIn(path.suffix.casefold(), forbidden_suffixes, name)

    def test_package_matches_current_source(self):
        expected = []
        for path in SOURCE.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            relative = path.relative_to(SOURCE).as_posix()
            expected.append(relative)
            self.assertIn(relative, self.names)
            self.assertEqual(self.archive.read(relative), path.read_bytes(), relative)
        self.assertEqual(set(self.names), set(expected))


if __name__ == "__main__":
    unittest.main()
