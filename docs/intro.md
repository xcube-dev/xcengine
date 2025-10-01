# Introduction

xcengine turns Python Jupyter notebooks into Earth Observation Application
Packages and Docker images bundling an xcube Server and Viewer.

## Jupyter notebooks

[Jupyter notebooks](https://jupyter.org/) provide a web-based interactive
development environment which integrates code, documentation, and
output visualization.

## Application packages

The *Earth Observation Application Package* is an increasingly popular
format for packaging and deploying EO software tools. It is defined in
a [Best Practice document](https://docs.ogc.org/bp/20-089r1.html)
published by the [Open Geospatial Consortium](https://www.ogc.org/).
An Application Package consists of two parts:

1. A [Docker container 
   image](https://docs.docker.com/get-started/docker-concepts/the-basics/what-is-an-image/)
   containing the processing code to be packaged.
2. A [Common Workflow Language](https://www.commonwl.org/) (CWL) file
   which defines how the code in the container image should be run,
   and what its available parameters, inputs, and outputs are.

Application Packages are designed to be run on cloud processing
platforms, but can also be tested locally. Application Packages provide
a great deal of power and flexibility; partly because of this flexibility, they
can be complex and challenging to build from scratch.

## xcube Server and Viewer

[xcube](https://xcube.readthedocs.io/) is a mature and powerful Python
framework for EO data processing and visualization. Amongst other features,
it includes an [API server](https://xcube.readthedocs.io/en/latest/webapi.html)
and [web viewer](https://xcube-dev.github.io/xcube-viewer/) which can
serve and visualize data from a wide variety of sources, both statically
stored and fetched or processed on demand.

## xcengine

xcengine takes Python Jupyter notebooks as input, and produces a Docker
image and a CWL file which encapsulate the code contained in the notebook.
Together these constitute an Application Package. The Docker image can also
be run in an interactive, stand-alone mode to start up an xcube API server
and web viewer, allowing the notebook's data to be exported via a variety
of standard interfaces or explored visually and interactively.
