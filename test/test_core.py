import datetime
import json
import os
import pathlib
import signal
import threading
import time

import pytz
from io import BufferedReader
import yaml
import cwltool.load_tool

import pytest
from unittest.mock import Mock

import docker.models.images
import schema_salad.exceptions
from docker import DockerClient
from docker.models.containers import Container

import xcengine.core
import xcengine.parameters

from unittest.mock import MagicMock, patch

from xcengine.core import ChunkStream, ImageBuilder, ScriptCreator


@patch("xcengine.core.ScriptCreator.__init__")
@pytest.mark.parametrize("tag", [None, "bar"])
@pytest.mark.parametrize(
    "env_file_name", ["environment.yml", "foo.yaml", None]
)
@pytest.mark.parametrize("use_env_file_param", [False, True])
def test_image_builder_init(
    init_mock,
    tmp_path: pathlib.Path,
    tag: str | None,
    env_file_name: str | None,
    use_env_file_param: bool,
):
    nb_path = tmp_path / "foo.ipynb"
    nb_path.touch()
    if env_file_name is not None:
        environment_path = tmp_path / env_file_name
        environment_path.touch()
    else:
        environment_path = None
    build_path = tmp_path / "build"
    build_path.mkdir()
    init_mock.return_value = None
    ib = ImageBuilder(
        notebook=nb_path,
        environment=environment_path if use_env_file_param else None,
        build_dir=build_path,
        tag=tag,
    )
    assert ib.notebook == nb_path
    assert ib.build_dir == build_path
    expected_env = (
        environment_path
        if (use_env_file_param or env_file_name == "environment.yml")
        else None
    )
    assert ib.environment == expected_env
    if tag is None:
        assert abs(
            datetime.datetime.now(datetime.UTC)
            - pytz.utc.localize(
                datetime.datetime.strptime(
                    ib.tag, nb_path.stem + ":" + ImageBuilder.tag_format
                )
            )
        ) < datetime.timedelta(seconds=10)
    else:
        assert ib.tag == tag
    init_mock.assert_called_once_with(nb_path)


def test_runner_init_invalid_image_type():
    with pytest.raises(ValueError, match='Invalid type "int"'):
        # noinspection PyTypeChecker
        xcengine.core.ContainerRunner(666, pathlib.Path("/foo"))


@patch("docker.from_env")
@pytest.mark.parametrize("pass_client", [False, True])
def test_runner_init_with_string(from_env_mock, pass_client):
    image_name = "foo"
    image_mock = Mock(docker.models.images.Image)
    client_mock = Mock(docker.client.DockerClient)
    from_env_mock.return_value = client_mock

    def get_mock(name):
        assert name == image_name
        return image_mock

    client_mock.images.get = get_mock
    runner = xcengine.core.ContainerRunner(
        image_name,
        pathlib.Path("/foo"),
        client=client_mock if pass_client else None,
    )
    assert image_mock == runner.image


def test_runner_init_with_image():
    runner = xcengine.core.ContainerRunner(
        image := Mock(docker.models.images.Image), pathlib.Path("/foo")
    )
    assert runner.image == image


@pytest.mark.parametrize("keep", [False, True])
def test_runner_run_keep(keep: bool):
    runner = xcengine.core.ContainerRunner(
        image := Mock(docker.models.images.Image),
        None,
        client := Mock(DockerClient),
    )
    image.tags = []
    client.containers.run.return_value = (container := MagicMock(Container))
    container.status = "exited"
    runner.run(False, 8080, False, keep)
    if keep:
        container.remove.assert_not_called()
    else:
        container.remove.assert_called_once_with(force=True)


@pytest.mark.parametrize(
    "script_args", [None, [], ["--foo", "--bar", "42", "--baz", "somestring"]]
)
@pytest.mark.parametrize("run_batch", [False, True])
def test_runner_extra_args(script_args: list[str] | None, run_batch: bool):
    runner = xcengine.core.ContainerRunner(
        image := Mock(docker.models.images.Image),
        None,
        client := Mock(DockerClient),
    )
    image.tags = []
    client.containers.run.return_value = (container := MagicMock(Container))
    container.status = "exited"
    runner.run(
        run_batch=run_batch,
        host_port=None,
        from_saved=False,
        keep=False,
        script_args=script_args,
    )
    run_args = client.containers.run.call_args
    expected_run_args = ["--batch"] if run_batch else []
    expected_script_args = [] if script_args is None else script_args
    command = run_args[1]["command"]
    assert (
        command
        == ["python", "execute.py"] + expected_run_args + expected_script_args
    )


def test_runner_sigint():
    runner = xcengine.core.ContainerRunner(
        image := Mock(docker.models.images.Image),
        None,
        client := Mock(DockerClient),
    )
    image.tags = []
    client.containers.run.return_value = (container := Mock(Container))
    container.status = "running"

    def container_stop():
        container.status = "stopped"

    container.stop = container_stop
    pid = os.getpid()

    old_alarm_handler = signal.getsignal(signal.SIGALRM)

    class AlarmException(Exception):
        pass

    def alarm_handler(signum, frame):
        raise AlarmException()

    signal.signal(signal.SIGALRM, alarm_handler)

    def interrupt_process():
        time.sleep(1)  # allow one second for runner to start
        os.kill(pid, signal.SIGINT)

    thread = threading.Thread(target=interrupt_process, daemon=True)
    thread.start()

    signal.alarm(5)
    try:
        # Should trap imminent SIGINT from interrupt_process and exit quickly
        runner.run(False, 8080, False, False)
    except AlarmException:
        # time-out, exception raised by alarm_handler
        # We need a time-out so that the test fails rather than hanging.
        assert False, "Container did not stop on SIGINT"
    finally:
        # Reset the alarm handler and cancel the alarm to avoid affecting
        # subsequent tests.
        signal.signal(signal.SIGALRM, old_alarm_handler)
        signal.alarm(0)
    assert container.status == "stopped"


@patch("xcengine.core.subprocess.run")
def test_pip(mock_run):
    pip_output = {
        "version": "1",
        "pip_version": "24.3.1",
        "installed": [
            {"metadata": {"name": "pyfiglet"}, "installer": "pip"},
            {
                "metadata": {"name": "xrlint"},
                "direct_url": {"url": "file:///home/pont/loc/repos/xrlint"},
                "installer": "pip",
            },
            {"metadata": {"name": "setuptools"}},
            {
                "metadata": {"name": "pip"},
                "direct_url": {
                    "url": "file:///home/conda/feedstock_root/build_artifacts/pip_1734466185654/work"
                },
                "installer": "conda",
            },
            {"metadata": {"name": "textdistance"}, "installer": "pip"},
        ],
    }
    mock = MagicMock()
    mock.configure_mock(stdout=json.dumps(pip_output))
    mock_run.return_value = mock
    inspector = xcengine.core.PipInspector()
    assert inspector.is_local("xrlint")
    assert not inspector.is_local("pyfiglet")
    assert not inspector.is_local("textdistance")
    assert not inspector.is_local("pip")
    assert not inspector.is_local("setuptools")


def test_chunk_stream():
    chunks = ["123", "456", "789", "abc"]
    expected = "".join(chunks).encode()
    bytegen = (chunk.encode() for chunk in chunks)
    chunk_stream = ChunkStream(bytegen)
    assert chunk_stream.readable()
    assert BufferedReader(chunk_stream).read() == expected


def test_script_creator_init_with_parameters():
    script_creator = ScriptCreator(
        pathlib.Path(__file__).parent / "data" / "paramtest.ipynb"
    )
    assert script_creator.nb_params.params == {
        "parameter_1": (int, 6),
        "parameter_2": (str, "default value"),
    }


def test_script_creator_init_no_parameters():
    script_creator = ScriptCreator(
        pathlib.Path(__file__).parent / "data" / "noparamtest.ipynb"
    )
    assert script_creator.nb_params.params == {}


@pytest.mark.parametrize("clear", [True, False])
def test_script_creator_convert_notebook_to_script(tmp_path, clear):
    (output_dir := tmp_path / "output").mkdir()
    extraneous_filename = "foo"
    (output_dir / extraneous_filename).touch()
    script_creator = ScriptCreator(
        pathlib.Path(__file__).parent / "data" / "paramtest.ipynb"
    )
    script_creator.convert_notebook_to_script(output_dir, clear)
    filenames = {
        "user_code.py",
        "execute.py",
        "parameters.py",
        "parameters.yaml",
        "util.py",
    } | (set() if clear else {extraneous_filename})
    expected = {output_dir / f for f in filenames}
    assert set(output_dir.iterdir()) == expected
    # TODO test execution as well?


@pytest.mark.parametrize("nb_name", ["noparamtest", "paramtest"])
def test_script_creator_cwl(tmp_path, nb_name):
    nb_path = pathlib.Path(__file__).parent / "data" / f"{nb_name}.ipynb"
    script_creator = ScriptCreator(nb_path)
    image_tag = "foo"
    cwl_path = tmp_path / "test.cwl"
    cwl = script_creator.create_cwl(image_tag)
    with open(cwl_path, "w") as fh:
        yaml.dump(cwl, fh)
    loading_context, workflowobj, uri = cwltool.load_tool.fetch_document(
        str(cwl_path)
    )
    try:
        cwltool.load_tool.resolve_and_validate_document(
            loading_context, workflowobj, uri
        )
    except schema_salad.exceptions.ValidationException:
        pytest.fail("CWL validation failed")
    graph = cwl["$graph"]
    cli_tools = [n for n in graph if n["class"] == "CommandLineTool"]
    assert len(cli_tools) == 1
    cli_tool = cli_tools[0]
    assert (
        cli_tool["requirements"]["DockerRequirement"]["dockerPull"]
        == image_tag
    )
    assert cli_tool["hints"]["DockerRequirement"]["dockerPull"] == image_tag
    workflows = [n for n in graph if n["class"] == "Workflow"]
    assert len(workflows) == 1
    workflow = workflows[0]
    assert workflow["id"] == (
        nb_path.stem if nb_name == "noparamtest" else "my-workflow"
    )


def test_script_creator_notebook_config():
    nb_path = pathlib.Path(__file__).parent / "data" / "paramtest.ipynb"
    script_creator = ScriptCreator(nb_path)
    config = script_creator.nb_params.config
    assert config["environment_file"] == "my-environment.yml"
    assert config["container_image_tag"] == "my-tag"


def test_image_builder_notebook_config(tmp_path):
    nb_path = pathlib.Path(__file__).parent / "data" / "paramtest.ipynb"
    image_builder = ImageBuilder(nb_path, None, tmp_path, None)
    config = image_builder.script_creator.nb_params.config
    assert config["environment_file"] == "my-environment.yml"
    assert config["container_image_tag"] == "my-tag"


def test_image_builder_write_dockerfile(tmp_path):
    ImageBuilder.write_dockerfile(
        dockerfilepath := tmp_path / "as-yet-nonexistent-dir" / "Dockerfile"
    )
    with open(dockerfilepath) as fh:
        content = fh.read()
        assert content.startswith("FROM ")
        assert "\nENTRYPOINT " in content


@patch("docker.from_env")
@pytest.mark.parametrize("set_env", [False, True])
def test_image_builder_build_skip_build(from_env_mock, tmp_path, set_env):
    build_dir = tmp_path / "build"
    env_path = tmp_path / "env2.yaml"
    env_def = {
        "name": "foo",
        "channels": "bar",
        "dependencies": ["python >=3.13", "baz >=42.0"],
    }
    env_path.write_text(yaml.safe_dump(env_def))
    image_builder = ImageBuilder(
        pathlib.Path(__file__).parent / "data" / "noparamtest.ipynb",
        env_path if set_env else None,
        build_dir,
        None,
    )
    image_builder.build(skip_build=True)
    from_env_mock.assert_not_called()
    env_path = build_dir / "environment.yml"
    assert env_path.is_file()
    output_env = yaml.safe_load(env_path.read_text())
    assert {"name", "channels", "dependencies"} <= set(output_env)
    if set_env:
        assert output_env["name"] == env_def["name"]
        assert output_env["channels"] == env_def["channels"]
        assert set(output_env["dependencies"]) >= set(env_def["dependencies"])
