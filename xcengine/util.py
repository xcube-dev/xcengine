# Copyright (c) 2024-2025 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.
from collections import namedtuple
from datetime import datetime
import pathlib
import shutil

import pystac
import xarray as xr


def clear_directory(directory: pathlib.Path) -> None:
    for path in directory.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def write_stac(
    datasets: dict[str, xr.Dataset], stac_root: pathlib.Path
) -> None:
    catalog = pystac.Catalog(
        id="catalog",
        description="Root catalog",
        href=f"{stac_root}/catalog.json",
    )
    for ds_name in datasets:
        asset_path = str(stac_root / "output" / (ds_name + ".zarr"))
        asset = pystac.Asset(
            roles=["data"],
            href=asset_path,
            # No official media type for Zarr yet, but "application/vnd.zarr"
            # https://github.com/radiantearth/stac-spec/issues/713 and listed in
            # https://humanbrainproject.github.io/openMINDS/v3/core/v4/data/contentType.html
            # https://planetarycomputer.microsoft.com/api/stac/v1/collections/terraclimate
            # uses the similar "application/vnd+zarr" but RFC 6838 mandates
            # "." rather than "+".
            media_type="application/vnd.zarr",
        )
        bb = namedtuple("Bounds", ["left", "bottom", "right", "top"])(
            0, -90, 360, 90
        )  # TODO determine and set actual bounds here
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
