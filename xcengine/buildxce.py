#!/usr/bin/env python3

# Copyright (c) 2024 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.

import os
import shutil
import tarfile
import tempfile
import subprocess
import logging
import pathlib
import textwrap
import time
import uuid
from datetime import datetime
from collections.abc import Mapping

import click
import docker
import docker.models.images
import nbformat
import yaml
from docker.models.containers import Container
from nbconvert import PythonExporter

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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

from_saved_option = click.option(
    "-f",
    "--from-saved",
    is_flag=True,
    help="If batch and server both used, serve datasets from saved Zarrs",
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

    convert_notebook_to_script(output_dir, notebook)
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
@batch_option
@server_option
@from_saved_option
@click.option(
    "-w",
    "--workdir",
    type=click.Path(path_type=pathlib.Path, dir_okay=True, file_okay=False),
    help="Working directory to use for preparing the Docker image. If not "
    "specified, an automatically created temporary directory will be used.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=pathlib.Path, dir_okay=True, file_okay=False),
    help="Write output data to this directory.",
)
@click.option(
    "-k",
    "--keep",
    is_flag=True,
    help="Keep container after it has finished running.",
)
@click.option(
    "-e",
    "--environment",
    type=click.Path(path_type=pathlib.Path, dir_okay=False, file_okay=True),
    help="Conda environment file to use in docker image. "
    "If not specified, use the current environment.",
)
@notebook_argument
def build(
    batch: bool,
    server: bool,
    from_saved: bool,
    keep: bool,
    workdir: pathlib.Path,
    notebook: pathlib.Path,
    output: pathlib.Path,
    environment: pathlib.Path,
) -> None:
    args = dict(
        notebook=notebook,
        output_dir=output,
        batch=batch,
        server=server,
        from_saved=from_saved,
        keep=keep,
        environment=environment,
    )
    if workdir:
        os.makedirs(workdir, exist_ok=True)
        _build(work_dir=workdir, **args)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            _build(work_dir=pathlib.Path(temp_dir), **args)


def _build(
    work_dir: pathlib.Path,
    notebook: pathlib.Path,
    output_dir: pathlib.Path,
    batch: bool,
    server: bool,
    from_saved: bool,
    keep: bool,
    environment: pathlib.Path,
) -> None:
    convert_notebook_to_script(work_dir, notebook)
    if environment:
        shutil.copy2()
    else:
        export_conda_env(work_dir)
    image = build_image(work_dir)
    if batch or server:
        client = docker.from_env()
        LOGGER.info(f"Running container from image {image.short_id}")
        LOGGER.info(f"Image tags: {' '.join(image.tags)}")
        command = (
            ["python", "execute.py"]
            + (["--batch"] if batch else [])
            + (["--server"] if server else [])
            + (["--from-saved"] if from_saved else [])
        )
        container: Container = client.containers.run(
            image=image,
            command=command,
            ports={8080: 8080},
            remove=False,
            detach=True,
        )
        LOGGER.info(f"Waiting for container {container.short_id} to complete.")
        while container.status in {"created", "running"}:
            LOGGER.debug(
                f"Waiting for {container.short_id} (status: {container.status})"
            )
            time.sleep(2)
            container.reload()
        LOGGER.info(f"Container {container.short_id} is {container.status}.")
        if output_dir:
            LOGGER.info(f"Copying results from container to {output_dir}...")
            extract_output_from_container(container, output_dir)
            LOGGER.info(f"Results copied.")
        if not server and not keep:
            LOGGER.info(f"Removing container {container.short_id}...")
            container.remove(force=True)
            LOGGER.info(f"Container {container.short_id} removed.")


def convert_notebook_to_script(
    output_dir: pathlib.Path, input_notebook: pathlib.Path
) -> None:
    with open(input_notebook) as fh:
        notebook = nbformat.read(fh, as_version=4)
    insert_params_cell(notebook)
    exporter = PythonExporter()
    (body, resources) = exporter.from_notebook_node(notebook)
    with open(output_dir / "user_code.py", "w") as fh:
        fh.write(body)
    with open(pathlib.Path(__file__).parent / "wrapper.py", "r") as fh:
        wrapper = fh.read()
    with open(output_dir / "execute.py", "w") as fh:
        fh.write(wrapper)


def insert_params_cell(notebook: nbformat.NotebookNode) -> None:
    params_cell_index = None
    for i, cell in enumerate(notebook.cells):
        if hasattr(md := cell.metadata, "tags") and "parameters" in md.tags:
            params_cell_index = i
            break
    if params_cell_index is not None:
        notebook.cells.insert(
            params_cell_index + 1,
            {
                "cell_type": "code",
                "execution_count": 0,
                "id": str(uuid.uuid4()),
                "metadata": {},
                "outputs": [],
                "source": "__xce_set_params()",
            },
        )


def export_conda_env(output_path: pathlib.Path) -> None:
    process = subprocess.run(["conda", "env", "export"], capture_output=True)
    env_def = yaml.safe_load(process.stdout)
    # TODO: improve handling of pip dependencies
    # Find any pip dependencies and remove them (for now). This is a
    # crude way to remove any non-PyPI dependencies installed from the local
    # filesystem, which would break environment creation within the container.
    # However, this risks removing required packages. Reproducing a live
    # environment exactly is a hard problem but we could do better here.
    deps: list = env_def["dependencies"]
    pips = next(
        (
            d
            for d in enumerate(deps)
            if isinstance(d[1], Mapping) and "pip" in d[1]
        ),
        None,
    )
    if pips:
        LOGGER.warning("Environment contains pip dependencies:")
        for pkg in pips[1]["pip"]:
            LOGGER.warning(pkg)
        LOGGER.warning("These will be omitted from the container.")
        del deps[pips[0]]
    if not any(d for d in deps if d.startswith("xcube=")):
        deps.append("xcube")
    with open(output_path / "environment.yml", "w") as fh:
        fh.write(yaml.safe_dump(env_def))


def build_image(docker_path: pathlib.Path) -> docker.models.images.Image:
    client = docker.from_env()
    dockerfile = textwrap.dedent(
        """
    FROM mambaorg/micromamba:1.5.10-noble-cuda-12.6.0
    COPY environment.yml environment.yml
    RUN micromamba install -y -n base -f environment.yml && \
    micromamba clean --all --yes
    COPY user_code.py user_code.py
    COPY execute.py execute.py
    CMD python execute.py
    """
    )
    with open(docker_path / "Dockerfile", "w") as fh:
        fh.write(dockerfile)
    LOGGER.info("Building Docker image...")
    image, logs = client.images.build(
        path=str(docker_path),
        tag=f"xce2:{datetime.now().strftime('%Y.%m.%d.%H.%M.%S')}",
    )
    LOGGER.info("Docker image built...")
    return image


def clear_directory(path: pathlib.Path) -> None:
    for path in path.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            os.remove(path)


def _tar_strip(member, path):
    member_1 = tarfile.data_filter(member, path)
    member_2 = member.replace(
        name=pathlib.Path(*pathlib.Path(member_1.path).parts[1:])
    )
    return member_2


def extract_output_from_container(
    container: Container, dest_dir: pathlib.Path
) -> None:
    bits, stat = container.get_archive("/home/xcube/output")
    with tempfile.NamedTemporaryFile(suffix=".tar") as temp_tar:
        # TODO stream this directly to tarfile rather than using a temp file
        with open(temp_tar.name, "wb") as fh:
            for chunk in bits:
                fh.write(chunk)
        with tarfile.open(temp_tar.name, "r") as tar_fh:
            tar_fh.extractall(dest_dir, filter=_tar_strip)


if __name__ == "__main__":
    cli()
