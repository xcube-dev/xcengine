#!/usr/bin/env python3

# Copyright (c) 2024 by Brockmann Consult GmbH
# Permissions are hereby granted under the terms of the MIT License:
# https://opensource.org/licenses/MIT.

import json
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

import docker
from docker.errors import BuildError
from docker.models.containers import Container
import docker.models.images
import nbconvert
import nbformat
import yaml
from docker.models.images import Image

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
            LOGGER.warning(
                f"No environment file given; "
                f"trying to reproduce current environment in Docker image"
            )
            ImageBuilder.export_conda_env(work_dir)
        image: Image = ImageBuilder.build_image(work_dir)
        if run_batch or run_server:
            runner = ContainerRunner(image, self.output_dir)
            runner.run(run_batch, run_server, from_saved, keep)

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


class ContainerRunner:

    def __init__(
        self,
        image: Image | str,
        output_dir: pathlib.Path,
        client: docker.DockerClient = None,
    ):
        self._client = client
        match image:
            case Image():
                self.image = image
            case str():
                self.image = self.client.images.get(image)
            case _:
                raise ValueError(
                    f'Invalid type "{type(image).__name__}" for image'
                )
        self.output_dir = output_dir

    @property
    def client(self):
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def run(
        self, run_batch: bool, run_server: bool, from_saved: bool, keep: bool
    ):
        LOGGER.info(f"Running container from image {self.image.short_id}")
        LOGGER.info(f"Image tags: {' '.join(self.image.tags)}")
        command = (
            ["python", "execute.py"]
            + (["--batch"] if run_batch else [])
            + (["--server"] if run_server else [])
            + (["--from-saved"] if from_saved else [])
        )
        container: Container = self.client.containers.run(
            image=self.image,
            command=command,
            ports={"8080": 8080},
            remove=False,
            detach=True,
        )
        LOGGER.info(f"Waiting for container {container.short_id} to complete.")
        while container.status in {"created", "running"}:
            LOGGER.debug(
                f"Waiting for {container.short_id} "
                f"(status: {container.status})"
            )
            time.sleep(2)
            container.reload()
        LOGGER.info(f"Container {container.short_id} is {container.status}.")
        if self.output_dir:
            LOGGER.info(
                f"Copying results from container to {self.output_dir}..."
            )
            self.extract_output_from_container(container)
            LOGGER.info(f"Results copied.")
        if not run_server and not keep:
            LOGGER.info(f"Removing container {container.short_id}...")
            container.remove(force=True)
            LOGGER.info(f"Container {container.short_id} removed.")

    @staticmethod
    def _tar_strip(member, path):
        member_1 = tarfile.data_filter(member, path)
        member_2 = member.replace(
            name=pathlib.Path(*pathlib.Path(member_1.path).parts[1:])
        )
        return member_2

    def extract_output_from_container(self, container: Container) -> None:
        bits, stat = container.get_archive("/home/xcube/output")
        with tempfile.NamedTemporaryFile(suffix=".tar") as temp_tar:
            # TODO stream this directly to tarfile rather than using temp file
            with open(temp_tar.name, "wb") as fh:
                for chunk in bits:
                    fh.write(chunk)
            with tarfile.open(temp_tar.name, "r") as tar_fh:
                tar_fh.extractall(self.output_dir, filter=self._tar_strip)


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
            self.pkg_index[pkg_data["metadata"]["name"]] = pkg_data

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
