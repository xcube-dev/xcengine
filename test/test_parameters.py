import json
import os

import pytest

import xarray as xr
import yaml

import xcengine.parameters
from xcengine.parameters import NotebookParameters

from test_util import dataset


@pytest.fixture
def expected_vars():
    return {
        "some_int": (int, 42),
        "some_float": (float, 3.14159),
        "some_string": (str, "foo"),
        "some_bool": (bool, False),
    }


@pytest.fixture
def params_yaml():
    return """
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


@pytest.fixture
def notebook_parameters(expected_vars):
    return xcengine.parameters.NotebookParameters(expected_vars)


@pytest.fixture
def stac_catalog():
    return {
        "description": "Root catalog",
        "id": "catalog",
        "links": [
            {
                "href": "item.json",
                "rel": "item",
                "type": "application/geo+json",
            }
        ],
        "stac_version": "1.0.0",
        "type": "Catalog",
    }


@pytest.fixture
def stac_item():
    return {
        "stac_version": "1.0.0",
        "stac_extensions": [],
        "type": "Feature",
        "id": "ds1",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [170, -45],
                    [170, -46],
                    [171, -46],
                    [171, -45],
                    [170, -45],
                ]
            ],
        },
        "properties": {
            "datetime": "2020-01-01T00:00:00.000000Z",
            "start_datetime": "2020-01-01T00:00:00.000000Z",
            "end_datetime": "2020-01-03T00:00:00.000000Z",
            "title": "dataset",
        },
        "bbox": [170, -46, 171, -45],
        "assets": {
            "asset1": {
                "type": "application/netcdf",
                "roles": ["data"],
                "title": "Asset 1",
                "href": "ds1.nc",
            }
        },
        "links": [],
    }


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


def test_parameters_get_cwl_step_inputs(notebook_parameters):
    assert notebook_parameters.get_cwl_step_inputs() == {
        "some_int": "some_int",
        "some_float": "some_float",
        "some_string": "some_string",
        "some_bool": "some_bool",
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


def test_parameters_from_yaml(expected_vars, params_yaml):
    assert NotebookParameters.from_yaml(params_yaml).params == expected_vars


def test_parameters_from_yaml_with_dataset():
    import xarray as xr

    yaml_ = """
some_ds:
    type: Dataset
    default: null
"""
    assert NotebookParameters.from_yaml(yaml_).params == {
        "some_ds": (xr.Dataset, None)
    }


def test_parameters_from_file(tmp_path, expected_vars, params_yaml):
    path = tmp_path / "params.yaml"
    path.write_text(params_yaml)
    assert NotebookParameters.from_yaml_file(path).params == expected_vars


def test_parameters_invalid_cwl_type():
    with pytest.raises(ValueError):
        NotebookParameters({"x": (Exception, 666)}).get_cwl_workflow_inputs()


def test_parameters_read_cli_arguments(notebook_parameters):
    assert notebook_parameters.read_params_from_cli(
        [
            "execute.py",
            "--some-int",
            "23",
            "--some-string",
            "bar",
            "--irrelevant-argument",
            "--some-float",
            "2.71828",
            "--some-bool",
        ]
    ) == {
        "some_int": 23,
        "some_float": 2.71828,
        "some_string": "bar",
        "some_bool": True,
    }
    assert notebook_parameters.read_params_from_cli([]) == {}


def test_parameters_read_cli_arguments_with_product(
    tmp_path, dataset, stac_catalog, stac_item
):
    dataset.to_netcdf(tmp_path / "ds1.nc")
    (tmp_path / "catalog.json").write_text(json.dumps(stac_catalog))
    (tmp_path / "item.json").write_text(json.dumps(stac_item))

    params = NotebookParameters(
        {"some_int": (int, 42), "ds1": (xr.Dataset, None)}
    )
    param_values = params.read_params_from_cli(
        ["execute.py", "--some-int", "23", "--product", str(tmp_path)]
    )
    assert len(param_values) == 2
    assert param_values["some_int"] == 23
    assert (dataset.v == param_values["ds1"].v).all()


def test_parameters_read_env_arguments(notebook_parameters):
    prefix = "xce_"
    os.environ.update(
        {
            prefix + k: v
            for k, v in {
                "some_int": "42",
                "some_float": "3.14159",
                "some_string": "foo",
                "some_bool": "False",
            }.items()
        }
    )
    expected = {
        "some_int": 42,
        "some_float": 3.14159,
        "some_string": "foo",
        "some_bool": False,
    }
    assert notebook_parameters.read_params_from_env() == expected
    assert notebook_parameters.read_params_combined([]) == expected


def test_parameters_read_params_combined(notebook_parameters):
    prefix = "xce_"
    os.environ.update(
        {
            prefix + k: v
            for k, v in {
                "some_int": "42",
                "some_string": "foo",
                "some_bool": "False",
            }.items()
        }
    )
    os.environ.pop(prefix + "some_float", None)
    assert notebook_parameters.read_params_combined(
        [
            "execute.py",
            "--some-string",
            "bar",
            "--irrelevant-argument",
            "--some-float",
            "2.71828",
        ]
    ) == {
        "some_int": 42,
        "some_float": 2.71828,
        "some_string": "bar",
        "some_bool": False,
    }


def test_read_datasets_from_product(
    tmp_path, dataset, stac_catalog, stac_item
):
    dataset.to_netcdf(tmp_path / "ds1.nc")
    (tmp_path / "catalog.json").write_text(json.dumps(stac_catalog))
    (tmp_path / "item.json").write_text(json.dumps(stac_item))

    params = NotebookParameters({"ds1": (xr.Dataset, None)})
    values = {}
    params.read_datasets_from_product(tmp_path, values)
    assert (dataset.v == values["ds1"].v).all()


def test_read_datasets_from_product_no_catalog(tmp_path):
    params = NotebookParameters({"ds1": (xr.Dataset, None)})
    with pytest.raises(RuntimeError) as error:
        params.read_datasets_from_product(tmp_path, {})
    assert "catalog.json" in str(error)


def test_read_datasets_from_product_missing_items(
    tmp_path, stac_catalog, stac_item
):
    (tmp_path / "catalog.json").write_text(json.dumps(stac_catalog))
    (tmp_path / "item.json").write_text(json.dumps(stac_item))
    params = NotebookParameters(
        {"foo": (xr.Dataset, None), "bar": (xr.Dataset, None)}
    )
    with pytest.raises(RuntimeError) as error:
        params.read_datasets_from_product(tmp_path, {})
    for substring in "missing", "foo", "bar":
        assert substring in str(error)
