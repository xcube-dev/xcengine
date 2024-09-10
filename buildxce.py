#!/usr/bin/env python3

import tempfile
import subprocess
import argparse
import pathlib
import textwrap
from datetime import datetime

import yaml
import docker
import nbformat
from nbconvert import PythonExporter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=str)
    parser.add_argument(
        "--workdir",
        "-w",
        type=str,
        help="Use this as working directory (useful for debugging). "
        "If omitted, use an automatically created temporary directory.",
    )
    parser.add_argument(
        "--run",
        "-r",
        action="store_true",
        help="Run the image after building it",
    )
    args = parser.parse_args()
    if args.workdir:
        convert(args.workdir, args)
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            convert(temp_dir, args)


def convert(output_dir, args):
    output_path = pathlib.Path(output_dir)
    write_script(output_path, args.notebook)
    export_conda_env(output_path)
    image = build_image(output_path)
    if args.run:
        client = docker.from_env()
        client.containers.run(
            image=image,
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

    snippet = textwrap.dedent(
        """
    import xarray as xr
    import xcube
    from xcube.server.server import Server
    from xcube.server.framework import get_framework_class
    import xcube.util.plugin
    import xcube.core.new

    xcube.util.plugin.init_plugins()
    server = Server(
        framework=get_framework_class("tornado")(),
        config={}
    )
    context = server.ctx.get_api_ctx("datasets")

    for name, thing in locals().copy().items():
        if isinstance(thing, xr.Dataset) and not name.startswith("_"):
            context.add_dataset(thing, name, style="bar")

    server.start()
    """
    )
    with open(pathlib.Path(output_dir) / "serve.py", "w") as fh:
        fh.write(body)
        fh.write(snippet)


def export_conda_env(output_path: pathlib.Path):
    process = subprocess.run(["conda", "env", "export"], capture_output=True)
    with open(output_path / "environment.yml", "wb") as fh:
        fh.write(process.stdout)


def build_image(docker_path):
    client = docker.from_env()
    dockerfile = textwrap.dedent(
        """
    FROM quay.io/bcdev/xcube:v1.7.0
    COPY serve.py serve.py
    CMD python serve.py
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
    main()
