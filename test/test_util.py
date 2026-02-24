import logging
import os
import sys
from collections import namedtuple
from pathlib import Path
from unittest import mock
from unittest.mock import patch

import pystac
import pytest
import xarray as xr
from xcube.server.webservers.tornado import TornadoFramework

from xcengine.util import (
    clear_directory,
    write_stac,
    save_datasets,
)
import xcengine.util


@pytest.fixture
def dataset():
    return xr.Dataset(
        data_vars=dict(
            v=(
                ["time", "lat", "lon"],
                [[[1, 2], [3, 4]], [[5, 6], [7, 8]], [[9, 0], [1, 2]]],
            ),
        ),
        coords=dict(
            lon=[10, 20],
            lat=[40, 50],
            time=["2020-01-01", "2020-01-02", "2020-01-03"],
        ),
        attrs=dict(title="example dataset"),
    )


def test_clear_directory(tmp_path):
    subdir = tmp_path / "foo" / "bar" / "baz"
    os.makedirs(subdir)
    for name in "a", "b", "c":
        for path in Path(tmp_path / name), subdir / name:
            path.write_text("test")
    clear_directory(tmp_path)
    assert tmp_path.exists()
    assert tmp_path.is_dir()
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize("write_datasets", [False, True])
def test_write_stac(tmp_path, dataset, write_datasets):
    datasets = {"ds1": dataset, "ds2": dataset.copy()}
    datasets["ds2"].attrs["xcengine_output_format"] = "netcdf"
    if write_datasets:
        output_path = tmp_path / "output"
        output_path.mkdir()
        datasets["ds1"].to_zarr(output_path / ("ds1.zarr"))
        datasets["ds2"].to_netcdf(output_path / ("ds2.nc"))

    write_stac(datasets, tmp_path)
    catalog = pystac.Catalog.from_file(tmp_path / "catalog.json")
    items = set(catalog.get_items(recursive=True))
    assert {item.id for item in items} == datasets.keys()
    catalog.make_all_asset_hrefs_absolute()
    data_asset_hrefs = {
        item.id: [a.href for a in item.assets.values() if "data" in a.roles]
        for item in items
    }
    assert data_asset_hrefs == {
        "ds1": [str((tmp_path / "ds1" / "ds1.zarr").resolve(strict=False))],
        "ds2": [str((tmp_path / "ds2" / "ds2.nc").resolve(strict=False))],
    }


@pytest.mark.parametrize("eoap_mode", [False, True])
@pytest.mark.parametrize("ds2_format", [None, "zarr", "netcdf"])
def test_save_datasets(tmp_path, dataset, eoap_mode, ds2_format):
    datasets = {"ds1": dataset, "ds2": dataset.copy()}
    if ds2_format is not None:
        datasets["ds2"].attrs["xcengine_output_format"] = ds2_format
    save_datasets(datasets, tmp_path, eoap_mode)

    def outdir(ds_id):
        return tmp_path / (ds_id if eoap_mode else "output")

    assert (outdir("ds1") / "ds1.zarr").is_dir()
    ds2_suffix = "nc" if ds2_format == "netcdf" else "zarr"
    ds2_path = outdir("ds2") / f"ds2.{ds2_suffix}"
    if ds2_format == "netcdf":
        assert ds2_path.is_file()
    else:
        assert ds2_path.is_dir()
    catalogue_path = tmp_path / "catalog.json"
    if eoap_mode:
        assert catalogue_path.is_file()
    else:
        assert not catalogue_path.exists()


def test_start_server():
    import xcube.core.new

    framework_patch = mock.MagicMock()
    framework_patch.get_framework_class.return_value = TornadoFramework
    server_object_patch = mock.MagicMock()
    server_module_patch = mock.MagicMock()
    server_module_patch.Server.return_value = server_object_patch
    with patch.dict(
        sys.modules,
        {
            "xcube.server.framework": framework_patch,
            "xcube.server.server": server_module_patch,
        },
    ):
        xcengine.util.start_server(
            {"ds1": xcube.core.new.new_cube()},
            {},
            namedtuple("Args", "batch from_saved xcube_viewer_api_url")(
                False, False, "http://localhost:8000/"
            ),
            logging.getLogger(),
        )

    server_object_patch.start.assert_called_once()
