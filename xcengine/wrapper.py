with open("user_code.py", "r") as fh:
    user_code = fh.read()

exec(user_code)

import sys
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--from-saved", action="store_true")
    args = parser.parse_args()
    xcube.util.plugin.init_plugins()

    datasets = {name: thing for name, thing in globals().copy().items()
                  if isinstance(thing, xr.Dataset) and not name.startswith("_")}

    saved_datasets = {}

    if args.batch:
        parent_path = pathlib.Path(sys.argv[0]).parent
        output_path = parent_path / "output"
        output_path.mkdir(parents=True, exist_ok=True)
        for name, dataset in datasets.items():
            dataset_path = output_path / (name + ".zarr")
            saved_datasets[name] = dataset_path
            dataset.to_zarr(dataset_path)
        (parent_path / "finished").touch()

    if args.server:
        xcube.util.plugin.init_plugins()
        server = Server(
            framework=get_framework_class("tornado")(),
            config={}
        )
        context = server.ctx.get_api_ctx("datasets")
        for name in datasets:
            dataset = (
                xr.open_zarr(saved_datasets[name])
                if args.batch and args.from_saved
                else datasets[name]
            )
            context.add_dataset(dataset, name, style="bar")
            LOGGER.info("Added " + name)
        server.start()


if __name__ == "__main__":
    main()
