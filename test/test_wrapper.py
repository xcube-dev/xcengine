import os
from unittest.mock import patch, Mock
import pytest


@patch("xcengine.util.save_datasets")
@pytest.mark.parametrize("cli_args", [["--verbose"], ["--batch"]])
def test_wrapper(save_datasets_mock, tmp_path, monkeypatch, cli_args):
    import xcengine

    with patch("sys.argv", ["wrapper.py"] + cli_args):
        for path in xcengine.__path__:
            monkeypatch.syspath_prepend(path)
        user_code_path = tmp_path / "user_code.py"
        user_code_path.touch()
        os.environ["XC_USER_CODE_PATH"] = str(user_code_path)
        from xcengine import wrapper

        xcengine.wrapper.main()

        assert save_datasets_mock.call_count == (
            1 if "--batch" in cli_args else 0
        )
