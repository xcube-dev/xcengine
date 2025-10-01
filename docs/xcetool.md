# Running xcengine

## The `xcetool` command

The command-line interface to xcengine is the command `xcetool`, which
implements multiple subcommands and options for building and running
container images and Application Packages.

You can use the `--help` flag for any `xcetool` command or subcommand to get more
details on usage and available options.

### `xcetool image build`

This is the main `xcetool` subcommand: it builds a container image from a supplied
notebook and environment file. If given the `--eoap` argument, it also generates
a CWL file defining a corresponding application package.

### `xcetool image run`

This subcommand runs an xcengine container image. An image can also be run using the
`docker run` command, but `xcetool image run` provides some additional convenience
(e.g. easy configuration of the HTTP port).

### `xcetool make-script` 

This subcommand does not generate a container image, but a directory containing
the main contents that the image would have had: a script derived from the notebook
along with some supporting files. The `make-script` subcommand is mainly useful for
debugging.

## Publishing your container image

Once you have built your container image locally, you can push it to an online
registry. The tag is used to determine the registry and repository to which to
push the image. For example, if an image is tagged `quay.io/alice/helloworld:1.0`,
pushing it will attempt to upload the image to the repository `helloworld`
under the account `alice` on the registry `quay.io`.


## Deploying your Application Package

Once your container image has been pushed to a registry, the CWL file can be deployed
to a cloud platform to make your Application Package available to users of this
platform. The process for deploying the CWL file varies; consult the platform
documentation or support for details.

