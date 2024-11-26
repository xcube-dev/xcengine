import pathlib
import pytest
from unittest.mock import Mock

import docker.models.images

import xcengine.core


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


@pytest.fixture
def notebook_parameters():
    return xcengine.core.NotebookParameters("""
some_int = 42
some_float = 3.14159
some_string = "foo"
some_bool = False
    """)


def test_parameters_init(notebook_parameters):
    assert notebook_parameters.vars == {
        "some_int": (int, 42),
        "some_float": (float, 3.14159),
        "some_string": (str, "foo"),
        "some_bool": (bool, False)
    }


def test_parameters_get_workflow_inputs(notebook_parameters):
    assert notebook_parameters.get_cwl_workflow_inputs() == {
        "some_int": {
            "type": "long",
            "default": 42,
            "label": "some_int",
            "doc": "some_int"
        },
        "some_float": {
            "type": "double",
            "default": 3.14159,
            "label": "some_float",
            "doc": "some_float"
        },
        "some_string": {
            "type": "string",
            "default": "foo",
            "label": "some_string",
            "doc": "some_string"
        },
        "some_bool": {
            "type": "boolean",
            "default": False,
            "label": "some_bool",
            "doc": "some_bool"
        },

    }
