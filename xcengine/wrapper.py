#!/usr/bin/env python3

# Copyright (c) 2024 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.


import logging
import pathlib
import parameters

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def __xce_set_params():
    params = parameters.NotebookParameters.from_yaml_file(
        pathlib.Path(sys.argv[0]).parent / "parameters.yaml"
    )
    globals().update(params.read_params_combined(sys.argv))


with pathlib.Path(__file__).with_name("user_code.py").resolve().open() as fh:
    user_code = fh.read()

exec(user_code)

import sys
import argparse
import pathlib

import xarray as xr
from xcube.server.server import Server
from xcube.server.framework import get_framework_class
import xcube.util.plugin
import xcube.core.new


def main():
    parser = argparse.ArgumentParser()

    # TODO: decide how to distinguish xcengine args from user code args
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--from-saved", action="store_true")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args, _ = parser.parse_known_args()
    if args.verbose > 0:
        LOGGER.setLevel(logging.DEBUG)

    xcube.util.plugin.init_plugins()
    datasets = {
        name: thing
        for name, thing in globals().copy().items()
        if isinstance(thing, xr.Dataset) and not name.startswith("_")
    }

    saved_datasets = {}

    if args.batch:
        parent_path = pathlib.Path(sys.argv[0]).parent
        output_path = pathlib.Path.home() / "output"
        output_path.mkdir(parents=True, exist_ok=True)
        for name, dataset in datasets.items():
            dataset_path = output_path / (name + ".zarr")
            saved_datasets[name] = dataset_path
            dataset.to_zarr(dataset_path)
        (parent_path / "finished").touch()

    if args.server:
        xcube.util.plugin.init_plugins()
        server = Server(framework=get_framework_class("tornado")(), config={})
        context = server.ctx.get_api_ctx("datasets")
        for name in datasets:
            dataset = (
                xr.open_zarr(saved_datasets[name])
                if args.batch and args.from_saved
                else datasets[name]
            )
            context.add_dataset(dataset, name, style="bar")
            LOGGER.info("Added " + name)
        LOGGER.info(f"Starting server on port {server.ctx.config['port']}...")
        server.start()


if __name__ == "__main__":
    main()
