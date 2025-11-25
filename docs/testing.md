# Testing and running Application Packages

Application Packages are generally deployed to cloud platforms, but there are
also ways to run CWL files and complete Application Packages locally.

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
