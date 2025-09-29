# Running `xcetool`

xcengine provides a command `xcetool` which converts a Jupyter Python notebook
to a compute engine. A compute engine consists of:

- A docker container image packaging the notebook code, a Python environment,
  and an [xcube](https://xcube.readthedocs.io/) server component, letting
  the notebook results be served over multiple supported APIs and explored
  in the interactive xcube viewer.
- An accompanying CWL file defining an OGC
  [Earth Observation Application Package](docs.ogc.org/bp/20-089r1.html) using
  the container image. This lets your notebook code run as part of a processing
  workflow on any EOAP platform.

In the conversion process, xcengine tries to maximize convenience for the user
by requiring as little extra configuration and input as possible. Input
variables and their types can be defined by tagging a notebook cell
(similarly to [papermill](https://papermill.readthedocs.io/)), and output
datasets are automatically extracted from the notebook’s environment.
Some user configuration is unavoidable, but xcengine automates much of the
boilerplate required to create an EOAP.
