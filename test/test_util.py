import os
from pathlib import Path

import pystac
import pytest
import xarray as xr

from xcengine.util import clear_directory, write_stac, save_datasets


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


@pytest.mark.parametrize("write_zarrs", [False, True])
def test_write_stac(tmp_path, dataset, write_zarrs):
    datasets = {"ds1": dataset, "ds2": dataset}
    if write_zarrs:
        output_path = tmp_path / "output"
        output_path.mkdir()
        for ds_id, ds in datasets.items():
            ds.to_zarr(output_path / (ds_id + ".zarr"))

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
        ds_id: [
            str(Path(tmp_path / ds_id / f"{ds_id}.zarr").resolve(strict=False))
        ]
        for ds_id in datasets.keys()
    }


@pytest.mark.parametrize("eoap_mode", [False, True])
def test_save_datasets(tmp_path, dataset, eoap_mode):
    datasets = {"ds1": dataset, "ds2": dataset}
    save_datasets(datasets, tmp_path, eoap_mode)
    for ds_id in datasets.keys():
        assert (
            tmp_path / (ds_id if eoap_mode else "output") / (ds_id + ".zarr")
        ).is_dir()
    catalogue_path = tmp_path / "catalog.json"
    if eoap_mode:
        assert catalogue_path.is_file()
    else:
        assert not catalogue_path.exists()
