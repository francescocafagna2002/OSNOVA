import csv
import gzip
import io
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from scripts.preview_data import find_data_dir, main, preview


class PreviewDataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_header_and_ten_records_for_csv_and_gzip(self):
        rows = [[str(i), f"synthetic\nvalue {i}"] for i in range(20)]
        for suffix, opener in ((".csv", open), (".csv.gz", gzip.open)):
            with self.subTest(suffix=suffix):
                path = self.root / f"measurements{suffix}"
                with opener(path, "wt", encoding="utf-8-sig", newline="") as target:
                    csv.writer(target, delimiter=";").writerows([["id", "value"], *rows])
                output = io.StringIO()
                with redirect_stdout(output):
                    preview(path)
                records = list(csv.reader(io.StringIO(output.getvalue().split("\n", 2)[2]), delimiter=";"))
                self.assertEqual(records, [["id", "value"], *rows[:10]])

    def test_short_and_empty_files(self):
        for content in ("", "id,value\n1,synthetic\n"):
            with self.subTest(content=content):
                path = self.root / "short.csv"
                path.write_text(content, encoding="utf-8")
                output = io.StringIO()
                with redirect_stdout(output):
                    preview(path)
                self.assertEqual(output.getvalue().split("\n", 2)[2], content)

    def test_mount_discovery_from_repository_directory(self):
        repo = self.root / "OSNOVA"
        repo.mkdir()
        for name in ("aew-data", "aew_data", "data/aew-data", "data/aew_data"):
            with self.subTest(name=name):
                mount = self.root / name
                mount.mkdir(parents=True)
                with patch("scripts.preview_data.Path.cwd", return_value=repo):
                    self.assertEqual(find_data_dir(), mount)
                mount.rmdir()

    def test_cli_only_reads_csv_files_recursively(self):
        nested = self.root / "monthly"
        nested.mkdir()
        (nested / "month.CSV").write_text("id,value\n1,synthetic\n", encoding="utf-8")
        (self.root / "notes.txt").write_text("do not print", encoding="utf-8")
        output = io.StringIO()
        with patch("sys.argv", ["preview_data.py", str(self.root)]), redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertIn("month.CSV", output.getvalue())
        self.assertNotIn("do not print", output.getvalue())

    def test_missing_or_empty_directory_returns_failure(self):
        for path in (self.root / "missing", self.root):
            with self.subTest(path=path):
                with patch("sys.argv", ["preview_data.py", str(path)]), redirect_stderr(io.StringIO()):
                    self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()