#!/usr/bin/env python3

# Copyright (c) 2024 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.

import logging
import os
import pathlib
import subprocess
import tempfile

import click
import yaml

from .core import ScriptCreator, ImageBuilder, ContainerRunner


@click.group(
    help="Create and run compute engine scripts and containers "
    "from IPython notebooks"
)
@click.option("-v", "--verbose", count=True)
def cli(verbose):
    if verbose > 0:
        logging.getLogger().setLevel(logging.DEBUG)


batch_option = click.option(
    "-b", "--batch", is_flag=True, help="Run as batch script after creating"
)

server_option = click.option(
    "-s",
    "--server",
    is_flag=True,
    help="Run as xcube server script after creating",
)

output_option = click.option(
    "-o",
    "--output",
    type=click.Path(path_type=pathlib.Path, dir_okay=True, file_okay=False),
    help="Write output data to this directory, which will be created if it "
    "does not exist already.",
)

from_saved_option = click.option(
    "-f",
    "--from-saved",
    is_flag=True,
    help="If batch and server both used, serve datasets from saved Zarrs",
)

keep_option = click.option(
    "-k",
    "--keep",
    is_flag=True,
    help="Keep container after it has finished running.",
)

notebook_argument = click.argument(
    "notebook",
    type=click.Path(
        path_type=pathlib.Path, dir_okay=False, file_okay=True, exists=True
    ),
)


@cli.command(help="Create a compute engine script on the host system")
@batch_option
@server_option
@from_saved_option
@click.option(
    "-c",
    "--clear",
    is_flag=True,
    help="Clear output directory before writing to it",
)
@notebook_argument
@click.argument(
    "output_dir",
    type=click.Path(path_type=pathlib.Path, dir_okay=True, file_okay=False),
)
def make_script(
    batch: bool,
    server: bool,
    from_saved: bool,
    clear: bool,
    notebook: pathlib.Path,
    output_dir: pathlib.Path,
) -> None:
    script_creator = ScriptCreator(notebook)
    script_creator.convert_notebook_to_script(
        output_dir=output_dir, clear_output=clear
    )
    if batch or server:
        args = ["python3", output_dir / "execute.py"]
        if batch:
            args.append("--batch")
        if server:
            args.append("--server")
        if from_saved:
            args.append("--from-saved")
        subprocess.run(args)


@cli.group(name="image", help="Build and run compute engine container images")
def image_cli():
    pass


@image_cli.command(
    help="Build, and optionally run, a compute engine as a Docker image"
)
@batch_option
@server_option
@from_saved_option
@click.option(
    "-b",
    "--build-dir",
    type=click.Path(path_type=pathlib.Path, dir_okay=True, file_okay=False),
    help="Build directory to use for preparing the Docker image. If not "
    "specified, an automatically created temporary directory will be used.",
)
@keep_option
@click.option(
    "-e",
    "--environment",
    type=click.Path(path_type=pathlib.Path, dir_okay=False, file_okay=True),
    help="Conda environment file to use in Docker image. "
    "If not specified, try to reproduce the current environment.",
)
@output_option
@click.option(
    "-t",
    "--tag",
    type=str,
    default=None,
    help="Tag to apply to the Docker image. "
    "If not specified, a timestamp-based tag will be generated automatically",
)
@click.option(
    "-a",
    "--eoap",
    type=click.Path(path_type=pathlib.Path, writable=True),
    default=None,
    help="Write a CWL file defining an Earth Observation Application Package "
    "to the specified path",
)
@notebook_argument
def build(
    batch: bool,
    server: bool,
    from_saved: bool,
    keep: bool,
    build_dir: pathlib.Path,
    notebook: pathlib.Path,
    output: pathlib.Path,
    environment: pathlib.Path,
    tag: str,
    eoap: pathlib.Path,
) -> None:
    init_args = dict(
        notebook=notebook, output_dir=output, environment=environment, tag=tag
    )
    build_args = dict(
        run_batch=batch, run_server=server, from_saved=from_saved, keep=keep
    )
    if build_dir:
        image_builder = ImageBuilder(build_dir=build_dir, **init_args)
        os.makedirs(build_dir, exist_ok=True)
        image_builder.build(**build_args)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_builder = ImageBuilder(
                build_dir=pathlib.Path(temp_dir), **init_args
            )
            image_builder.build(**build_args)
    if eoap:
        eoap.write_text(yaml.dump(image_builder.create_cwl()))


@image_cli.command(help="Run a compute engine image as a Docker container")
@batch_option
@server_option
@from_saved_option
@output_option
@keep_option
@click.argument("image", type=str)
def run(
    batch: bool,
    server: bool,
    from_saved: bool,
    keep: bool,
    image: str,
    output: pathlib.Path,
) -> None:
    runner = ContainerRunner(image=image, output_dir=output)
    runner.run(
        run_batch=batch, run_server=server, from_saved=from_saved, keep=keep
    )


if __name__ == "__main__":
    cli()
