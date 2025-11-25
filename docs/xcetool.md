# Running xcengine

## The `xcetool` command

The command-line interface to xcengine is the command `xcetool`, which
implements multiple subcommands and options for building and running
container images and Application Packages.

You can use the `--help` flag for any `xcetool` command or subcommand to get more
details on usage and available options.

### `xcetool image build`

Usage: `xcetool image build [OPTIONS] NOTEBOOK`

This is the main `xcetool` subcommand: it builds a container image from a supplied
notebook and environment file. If given the `--eoap` argument, it also generates
a CWL file defining a corresponding application package.

Options:

-   `-b`, `--build-dir` `DIRECTORY`: Build directory to use for preparing the
    Docker image. If not specified, an automatically created temporary
    directory will be used.
    This option is mainly useful for debugging.
-   `-e`, `--environment` `FILE`:
    Conda environment file to use in Docker image.
    If no environment file is specified here or in the notebook,
    xcetool will try to reproduce the current environment
    as a last resort, but this is not recommended.
-   `-t`, `--tag` `TEXT`: Tag to apply to the Docker image.
    If not specified, a
    timestamp-based tag will be generated automatically.
-   `-a`, `--eoap` `PATH`: Write a CWL file defining an Earth Observation
    Application Package to the specified path.
-   `--help`: Show a help message for this subcommand and exit.

### `xcetool image run`

Usage: `xcetool image run [OPTIONS] IMAGE`

Options:

-   `-b`, `--batch`: Run the compute engine as a batch script.
    Use with the `--output` option to copy output
    out of the container.
-   `-s`, `--server`: Run the compute engine as an xcube server.
-   `-p`, `--port` INTEGER: Host port for xcube server (default: 8080).
    Implies `--server`.
-   `-f`, `--from-saved`: If `--batch` and `--server` both used, serve
    datasets from saved Zarrs rather than
    computing them on the fly.
-   `-o`, `--output` DIRECTORY  Write any output data to this directory,
    which will be created if it does not exist
    already.
-   `-k`, `--keep`: Keep container after it has finished
    running.
-   `--help`: Show a help message for this subcommand and exit.

This subcommand runs an xcengine container image. An image can also be run
using the `docker run` command, but `xcetool image run` provides some
additional convenience (e.g. easy configuration of a server HTTP port).

If you use the `--server` option with `xcetool image run`, the image will be
run in xcube server mode: after the code from the input notebook is used to
generate datasets, those datasets will be made available in an xcube server
instance. You can also use the `--port` option to select the HTTP port where
the xcube server should be exposed. The server also includes an interactive
web viewer component. On start-up, `xcetool` will print the URLs of the xcube
server and viewer to the standard output.

If you give the `--server` or `--port` options, `xcetool` will run the
container indefinitely as an xcube server and viewer instance. You can stop
the container and force `xcetool` to exit by pressing ctrl-C on the command
line (or by sending it an interrupt signal in some other way).

### `xcetool make-script` 

This subcommand does not generate a container image, but a directory
containing the main contents that the image would have had: a script derived
from the notebook along with some supporting files. The `make-script`
subcommand is mainly useful for debugging.

Usage: `xcetool make-script [OPTIONS] NOTEBOOK OUTPUT_DIR`

Create a compute engine script on the host system. The output directory will
be used for the generated script, supporting code modules, and any output
produced by running the script.

Options:

-   `-b`, `--batch`: Run as batch script after creating
-   `-s`, `--server`: Run the script as an xcube server after creating it.
-   `-f`, `--from-saved`: If `--batch` and `--server` both used, serve datasets from saved Zarrs rather than computing them on the fly.
-   `-c`, `--clear`: Clear output directory before writing to it
-   `--help`: Show a help message for this subcommand and exit.

## Publishing your container image

Once you have built your container image locally, you can push it to an online
registry. The tag is used to determine the registry and repository to which to
push the image. For example, if an image is tagged `quay.io/alice/helloworld:1.0`,
pushing it will attempt to upload the image to the repository `helloworld`
under the account `alice` on the registry `quay.io`. See the [Docker
documentation](https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-a-registry/)
for more details.

