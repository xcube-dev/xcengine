# Making a Jupyter notebook xcengine-compatible

xcengine is designed to require as little alteration as possible to a Python
notebook, but some configuration may be necessary, in particular to define
input parameters.

## Configuring input parameters

An Application Package can have, and usually does have, *input parameters*
defined types and default values, which can be set by the caller when running
the package. xcengine automatically generates these parameters from variables
in the notebook. Any variable to be used as a parameter must be defined
in the **parameters cell** of the notebook. You can only have one parameters
cell in a notebook, and it is strongly advised that the parameters cell appear
**as early as possible** in the notebook.

You turn a normal code cell into a parameters cell by adding a tag called
**parameters** to it in Jupyter Lab using the Property Inspector. (The Property
Inspector can be opened by clicking the gear icon at the top right of the Jupyter
Lab window.)

⚠️ Whenever possible, it's advisable to make the parameters cell the **very
first code cell** in the notebook, even before package imports. (xcengine reads
parameters by actually executing the notebook code up to the parameters cell,
so any packages imported before or within it must be available in the Python
environment where xcengine is running! Putting the parameters cell first
avoids this complication.)

![Property inspector](images/property-inspector.png)

You can define as many parameters as you like in the property cell. The
values you assign to them will be used as the default values for these
parameters when xcengine generates the Application Package.

This tagging convention is similar to the one used by [papermill](https://papermill.readthedocs.io/).

## Configuring xcengine

As well as parameters, the parameters cell can contain an **xcengine
configuration dictionary**. This is a Python dictionary with the special
name `xcengine_config`. Available configuration settings are:

-   `workflow_id`: a string identifier for the workflow in your Application
    Package. The runner or Application Package platform can use this
    identifier to refer to your Application Package. By default, the name
    of the notebook (without the `.ipynb` suffix) is used.
-   `environment_file`: the name of a YAML file defining a [conda
    environment](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)
    (these are often called `environment.yml`). If an environment file is not
    specified in the notebook or on the command line, xcetool will try to
    deduce the environment automatically. This cannot be done 100% reliably,
    so it is **strongly recommended** to provide an environment file.
-   `container_image_tag`: the tag applied to the Docker container image that
    xcengine builds. If you plan to push the image to a public registry,
    you can enter the final registry tag here and push the image once it's
    been built by xcengine. If no tag is specified, xcengine will create one
    based on the current date and time.
-   `build_includes`: a list of strings defining paths to local Python
    packages. These packages will be installed into the Docker container
    image's Python environment. See *Installing local Python packages in the
    container's Python environment* below for more details.
-   `include_directory`: include the whole of the notebook's parent directory
    in the built image. See *Including local data and Python modules when*
    *building an image* below for more details.

Some of these configuration settings can also be set on the command line.

## Dataset input

As well as the usual methods of dataset input, xcengine provides support for
the Application Package ‘stage-in’ process described in the [OGC Best
Practice document](https://docs.ogc.org/bp/20-089r1.html), in which an
Application Package Platform provides the Application Package with a
[STAC catalogue](https://stacspec.org/) of one or more input datasets.

xcengine currently provides basic support for stage-in: in a generated
Application Package, the xcengine support code provides the notebook code with
the path to the STAC stage-in catalogue. The notebook code can then read this
catalogue (e.g. using [PySTAC](https://pystac.readthedocs.io/)) to find the
staged-in datasets.

An input variable for a STAC stage-in catalogue can be defined in the
parameters cell (see above) as a string variable. The variable name can be
freely chosen, but the variable declaration must be annotated with the string
`"EOInput"` to distinguish it from an ordinary string parameter, like this:

```python
dataset_inputs: "EOInput" = "/some/default/path"
```

When the converted notebook is run as an Application Package, the variable
`dataset_inputs` will be set to a string specifying a filesystem path
containing a STAC catalogue called `catalog.json`, which the notebook code
can use to find staged-in datasets.

## Dataset output

### Selecting datasets for output

No additional code or configuration is needed for datasets to be written
(‘staged out’) from Application Packages or served when the container image is
run in xcube Server/Viewer mode. xcengine will automatically output or serve
any instances of `xarray.Dataset` or `pandas.DataFrame` which are in scope when
the notebook's code has finished executing. Subtypes of these datatypes are
also detected, so e.g. `geopandas.GeoDataFrame` will be output or served like
its parent type `pandas.DataFrame`.

If you're created some datasets which you *don't* wish to be written, you can
use the Python [`del` statement](https://docs.python.org/3/reference/simple_stmts.html#the-del-statement)
to delete them at the end of the notebook to remove them, e.g.

```python
del my_temporary_dataset
```

### Setting dataset output type

By default, all `xarray.Dataset` instances are written as Zarr. But you can
force them to be written as NetCDF by setting an attribute on the dataset,
like this:

```python
my_dataset.attrs["xcengine_output_format"] = "netcdf"
```

`pandas.DataFrame` instances are always written as CSV.

### Setting STAC metadata

In Application Package mode, output data are accompanied by
[STAC records](https://stacspec.org/) describing the data. Some of the data
for STAC records can be derived from metadata attributes on the datasets
themselves. xcengine functionality for automatically deriving STAC metadata
is currently limited to setting the bounding box via metadata in the global
attributes dictionary in the `attrs` attribute of the dataset. The following
attributes are used by xcengine when exporting data:

- `geospatial_lon_min`
- `geospatial_lat_min`
- `geospatial_lon_max`
- `geospatial_lat_max`

If a dataset has a geographical extent which can be represented by these
limits, it is recommended to ensure that they are set. If they are not present,
xcengine will use default values.

## Determining whether your code is running in an xcengine container

In an xcengine-derived container, the environment variable `XCENGINE_VERSION`
is always set to the version of xcengine that created the container image. If
your notebook code needs to determine whether it's running inside an xcengine
container, you can check whether this variable is set (e.g. using
`os.environ`).

## Installing local Python packages in the container's Python environment

In most cases, a notebook's environment can be fully defined by an
`environment.yml` file which only lists dependencies from public sources
(e.g. conda-forge and PyPI). Sometimes, however, you may need to use a
package which is available on your local computer, but has not been published
to any public channel. xcengine provides a way to do this, as detailed
below. You can also find an example in the `inclusions.ipynb` notebook. 

### 1. Reference the local package in your `environment.yml` file

In the `environment.yml` file defining the notebook's environment, list
any local package dependencies in the `pip` section, for example:

```yaml
name: myenvironment
channels:
  - conda-forge
dependencies:
  - python >=3.11
  - xarray
  - pip:
    - ./mylocalpackage/
    - ./someotherpackage.whl
```

Referenced packages can be pre-built wheels or Python package directories.

Note that, when building the Python environment, all these packages are
copied into the same directory as the environment file, so the environment
file should reference them in this location with a `./` prefix as shown above.

### 2. List the paths to local packages in the parameters cell

Use the configuration key `build_includes` in the xcengine configuration
dictionary in the parameter cell to list the packages to be included. The
value should be a list of strings, each one giving a path to a package.
These paths are resolved relative to the notebook itself. Such a configuration
might look as follows:

```python
xcengine_config = dict(
    environment_file="../environment.yml",
    build_includes=["../mylocalpackage", "../someotherpackage.whl"]
)
```

With this configuration, the referenced packages will be copied into the
build context and installed in the container's Python environment when the
Docker container image is being built.

## Including local data and Python modules when building an image

If your notebook relies on additional data or Python modules to run, you
can include these using the `include_directory` configuration option:

```python
xcengine_config = dict(
    include_directory=True,
)
```

This will bundle everything in the notebook's directory along with the
notebook-derived code in the container image. (It's not currently
possible to include run-time code and data from outside the notebook's
directory.)

If you reference files relative to your notebook, you will need a minor
modification to do this in the generated container.
In the notebook, we can usually assume that the current directory (CWD)
is the notebook's directory and look for data there. In an EOAP, the current
directory is usually not the same as the script's directory, so we have to
explicitly define the data directory relative to the script's own path.
You can do this with a simple code snippet:

```python
import pathlib
try:
    # Find the script's parent directory, if we're running as a script.
    datadir = pathlib.Path(__file__).parent
except NameError:
    # If __file__ is not defined, assume we're running in a notebook
    # and look for the data file in the current working directory.
    datadir = pathlib.Path.cwd()
```

Now the variable `datadir` will point to the directory containing the
notebook, and instead of reading data from that directory with e.g.

```python
df = pd.read_csv("input-data.csv")
```

you can use

```python
df = pd.read_csv(datadir / "input-data.csv")
```

which will work in both the notebook and the generated application package.

You can also find an example in the `inclusions.ipynb` notebook.
