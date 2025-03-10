import os
from unittest.mock import patch
import sys


@patch("sys.argv", ["wrapper.py", "--verbose"])
def test_wrapper(tmp_path, monkeypatch):
    import xcengine
    for path in xcengine.__path__:
        monkeypatch.syspath_prepend(path)
    user_code_path = (tmp_path / "user_code.py")
    user_code_path.touch()
    os.environ["XC_USER_CODE_PATH"] = str(user_code_path)
    from xcengine import wrapper
    xcengine.wrapper.main()
