import pathlib
import shutil
from unittest.mock import patch
import importlib.util
import sys
import pytest


@pytest.fixture
def code_dir(tmp_path, monkeypatch):
    # Copy required code to a temporary directory, to which we can also
    # add a user_code.py file.
    # TODO: factor out and reuse the copying code in core.py.
    import xcengine
    src = pathlib.Path(xcengine.__path__[0])
    for filename in "wrapper.py", "util.py", "parameters.py":
        shutil.copy2(src / filename, tmp_path / filename)
    monkeypatch.chdir(tmp_path)
    return pathlib.Path(tmp_path)


@patch("sys.argv", ["wrapper.py", "--verbose"])
def test_wrapper(code_dir: pathlib.Path):
    sys.path.append(str(code_dir))
    (code_dir / "user_code.py").touch()
    spec = importlib.util.spec_from_file_location(
        "wrapper", str(code_dir / "wrapper.py")
    )
    wrapper = importlib.util.module_from_spec(spec)
    sys.modules["wrapper"] = wrapper
    spec.loader.exec_module(wrapper)
    wrapper.main()
