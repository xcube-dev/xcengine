# Testing and running Application Packages

Application Packages are generally deployed to cloud platforms, but there are
also ways to run CWL files and complete Application Packages locally.

## Understanding and debugging xcengine container images

When generating a container image, xcengine uses a
[micromamba](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html)
image as a base. If you need to investigate or
debug an xcengine image, or if you're just curious about its structure, you may
find the [micromamba-docker
documentation](https://micromamba-docker.readthedocs.io/) useful.

xcengine sets a custom entry point to run its own runner script, so any commands
provided when running a container from an xcengine image with `docker run`
will be applied as arguments to the xcengine runner. For instance, for an
image tagged `myimage:1`, the `--server` parameter can be used like this:

`docker run myimage:1 --server`

This would run the xcengine runner script with the `--server` option, which
starts an xcube server and viewer instance.

To explore or debug a container image, it's often useful to start a container
with an interactive shell. To do this with an xcengine image, it's not enough
to provide a path to a shell as a command, since this path will just be passed
as a parameter to the xcengine runner script. You need to set the entry point
as well, like this:

`docker --rm -it --entrypoint /usr/local/bin/_entrypoint.sh myimage:1 bash`

This resets the entry point to the usual micromamba-docker entry point, which
sets up the Python environment, then runs bash within that environment.

## Running with cwltool

[cwltool](https://www.commonwl.org/user_guide/introduction/quick-start.html)
is the reference runner for CWL files. It doesn't implement the full
Application Package best practice (so there is no stage-in / stage-out
functionality) but can nevertheless be used to run CWL files that implement
Application Packages.

## Running with ZOO-Project and the DRU extensions

For a fully functional, locally deployable Application Package platform you can
use the [ZOO-Project](https://zoo-project.org/) with the optional
[DRU extensions](https://zoo-project.github.io/docs/kernel/dru.html), running on
[minikube](https://minikube.sigs.k8s.io/docs/). The
[EOEPCA+ documentation](https://eoepca.readthedocs.io/projects/deploy/en/2.0-rc1/building-blocks/oapip-engine/)
gives detailed instructions for installation.

## Deploying your Application Package to a platform

Once your container image has been pushed to a registry, the CWL file can be
deployed to a cloud platform to make your Application Package available to
users of this platform. The process for deploying the CWL file varies; consult
the platform documentation or support for details.
