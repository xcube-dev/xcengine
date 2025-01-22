import os
from pathlib import Path

import pystac
import pytest
import xarray as xr

from xcengine.util import clear_directory, write_stac


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


def test_write_stac(tmp_path, dataset):
    write_stac({"ds1": dataset, "ds2": dataset}, tmp_path)
    catalog = pystac.Catalog.from_file(tmp_path / "catalog.json")
    items = set(catalog.get_items(recursive=True))
    assert {item.id for item in items} == {"ds1", "ds2"}
    catalog.make_all_asset_hrefs_absolute()
    data_asset_hrefs = {
        item.id: [
            a.href  # (Path(item.self_href) / a.href).resolve(strict=False)
            for a in item.assets.values()
            if "data" in a.roles
        ]
        for item in items
    }
    assert data_asset_hrefs == {
        ds: [
            str(Path(tmp_path / "output" / f"{ds}.zarr").resolve(strict=False))
        ]
        for ds in {"ds1", "ds2"}
    }
