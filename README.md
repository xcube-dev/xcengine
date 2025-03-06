[![Unit tests](https://github.com/xcube-dev/xcengine/actions/workflows/tests.yaml/badge.svg)](https://github.com/xcube-dev/xcengine/actions/workflows/tests.yaml)
[![codecov](https://codecov.io/gh/xcube-dev/xcengine/graph/badge.svg?token=dTPaJB6nR3)](https://codecov.io/gh/xcube-dev/xcengine)

# xcengine: turn Jupyter notebooks into Application Packages

xcengine provides tools to convert a Jupyter notebook into one of several
parameterized, headlessly runnable forms:

-   A Python script
-   A Docker container image
-   An OGC [Earth Observation Application
    Package](https://docs.ogc.org/bp/20-089r1.html)

# Defining parameters in a notebook

xcengine uses the same convention as
[papermill](https://papermill.readthedocs.io/)
for defining parameters in a notebook. All parameters should be set as
Python variables in the same notebook code cell, and that cell should be
designated as the parameter cell by giving it the tag `parameters`. In
JupyterLab, you can do this using the property inspector (⚙⚙ icon in the
right sidebar). See the [papermill
documentation](https://papermill.readthedocs.io/en/latest/usage-parameterize.html#designate-parameters-for-a-cell)
for more details.

During conversion, `xcetool` will detect any variables that are set in the
parameters cell and make them available as command-line parameters for the
output script and container, and as workflow parameters for the application
package.

# xcetool usage

xcengine provides a command-line tool called `xcetool`, which has several
subcommands for different functions. Use the `--help` option with these
subcommands to get more details on usage.

## `xcetool make-script`

Convert a Jupyter notebook to a non-interactive Python script.

## `xcetool image build`

Convert a Jupyter notebook to a Docker container image. This subcommand can
additionally produce a Common Workflow Language (CWL) file defining an OGC
[Earth Observation Application Package](https://docs.ogc.org/bp/20-089r1.html) which uses the container image.

## `xcetool image run`

Run a Docker container using an image converted from a Jupyter notebook.
