import pytest

import yaml

import xcengine.parameters
from xcengine.parameters import NotebookParameters


@pytest.fixture
def expected_vars():
    return {
        "some_int": (int, 42),
        "some_float": (float, 3.14159),
        "some_string": (str, "foo"),
        "some_bool": (bool, False),
    }


@pytest.fixture
def notebook_parameters(expected_vars):
    return xcengine.parameters.NotebookParameters(expected_vars)


def test_parameters_get_commandline_inputs(notebook_parameters):
    assert notebook_parameters.get_cwl_commandline_inputs() == {
        "some_int": {
            "type": "long",
            "default": 42,
            "label": "some_int",
            "doc": "some_int",
            "inputBinding": {"prefix": "--some-int"},
        },
        "some_float": {
            "type": "double",
            "default": 3.14159,
            "label": "some_float",
            "doc": "some_float",
            "inputBinding": {"prefix": "--some-float"},
        },
        "some_string": {
            "type": "string",
            "default": "foo",
            "label": "some_string",
            "doc": "some_string",
            "inputBinding": {"prefix": "--some-string"},
        },
        "some_bool": {
            "type": "boolean",
            "default": False,
            "label": "some_bool",
            "doc": "some_bool",
            "inputBinding": {"prefix": "--some-bool"},
        },
    }


def test_parameters_from_code(expected_vars):
    assert (
        xcengine.parameters.NotebookParameters.from_code(
            """
some_int = 42
some_float = 3.14159
some_string = "foo"
some_bool = False
    """
        ).params
        == expected_vars
    )


def test_parameters_get_workflow_inputs(notebook_parameters):
    assert notebook_parameters.get_cwl_workflow_inputs() == {
        "some_int": {
            "type": "long",
            "default": 42,
            "label": "some_int",
            "doc": "some_int",
        },
        "some_float": {
            "type": "double",
            "default": 3.14159,
            "label": "some_float",
            "doc": "some_float",
        },
        "some_string": {
            "type": "string",
            "default": "foo",
            "label": "some_string",
            "doc": "some_string",
        },
        "some_bool": {
            "type": "boolean",
            "default": False,
            "label": "some_bool",
            "doc": "some_bool",
        },
    }


def test_parameters_to_yaml(notebook_parameters):
    assert yaml.safe_load(notebook_parameters.to_yaml()) == {
        "some_int": {"type": "int", "default": 42},
        "some_float": {"type": "float", "default": 3.14159},
        "some_string": {"type": "str", "default": "foo"},
        "some_bool": {"type": "bool", "default": False},
    }


def test_parameters_from_yaml(expected_vars):
    assert (
        NotebookParameters.from_yaml(
            """
some_int:
    type: int
    default: 42
some_float:
    type: float
    default: 3.14159
some_string:
    type: str
    default: foo
some_bool:
    type: bool
    default: false
"""
        ).params
        == expected_vars
    )


def test_parameters_invalid_cwl_type():
    with pytest.raises(ValueError):
        NotebookParameters({"x": (Exception, 666)}).get_cwl_workflow_inputs()


def test_parameters_process_arguments(notebook_parameters):
    args = [
        "execute.py",
        "--some-bool",
        "True",
        "--some-int",
        "23",
        "--some-string",
        "bar",
        "--irrelevant-argument",
        "--some-float",
        "2.71828",
    ]
    param_values = notebook_parameters.process_arguments(args)
    assert param_values == {
        "some_int": 23,
        "some_float": 2.71828,
        "some_string": "bar",
        "some_bool": True,
    }
