import datetime
import json
import pathlib
import pytz
from io import BufferedReader

import pytest
from unittest.mock import Mock

import docker.models.images

import xcengine.core
import xcengine.parameters

from unittest.mock import MagicMock, patch

from xcengine.core import ChunkStream, ImageBuilder


@patch("xcengine.core.ScriptCreator.__init__")
@pytest.mark.parametrize("tag", [None, "bar"])
def test_image_builder_init(init_mock, tmp_path, tag):
    nb_path = tmp_path / "foo.ipynb"
    nb_path.touch()
    environment = tmp_path / "environment.yml"
    environment.touch()
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
    if tag is None:
        assert abs(
            datetime.datetime.now(datetime.UTC)
            - pytz.utc.localize(
                datetime.datetime.strptime(ib.tag, ImageBuilder.tag_format)
            )
        ) < datetime.timedelta(seconds=10)
    else:
        assert ib.tag == tag
    init_mock.assert_called_once_with(nb_path)


def test_init_runner_invalid_image_type():
    with pytest.raises(ValueError, match='Invalid type "int"'):
        # noinspection PyTypeChecker
        xcengine.core.ContainerRunner(666, pathlib.Path("/foo"))


def test_init_runner_with_string():
    image_name = "foo"
    image_mock = Mock(docker.models.images.Image)
    client_mock = Mock(docker.client.DockerClient)

    def get_mock(name):
        assert name == image_name
        return image_mock

    client_mock.images.get = get_mock
    runner = xcengine.core.ContainerRunner(
        image_name, pathlib.Path("/foo"), client=client_mock
    )
    assert image_mock == runner.image


def test_init_runner_with_image():
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
