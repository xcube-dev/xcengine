import pathlib
from unittest.mock import patch

from click.testing import CliRunner

from xcengine.cli import cli


@patch("xcengine.core.ScriptCreator.__init__")
@patch("xcengine.core.ScriptCreator.convert_notebook_to_script")
@patch("subprocess.run")
def test_make_script(run_mock, convert_mock, init_mock, tmp_path):
    nb_path = tmp_path / "foo.ipynb"
    nb_path.touch()
    output_dir = tmp_path / "bar"
    init_mock.return_value = None
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "make-script",
            "--batch",
            "--server",
            "--from-saved",
            str(nb_path),
            str(output_dir),
        ],
    )
    convert_mock.assert_called()
    init_mock.assert_called()
    run_mock.assert_called_with(
        [
            "python3",
            output_dir / "execute.py",
            "--batch",
            "--server",
            "--from-saved",
        ]
    )
    assert result.exit_code == 0
