import os
import pathlib

from xcengine.util import clear_directory


def test_clear_directory(tmp_path):
    subdir = tmp_path / "foo" / "bar" / "baz"
    os.makedirs(subdir)
    for name in "a", "b", "c":
        for path in pathlib.Path(tmp_path / name), subdir / name:
            path.write_text("test")
    clear_directory(tmp_path)
    assert tmp_path.exists()
    assert tmp_path.is_dir()
    assert os.listdir(tmp_path) == []
