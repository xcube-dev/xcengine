import os
import pathlib
from unittest.mock import patch, Mock
import pytest
import xcengine


@pytest.mark.parametrize(
    "cli_args", [["--verbose"], ["--batch"], ["--server"]]
)
def test_wrapper(tmp_path, monkeypatch, cli_args):

    with patch("sys.argv", ["wrapper.py"] + cli_args):
        for path in xcengine.__path__:
            monkeypatch.syspath_prepend(path)
        user_code_path = tmp_path / "user_code.py"
        user_code_path.touch()
        os.environ["XC_USER_CODE_PATH"] = str(user_code_path)
        from xcengine import wrapper

        with (
            patch("util.save_datasets", save_datasets_mock := Mock()),
            patch("util.start_server", start_server_mock := Mock()),
        ):
            xcengine.wrapper.main()

        assert save_datasets_mock.call_count == (
            1 if "--batch" in cli_args else 0
        )

        assert start_server_mock.call_count == (
            1 if "--server" in cli_args else 0
        )


@patch("sys.argv", ["wrapper.py", "--bar", "17"])
@patch.dict(os.environ, {"xce_baz": "42"})
def test_xce_set_params(tmp_path, monkeypatch):
    for path in xcengine.__path__:
        monkeypatch.syspath_prepend(path)
    (user_code_path := tmp_path / "user_code.py").touch()
    os.environ["XC_USER_CODE_PATH"] = str(user_code_path)
    from xcengine import wrapper

    wrapper.__xce_set_params(pathlib.Path(__file__).parent / "data/dummy")
    # NB: __xce_set_params doesn't explicitly set default values from
    # the parameter configuration (like "foo" here), since the user code
    # will set these anyway.
    assert "foo" not in wrapper.__dict__
    assert wrapper.__dict__["bar"] == 17
    assert wrapper.__dict__["baz"] == 42
