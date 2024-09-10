import argparse
import pathlib
import logging

import xarray as xr
from xcube.server.server import Server
from xcube.server.framework import get_framework_class
import xcube.util.plugin
import xcube.core.new

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# We use double underscores for all variable names to reduce the chance of a
# collision with identifiers in the user code.

__parser = argparse.ArgumentParser()
__parser.add_argument("--save", action="store_true")
__parser.add_argument("--serve", action="store_true")
__parser.add_argument("--from-saved", action="store_true")
__args = __parser.parse_args()
xcube.util.plugin.init_plugins()

__datasets = {name: thing for name, thing in locals().copy().items()
              if isinstance(thing, xr.Dataset) and not name.startswith("_")}

__saved_datasets = {}

if __args.save:
    __output_path = pathlib.Path.home() / "output"
    __output_path.mkdir(parents=True, exist_ok=True)
    for __name, __dataset in __datasets.items():
        __dataset_path = __output_path / (__name + ".zarr")
        __saved_datasets[__name] = __dataset_path
        __dataset.to_zarr(__dataset_path)

if __args.serve:
    xcube.util.plugin.init_plugins()
    __server = Server(
        framework=get_framework_class("tornado")(),
        config={}
    )
    __context = __server.ctx.get_api_ctx("datasets")
    for __name in __datasets:
        __dataset = (
            xr.open_zarr(__saved_datasets[__name])
            if __args.save and __args.from_saved
            else __datasets[__name]
        )
        __context.add_dataset(__dataset, __name, style="bar")
        LOGGER.info("Added " + __name)
    __server.start()
