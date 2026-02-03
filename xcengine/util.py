# Copyright (c) 2024-2025 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.

from collections import namedtuple
from datetime import datetime
import pathlib
import shutil
from typing import NamedTuple, Any, Mapping

import pystac
import xarray as xr
from xarray import Dataset


def clear_directory(directory: pathlib.Path) -> None:
    for path in directory.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def write_stac(
    datasets: Mapping[str, xr.Dataset], stac_root: pathlib.Path
) -> None:
    catalog_path = stac_root / "catalog.json"
    if catalog_path.exists():
        # Assume that the user code generated its own stage-out data
        return
    catalog = pystac.Catalog(
        id="catalog",
        description="Root catalog",
        href=f"{catalog_path}",
    )
    for ds_name, ds in datasets.items():
        output_format = ds.attrs.get("xcengine_output_format", "zarr")
        suffix = "nc" if output_format == "netcdf" else "zarr"
        output_name = f"{ds_name}.{suffix}"
        output_path = stac_root / "output" / output_name
        asset_parent = stac_root / ds_name
        asset_parent.mkdir(parents=True, exist_ok=True)
        asset_path = asset_parent / output_name
        if output_path.exists():
            # If a Zarr for this asset is present in the output directory,
            # move it into the corresponding STAC subdirectory. If not,
            # we write the same STAC items with the same asset links anyway
            # and assume that the caller will take care of actually writing
            # the asset.
            output_path.rename(asset_path)
        asset = pystac.Asset(
            roles=["data", "visual"],
            href=str(asset_path),
            # No official media type for Zarr yet, but "application/vnd.zarr"
            # https://github.com/radiantearth/stac-spec/issues/713 and listed in
            # https://humanbrainproject.github.io/openMINDS/v3/core/v4/data/contentType.html
            # https://planetarycomputer.microsoft.com/api/stac/v1/collections/terraclimate
            # uses the similar "application/vnd+zarr" but RFC 6838 mandates
            # "." rather than "+".
            media_type=(
                "application/x-netcdf"
                if output_format == "netcdf"
                else "application/vnd.zarr"
            ),
            title=ds.attrs.get("title", ds_name),
        )

        class Bounds(NamedTuple):
            left: float
            bottom: float
            right: float
            top: float

        # TODO determine and set actual bounds here
        bb = Bounds(0, -90, 360, 90)
        item = pystac.Item(
            id=ds_name,
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [bb.left, bb.bottom],
                    [bb.left, bb.top],
                    [bb.right, bb.top],
                    [bb.right, bb.bottom],
                    [bb.left, bb.bottom],
                ],
            },
            bbox=[bb.left, bb.bottom, bb.right, bb.top],
            datetime=None,
            start_datetime=datetime(2000, 1, 1),  # TODO set actual start
            end_datetime=datetime(2001, 1, 1),  # TODO set actual end
            properties={},  # datetime values will be filled in automatically
            assets={"zarr": asset},
        )
        catalog.add_item(item)
    catalog.make_all_asset_hrefs_relative()
    catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)


def save_datasets(
    datasets: Mapping[str, Dataset], output_path: pathlib.Path, eoap_mode: bool
) -> dict[str, pathlib.Path]:
    saved_datasets = {}
    # EOAP doesn't require an "output" subdirectory (output can go anywhere
    # in the CWD) but it's used by xcetool's built-in runner.
    # Note that EOAP runners typically override the image-specified CWD.
    for ds_id, ds in datasets.items():
        output_subpath = output_path / (ds_id if eoap_mode else "output")
        output_subpath.mkdir(parents=True, exist_ok=True)
        output_format = ds.attrs.get("xcengine_output_format", "zarr")
        suffix = "nc" if output_format == "netcdf" else "zarr"
        dataset_path = output_subpath / f"{ds_id}.{suffix}"
        saved_datasets[ds_id] = dataset_path

        if output_format == "netcdf":
            ds.to_netcdf(dataset_path)
        else:
            ds.to_zarr(dataset_path)
    # The "finished" file is a flag to indicate to a runner when
    # processing is complete, though the xcetool runner doesn't yet use it.
    (output_path / "finished").touch()
    if eoap_mode:
        write_stac(datasets, output_path)
    return saved_datasets
