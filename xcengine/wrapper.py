#!/usr/bin/env python3

# Copyright (c) 2024-2026 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.


import logging
import os
import pathlib
import sys
import util

print("CWD", os.getcwd())

import parameters

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def __xce_set_params(config_locator: str | pathlib.Path = sys.argv[0]):
    params = parameters.NotebookParameters.from_yaml_file(
        pathlib.Path(config_locator).parent / "parameters.yaml"
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
        util.start_server(datasets, saved_datasets, args, LOGGER)


if __name__ == "__main__":
    main()
