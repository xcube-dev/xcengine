#!/usr/bin/env python3

# Copyright (c) 2024 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.

import json
import os
import shutil
import sys
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
from docker.errors import BuildError
from docker.models.containers import Container
import docker.models.images
import nbconvert
import nbformat
import yaml

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
    script_creator = ScriptCreator(output_dir, notebook)
    script_creator.convert_notebook_to_script(clear_output=clear)
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
    image_builder = ImageBuilder(
        notebook=notebook, output_dir=output, environment=environment
    )
    args = dict(
        batch=batch,
        server=server,
        from_saved=from_saved,
        keep=keep,
    )
    if workdir:
        os.makedirs(workdir, exist_ok=True)
        image_builder.build(work_dir=workdir, **args)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            image_builder.build(work_dir=pathlib.Path(temp_dir), **args)


class ScriptCreator:
    """Turn a Jupyter notebook into a set of scripts"""

    def __init__(self, output_dir: pathlib.Path, input_notebook: pathlib.Path):
        self.output_dir = output_dir
        self.input_notebook = input_notebook

    def convert_notebook_to_script(self, clear_output=False) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if clear_output:
            self.clear_output_directory()
        with open(self.input_notebook) as fh:
            notebook = nbformat.read(fh, as_version=4)
        self.insert_params_cell(notebook)
        exporter = nbconvert.PythonExporter()
        (body, resources) = exporter.from_notebook_node(notebook)
        with open(self.output_dir / "user_code.py", "w") as fh:
            fh.write(body)
        with open(pathlib.Path(__file__).parent / "wrapper.py", "r") as fh:
            wrapper = fh.read()
        with open(self.output_dir / "execute.py", "w") as fh:
            fh.write(wrapper)

    @staticmethod
    def insert_params_cell(notebook: nbformat.NotebookNode) -> None:
        params_cell_index = None
        for i, cell in enumerate(notebook.cells):
            if (
                hasattr(md := cell.metadata, "tags")
                and "parameters" in md.tags
            ):
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

    def clear_output_directory(self) -> None:
        for path in self.output_dir.iterdir():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


class ImageBuilder:
    """Builds docker images from notebooks and runs containers from them

    This class creates a docker image from a Jupyter notebook and optionally
    runs a container initialized from that image.
    """

    def __init__(
        self,
        notebook: pathlib.Path,
        output_dir: pathlib.Path,
        environment: pathlib.Path,
    ):
        self.notebook = notebook
        self.output_dir = output_dir
        self.environment = environment

    def build(
        self,
        work_dir: pathlib.Path,
        run_batch: bool,
        run_server: bool,
        from_saved: bool,
        keep: bool,
    ) -> None:
        script_creator = ScriptCreator(work_dir, self.notebook)
        script_creator.convert_notebook_to_script()
        if self.environment:
            shutil.copy2(self.environment, work_dir / "environment.yml")
        else:
            ImageBuilder.export_conda_env(work_dir)
        image = ImageBuilder.build_image(work_dir)
        if run_batch or run_server:
            client = docker.from_env()
            LOGGER.info(f"Running container from image {image.short_id}")
            LOGGER.info(f"Image tags: {' '.join(image.tags)}")
            command = (
                ["python", "execute.py"]
                + (["--batch"] if run_batch else [])
                + (["--server"] if run_server else [])
                + (["--from-saved"] if from_saved else [])
            )
            container: Container = client.containers.run(
                image=image,
                command=command,
                ports={"8080": 8080},
                remove=False,
                detach=True,
            )
            LOGGER.info(
                f"Waiting for container {container.short_id} to complete."
            )
            while container.status in {"created", "running"}:
                LOGGER.debug(
                    f"Waiting for {container.short_id} "
                    f"(status: {container.status})"
                )
                time.sleep(2)
                container.reload()
            LOGGER.info(
                f"Container {container.short_id} is {container.status}."
            )
            if self.output_dir:
                LOGGER.info(
                    f"Copying results from container to {self.output_dir}..."
                )
                extract_output_from_container(container, self.output_dir)
                LOGGER.info(f"Results copied.")
            if not run_server and not keep:
                LOGGER.info(f"Removing container {container.short_id}...")
                container.remove(force=True)
                LOGGER.info(f"Container {container.short_id} removed.")

    @staticmethod
    def export_conda_env(output_path: pathlib.Path) -> None:
        conda_process = subprocess.run(
            ["conda", "env", "export"], capture_output=True
        )
        env_def = yaml.safe_load(conda_process.stdout)
        # Try to remove any dependencies installed from the local filesystem,
        # which would break environment creation within the container. This
        # won't work if some of these packages are required for the compute
        # code, but it's in any case questionable to base a compute engine on
        # non-released code.
        deps: list = env_def["dependencies"]
        pip_index, pip_map = next(
            (
                d
                for d in enumerate(deps)
                if isinstance(d[1], Mapping) and "pip" in d[1]
            ),
            (None, None),
        )
        pip_inspect = PipInspector()
        if pip_map:
            nonlocals = []
            for pkg in pip_map["pip"]:
                if pip_inspect.is_local(pkg):
                    LOGGER.warning(
                        f'Omitting locally installed package "{pkg}" '
                        f"from environment"
                    )
                else:
                    nonlocals.append(pkg)
            if len(nonlocals) == 0:
                del deps[pip_index]
            else:
                pip_map["pip"] = nonlocals
        if not any(
            map(lambda d: isinstance(d, str) and d.startswith("xcube="), deps)
        ):
            # We need xcube for the server and viewer functionality
            deps.append("xcube")
        with open(output_path / "environment.yml", "w") as fh:
            fh.write(yaml.safe_dump(env_def))

    @staticmethod
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
        try:
            image, logs = client.images.build(
                path=str(docker_path),
                tag=f"xce2:{datetime.now().strftime('%Y.%m.%d.%H.%M.%S')}",
            )
        except BuildError as error:
            LOGGER.error(error.msg)
            for line in error.build_log:
                LOGGER.error(line)
            sys.exit(1)
        LOGGER.info("Docker image built.")
        return image


class PipInspector:
    """A simple wrapper around `pip inspect` output

    Provides a method to check whether a package was installed from the
    local filesystem.
    """

    def __init__(self):
        pip_process = subprocess.run(
            ["pip", "--no-color", "inspect"], capture_output=True
        )
        pip_packages = json.loads(pip_process.stdout)
        self.pkg_index: dict[str, dict] = {}
        for pkg_data in pip_packages["installed"]:
            self.pkg_index[name := pkg_data["metadata"]["name"]] = pkg_data

    def is_local(self, package_spec: str) -> bool:
        """Check if package was installed from local filesystem

        The heuristic used by this function is not guaranteed 100% accurate.

        :param package_spec: package name and optional version specifier, as
            output from "conda env export"
        :return: True iff the package was installed by pip from a local FS
        """

        package_name = package_spec.split("=")[0]
        # We also check the package name with "_"s replaced with "-",
        # since conda and pip package names often differ in this character.
        return self._is_local(package_name) or self._is_local(
            package_name.replace("_", "-")
        )

    def _is_local(self, package_name: str) -> bool:
        return (pkg_record := self.pkg_index.get(package_name, {})).get(
            "installer", ""
        ) == "pip" and pkg_record.get("direct_url", {"url": ""}).get(
            "url", ""
        ).startswith(
            "file://"
        )


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
