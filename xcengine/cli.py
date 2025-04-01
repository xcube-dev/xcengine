#!/usr/bin/env python3

# Copyright (c) 2024-2025 by Brockmann Consult GmbH
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


from_saved_option = click.option(
    "-f",
    "--from-saved",
    is_flag=True,
    help="If --batch and --server both used, serve datasets from saved Zarrs "
         "rather than computing them on the fly.",
)

notebook_argument = click.argument(
    "notebook",
    type=click.Path(
        path_type=pathlib.Path, dir_okay=False, file_okay=True, exists=True
    ),
)


@cli.command(
    help="Create a compute engine script on the host system. "
    "The output directory will be used for the generated "
    "script, supporting code modules, and any output "
    "produced by running the script."
)
@click.option(
    "-b", "--batch", is_flag=True, help="Run as batch script after creating"
)
@click.option(
    "-s",
    "--server",
    is_flag=True,
    help="Run the script as an xcube server after creating it.",
)
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
@click.option(
    "-b",
    "--build-dir",
    type=click.Path(path_type=pathlib.Path, dir_okay=True, file_okay=False),
    help="Build directory to use for preparing the Docker image. If not "
    "specified, an automatically created temporary directory will be used.",
)
@click.option(
    "-e",
    "--environment",
    type=click.Path(path_type=pathlib.Path, dir_okay=False, file_okay=True),
    help="Conda environment file to use in Docker image. "
    "If not specified, try to reproduce the current environment.",
)
@click.option(
    "-t",
    "--tag",
    type=str,
    default=None,
    help="Tag to apply to the Docker image. "
    "If not specified, a timestamp-based tag will be generated automatically.",
)
@click.option(
    "-a",
    "--eoap",
    type=click.Path(path_type=pathlib.Path, writable=True),
    default=None,
    help="Write a CWL file defining an Earth Observation Application Package "
    "to the specified path.",
)
@notebook_argument
def build(
    build_dir: pathlib.Path,
    notebook: pathlib.Path,
    environment: pathlib.Path,
    tag: str,
    eoap: pathlib.Path,
) -> None:
    init_args = dict(notebook=notebook, environment=environment, tag=tag)
    if build_dir:
        image_builder = ImageBuilder(build_dir=build_dir, **init_args)
        os.makedirs(build_dir, exist_ok=True)
        image = image_builder.build()
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_builder = ImageBuilder(
                build_dir=pathlib.Path(temp_dir), **init_args
            )
            image = image_builder.build()
    if eoap:
        eoap.write_text(yaml.dump(image_builder.create_cwl()))
    print(f"Built image with tags {image.tags}")


@image_cli.command(help="Run a compute engine image as a Docker container.")
@click.option(
    "-b",
    "--batch",
    is_flag=True,
    help="Run the compute engine as a batch script. Use with the --output "
         "option to copy output out of the container.",
)
@click.option(
    "-s",
    "--server",
    is_flag=True,
    help="Run the compute engine as an xcube server.",
)
@click.option(
    "-p",
    "--port",
    is_flag=False,
    type=int,
    default=8080,
    help="Host port for xcube server (default: 8080). Implies --server.",
)
@from_saved_option
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=pathlib.Path, dir_okay=True, file_okay=False),
    help="Write any output data to this directory, which will be created if it "
    "does not exist already.",
)
@click.option(
    "-k",
    "--keep",
    is_flag=True,
    help="Keep container after it has finished running.",
)
@click.argument("image", type=str)
@click.pass_context
def run(
    ctx: click.Context,
    batch: bool,
    server: False,
    port: int,
    from_saved: bool,
    keep: bool,
    image: str,
    output: pathlib.Path,
) -> None:
    runner = ContainerRunner(image=image, output_dir=output)
    port_specified_explicitly = (
        ctx.get_parameter_source("port")
        is not click.core.ParameterSource.DEFAULT
    )
    actual_port = port if server or port_specified_explicitly else None
    runner.run(
        run_batch=batch,
        host_port=actual_port,
        from_saved=from_saved,
        keep=keep,
    )


if __name__ == "__main__":
    cli()
