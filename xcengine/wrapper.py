#!/usr/bin/env python3

# Copyright (c) 2024-2025 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.


import json
import logging
import os
import pathlib
import sys
import util


print("CWD", os.getcwd())

import parameters

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def __xce_set_params():
    params = parameters.NotebookParameters.from_yaml_file(
        pathlib.Path(sys.argv[0]).parent / "parameters.yaml"
    )
    globals().update(params.read_params_combined(sys.argv))


if "XC_USER_CODE_PATH" in os.environ:
    __user_code_path = pathlib.Path(os.environ["XC_USER_CODE_PATH"])
else:
    __user_code_path = (
        pathlib.Path(__file__).with_name("user_code.py").resolve()
    )
with __user_code_path.open() as fh:
    user_code = fh.read()

exec(user_code)

import argparse
import pathlib

import xarray as xr
from xcube.server.server import Server
from xcube.server.framework import get_framework_class
import xcube.util.plugin
import xcube.core.new
import xcube.webapi.viewer


def main():
    parser = argparse.ArgumentParser()

    # TODO: decide how to distinguish xcengine args from user code args
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--from-saved", action="store_true")
    parser.add_argument("--eoap", action="store_true")
    parser.add_argument(
        "--xcube-viewer-api-url", type=str, default="http://localhost:8080"
    )
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
        saved_datasets = util.save_datasets(
            datasets, pathlib.Path.cwd(), args.eoap
        )

    if args.server:
        xcube.util.plugin.init_plugins()
        server = Server(framework=get_framework_class("tornado")(), config={})
        dataset_context = server.ctx.get_api_ctx("datasets")
        for name in datasets:
            dataset = (
                xr.open_zarr(saved_datasets[name])
                if args.batch and args.from_saved
                else datasets[name]
            )
            dataset_context.add_dataset(dataset, name, style="bar")
            LOGGER.info("Added " + name)
        logo_data = (
            pathlib.Path(xcube.webapi.viewer.__file__).parent
            / "dist"
            / "images"
            / "logo.png"
        ).read_bytes()

        viewer_context = server.ctx.get_api_ctx("viewer")
        viewer_context.config_items = {
            "config.json": json.dumps(
                {
                    "server": {"url": args.xcube_viewer_api_url},
                    "branding": {
                        # "layerVisibilities": {
                        #     # Set the default basemap.
                        #     "baseMaps.CartoDB.Dark Matter": True
                        # }
                    },
                }
            ),
            "images/logo.png": logo_data,
        }
        LOGGER.info(f"Starting server on port {server.ctx.config['port']}...")
        server.start()


if __name__ == "__main__":
    main()
