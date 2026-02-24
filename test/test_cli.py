import pathlib
import re
import urllib
from unittest.mock import patch, ANY, MagicMock
import pytest
import yaml
from click.testing import CliRunner

from xcengine.cli import cli


@patch("xcengine.core.ScriptCreator.__init__")
@patch("xcengine.core.ScriptCreator.convert_notebook_to_script")
@patch("subprocess.run")
@pytest.mark.parametrize("verbose_arg", [[], ["--verbose"]])
@pytest.mark.parametrize("batch_arg", [[], ["--batch"]])
@pytest.mark.parametrize("server_arg", [[], ["--server"]])
@pytest.mark.parametrize("from_saved_arg", [[], ["--from-saved"]])
def test_make_script(
    run_mock,
    convert_mock,
    init_mock,
    tmp_path,
    verbose_arg,
    batch_arg,
    server_arg,
    from_saved_arg,
):
    from xcengine.cli import logging

    logging.getLogger().setLevel(logging.WARN)
    nb_path = tmp_path / "foo.ipynb"
    nb_path.touch()
    output_dir = tmp_path / "bar"
    init_mock.return_value = None
    runner = CliRunner()
    result = runner.invoke(
        cli,
        verbose_arg
        + ["make-script"]
        + batch_arg
        + server_arg
        + from_saved_arg
        + [
            str(nb_path),
            str(output_dir),
        ],
    )
    convert_mock.assert_called_once_with(
        output_dir=output_dir, clear_output=False
    )
    init_mock.assert_called_once_with(nb_path)
    if batch_arg or server_arg:
        run_mock.assert_called_once_with(
            ["python3", output_dir / "execute.py"]
            + batch_arg
            + server_arg
            + from_saved_arg
        )
    assert logging.getLogger().getEffectiveLevel() == (
        logging.DEBUG if "--verbose" in verbose_arg else logging.WARNING
    )
    assert result.exit_code == 0


@pytest.mark.parametrize("specify_dir", [False, True])
@pytest.mark.parametrize("specify_env", [False, True])
@pytest.mark.parametrize("specify_eoap", [False, True])
@patch("xcengine.cli.ImageBuilder")
def test_image_build(
    builder_mock, tmp_path, specify_dir, specify_env, specify_eoap
):
    (nb_path := tmp_path / "foo.ipynb").touch()
    (env_path := tmp_path / "environment.yml").touch()
    (build_dir := tmp_path / "build").mkdir()
    eoap_path = tmp_path / "eoap.yaml"
    runner = CliRunner()
    tag = "foo"
    instance_mock = builder_mock.return_value = MagicMock()
    cwl = {"foo": 42}
    instance_mock.create_cwl.return_value = cwl
    result = runner.invoke(
        cli,
        ["image", "build", "--tag", tag]
        + (["--build-dir", str(build_dir)] if specify_dir else [])
        + (["--environment", str(env_path)] if specify_env else [])
        + (["--eoap", str(eoap_path)] if specify_eoap else [])
        + [str(nb_path)],
    )
    assert result.output.startswith("Built image")
    assert result.exit_code == 0
    builder_mock.assert_called_once_with(
        notebook=nb_path,
        environment=(env_path if specify_env else None),
        tag=tag,
        build_dir=(build_dir if specify_dir else ANY),
    )
    instance_mock.build.assert_called_once_with(skip_build=False)
    if specify_eoap:
        assert yaml.safe_load(eoap_path.read_text()) == cwl


@patch("xcengine.cli.ContainerRunner")
def test_image_run(runner_mock):
    cli_runner = CliRunner()
    instance_mock = runner_mock.return_value = MagicMock()
    result = cli_runner.invoke(cli, ["image", "run", "foo"])
    runner_mock.assert_called_once_with(image="foo", output_dir=None)
    assert result.exit_code == 0
    instance_mock.run.assert_called_once_with(
        run_batch=False,
        host_port=None,
        from_saved=False,
        keep=False,
        script_args=[],
    )


@patch("xcengine.cli.ContainerRunner")
def test_image_run_print_urls(runner_mock):
    cli_runner = CliRunner()
    instance_mock = runner_mock.return_value = MagicMock()
    port = 32168
    result = cli_runner.invoke(
        cli, ["image", "run", "--server", "--port", str(port), "foo"]
    )
    runner_mock.assert_called_once_with(image="foo", output_dir=None)
    assert result.exit_code == 0
    instance_mock.run.assert_called_once_with(
        run_batch=False,
        host_port=port,
        from_saved=False,
        keep=False,
        script_args=[],
    )
    assert re.search(
        f"server.*http://localhost:{port}", result.stdout, re.IGNORECASE
    )
    assert re.search(
        f"viewer.*http://localhost:{port}/viewer", result.stdout, re.IGNORECASE
    )


@patch("xcengine.cli.ContainerRunner")
def test_image_run_script_args(runner_mock):
    cli_runner = CliRunner()
    instance_mock = runner_mock.return_value = MagicMock()
    port = 32168
    result = cli_runner.invoke(
        cli, ["image", "run", "--server", "--port", str(port), "foo", "--bar"]
    )
    runner_mock.assert_called_once_with(image="foo", output_dir=None)
    assert result.exit_code == 0
    instance_mock.run.assert_called_once_with(
        run_batch=False,
        host_port=port,
        from_saved=False,
        keep=False,
        script_args=["--bar"],
    )


@patch("xcengine.cli.ContainerRunner")
@patch("webbrowser.open")
@patch("urllib.request.urlopen")
def test_image_run_open_browser(urlopen_mock, open_mock, runner_mock):
    cli_runner = CliRunner()
    port = 8080

    count = 0
    passed_url = None

    def urlopen(url):
        nonlocal count, passed_url
        passed_url = url
        if count == 0:
            count += 1
            raise urllib.error.URLError("mock")
        else:
            count += 1
            return None

    urlopen_mock.side_effect = urlopen

    cli_runner.invoke(
        cli, ["image", "run", "--port", str(port), "--open-browser", "foo"]
    )
    import time

    time.sleep(3)
    assert count == 2
    assert passed_url == f"http://localhost:{port}"
    open_mock.assert_called_once_with(f"http://localhost:{port}/viewer")


@patch("docker.from_env")
def test_image_skip_build_save_dockerfile_and_env(from_env_mock, tmp_path):
    build_dir = tmp_path / "build"
    nb_path = pathlib.Path(__file__).parent / "data" / "noparamtest.ipynb"
    cli_runner = CliRunner()
    result = cli_runner.invoke(
        cli,
        [
            "image",
            "build",
            "--skip-build",
            "--build-dir",
            str(build_dir),
            str(nb_path),
        ],
    )
    assert result.exit_code == 0
    assert (build_dir / "Dockerfile").is_file()
    assert (build_dir / "environment.yml").is_file()
    from_env_mock.assert_not_called()
