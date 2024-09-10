#!/usr/bin/env python3
import sys
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

# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument("notebook", type=str)
#     parser.add_argument(
#         "--workdir",
#         "-w",
#         type=str,
#         help="Use this as working directory (useful for debugging). "
#         "If omitted, use an automatically created temporary directory.",
#     )
#     parser.add_argument(
#         "--run",
#         "-r",
#         action="store_true",
#         help="Run the image after building it",
#     )
#     args = parser.parse_args()
#     if args.workdir:
#         convert(args.workdir, args)
#     else:
#         with tempfile.TemporaryDirectory() as temp_dir:
#             convert(temp_dir, args)

@click.group()
def cli():
    pass

@cli.command(help="Create a compute engine script on the host system")
@click.option(
    "-b",
    "--batch",
    is_flag=True,
    help="Run as batch script after creating")
@click.option(
    "-s",
    "--server",
    is_flag=True,
    help="Run as xcube server script after creating")
@click.option(
    "-f",
    "--from-saved",
    is_flag=True,
    help="If batch and server both used, serve datasets from saved Zarrs")
@click.argument(
    "notebook",
    type=click.Path()
)
@click.argument(
    "output_dir",
    type=click.Path()
)
def create(batch, server, from_saved, notebook, output_dir):
    output_path = pathlib.Path(output_dir)
    pathlib.Path.mkdir(output_path, parents=True, exist_ok=True)
    write_script(output_path, notebook)
    if batch or server:
        args = ["python3", output_path / "execute.py"]
        if batch:
            args.append("--save")
        if server:
            args.append("--serve")
        if from_saved:
            args.append("--from-saved")
        subprocess.run(args)


@cli.command(help="Build a compute engine as a Docker image")
@click.option(
    "-b",
    "--batch",
    is_flag=True,
    help="Run as batch script after creating")
@click.option(
    "-s",
    "--server",
    is_flag=True,
    help="Run as xcube server script after creating")
@click.option(
    "-f",
    "--from-saved",
    is_flag=True,
    help="If batch and server both used, serve datasets from saved Zarrs")
@click.option(
    "-w",
    "--workdir",
    type=str
)
@click.argument(
    "notebook",
    type=click.Path()
)
def build(batch, server, from_saved, workdir, notebook):
    # TODO allow export of saved results from container
    if workdir:
        convert(workdir, notebook, batch or server)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            convert(temp_dir, notebook, batch or server)


def convert(output_dir, notebook, run):
    output_path = pathlib.Path(output_dir)
    write_script(output_path, notebook)
    export_conda_env(output_path)
    image = build_image(output_path)
    if run:
        client = docker.from_env()
        LOGGER.info(f"Running {image.tags}")
        command = ["python", "execute.py"]
        if run:
            # TODO better mapping of CLI arguments
            command += ["--save", "--serve", "--from-saved"]
        client.containers.run(
            image=image,
            command=command,
            ports={8080: 8080},
            remove=True,
            #            auto_remove=True,
            detach=False,
        )


def write_script(output_dir, input_notebook):
    with open(input_notebook) as fh:
        notebook = nbformat.read(fh, as_version=4)

    exporter = PythonExporter()
    (body, resources) = exporter.from_notebook_node(notebook)

    with open(pathlib.Path(sys.argv[0]).parent / "wrapper.py", "r") as fh:
        wrapper = fh.read()

    with open(pathlib.Path(output_dir) / "execute.py", "w") as fh:
        fh.write(body)
        fh.write(wrapper)


def export_conda_env(output_path: pathlib.Path):
    process = subprocess.run(["conda", "env", "export"], capture_output=True)
    with open(output_path / "environment.yml", "wb") as fh:
        fh.write(process.stdout)


def build_image(docker_path):
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

if __name__ == "__main__":
     cli()
