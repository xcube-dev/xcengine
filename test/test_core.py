import datetime
import json
import pathlib
import pytz
from io import BufferedReader
import yaml
import cwltool.load_tool

import pytest
from unittest.mock import Mock

import docker.models.images
import schema_salad.exceptions

import xcengine.core
import xcengine.parameters

from unittest.mock import MagicMock, patch

from xcengine.core import ChunkStream, ImageBuilder, ScriptCreator


@patch("xcengine.core.ScriptCreator.__init__")
@pytest.mark.parametrize("tag", [None, "bar"])
@pytest.mark.parametrize("use_env", [False, True])
def test_image_builder_init(init_mock, tmp_path, tag, use_env):
    nb_path = tmp_path / "foo.ipynb"
    nb_path.touch()
    if use_env:
        environment = tmp_path / "environment.yml"
        environment.touch()
    else:
        environment = None
    build_path = tmp_path / "build"
    build_path.mkdir()
    init_mock.return_value = None
    ib = ImageBuilder(
        notebook=nb_path,
        environment=environment,
        build_dir=build_path,
        tag=tag,
    )
    assert ib.notebook == nb_path
    assert ib.build_dir == build_path
    assert ib.environment == environment
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
