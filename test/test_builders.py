import pathlib
import pytest
from unittest.mock import Mock

import docker.models.images

import xcengine.builders


def test_init_runner_invalid_image_type():
    with pytest.raises(ValueError, match='Invalid type "int"'):
        # noinspection PyTypeChecker
        xcengine.builders.ContainerRunner(666, pathlib.Path("/foo"))


def test_init_runner_with_string():
    image_name = "foo"
    image_mock = Mock(docker.models.images.Image)
    client_mock = Mock(docker.client.DockerClient)

    def get_mock(name):
        assert name == image_name
        return image_mock

    client_mock.images.get = get_mock
    runner = xcengine.builders.ContainerRunner(
        image_name, pathlib.Path("/foo"), client=client_mock
    )
    assert image_mock == runner.image


def test_init_runner_with_image():
    runner = xcengine.builders.ContainerRunner(
        image := Mock(docker.models.images.Image), pathlib.Path("/foo")
    )
    assert runner.image == image