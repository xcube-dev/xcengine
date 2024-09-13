#!/usr/bin/env python3

import os
import sys
import shutil
import tempfile
import subprocess
import logging
import pathlib
import textwrap
from datetime import datetime

import click
import docker
import nbformat
from nbconvert import PythonExporter

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@click.group(
    help="Create and run compute engine scripts and containers "
    "from IPython notebooks"
)
def cli():
    pass


@cli.command(help="Create a compute engine script on the host system")
@click.option(
    "-b", "--batch", is_flag=True, help="Run as batch script after creating"
)
@click.option(
    "-s",
    "--server",
    is_flag=True,
    help="Run as xcube server script after creating",
)
@click.option(
    "-f",
    "--from-saved",
    is_flag=True,
    help="If batch and server both used, serve datasets from saved Zarrs",
)
@click.option(
    "-c",
    "--clear",
    is_flag=True,
    help="Clear output directory before writing to it",
)
@click.argument("notebook", type=click.Path(), path_type=pathlib.Path)
@click.argument("output_dir", type=click.Path(), path_type=pathlib.Path)
def create(
    batch: bool,
    server: bool,
    from_saved: bool,
    clear: bool,
    notebook: pathlib.Path,
    output_dir: pathlib.Path,
) -> None:
    pathlib.Path.mkdir(output_dir, parents=True, exist_ok=True)
    if clear:
        clear_directory(output_dir)

    write_script(output_dir, notebook)
    if batch or server:
        args = ["python3", output_dir / "execute.py"]
        if batch:
            args.append("--batch")
        if server:
            args.append("--server")
        if from_saved:
            args.append("--from-saved")
        subprocess.run(args)


@cli.command(help="Build a compute engine as a Docker image")
@click.option(
    "-b", "--batch", is_flag=True, help="Run as batch script after creating"
)
@click.option(
    "-s",
    "--server",
    is_flag=True,
    help="Run as xcube server script after creating",
)
@click.option(
    "-f",
    "--from-saved",
    is_flag=True,
    help="If batch and server both used, serve datasets from saved Zarrs",
)
@click.option("-w", "--workdir", type=click.Path(), path_type=pathlib.Path)
@click.argument("notebook", type=click.Path(), path_type=pathlib.Path)
def build(
    batch: bool, server: bool, from_saved: bool, workdir, notebook
) -> None:
    # TODO allow export of saved results from container
    if workdir:
        convert(workdir, notebook, batch, server, from_saved)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            convert(
                pathlib.Path(temp_dir), notebook, batch, server, from_saved
            )


def convert(
    output_dir: pathlib.Path,
    notebook: pathlib.Path,
    batch: bool,
    server: bool,
    from_saved: bool,
) -> None:
    write_script(output_dir, notebook)
    export_conda_env(output_dir)
    image = build_image(output_dir)
    if batch or server:
        client = docker.from_env()
        LOGGER.info(f"Running {image.tags}")
        command = (
            ["python", "execute.py"]
            + (["--batch"] if batch else [])
            + (["--server"] if server else [])
            + (["--from-saved"] if from_saved else [])
        )
        client.containers.run(
            image=image,
            command=command,
            ports={8080: 8080},
            remove=True,
            # auto_remove=True,
            detach=False,
        )


def write_script(output_dir: pathlib.Path, input_notebook: pathlib.Path):
    with open(input_notebook) as fh:
        notebook = nbformat.read(fh, as_version=4)

    exporter = PythonExporter()
    (body, resources) = exporter.from_notebook_node(notebook)
    with open("user_code.py", "w") as fh:
        fh.write(body)

    with open(pathlib.Path(sys.argv[0]).parent / "wrapper.py", "r") as fh:
        wrapper = fh.read()

    output_path = pathlib.Path(output_dir)
    with open(output_path / "execute.py", "w") as fh:
        fh.write(body)
        fh.write(wrapper)


def export_conda_env(output_path: pathlib.Path):
    process = subprocess.run(["conda", "env", "export"], capture_output=True)
    with open(output_path / "environment.yml", "wb") as fh:
        fh.write(process.stdout)


def build_image(docker_path: pathlib.Path):
    client = docker.from_env()
    dockerfile = textwrap.dedent(
        """
    FROM quay.io/bcdev/xcube:v1.7.0
    COPY execute.py execute.py
    CMD python execute.py
    """
    )
    with open(docker_path / "Dockerfile", "w") as fh:
        fh.write(dockerfile)
    image, logs = client.images.build(
        path=str(docker_path),
        tag=f"xce2:{datetime.now().strftime('%Y.%m.%d.%H.%M.%S')}",
    )
    return image


def clear_directory(path: pathlib.Path) -> None:
    for path in path.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            os.remove(path)


if __name__ == "__main__":
    cli()
