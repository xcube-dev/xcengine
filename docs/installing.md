# Installing xcengine

xcengine is developed on GitHub and distributed as a Conda package on the
conda-forge channel.

## Installing from conda-forge

Using mamba, conda, or any other conda-compatible package manager, you can
install xcengine into the current environment with a command like

```bash
mamba install -c conda-forge xcengine
```

You can create a new environment containing xcengine with a command like

```bash
mamba create -c conda-forge xcengine
```

## Installing directly from the GitHub repository

If you want to work with the latest, unreleased development version of xcengine,
you can install it from the GitHub repository.

First, clone the repository and change to its root directory:

```bash
git clone https://github.com/xcube-dev/xcengine.git
cd xcengine
```

Next, create a conda environment containing the dependencies and activate it:

```bash
mamba env create -f environment.yml
mamba activate xcengine
```

Finally, install xcengine itself from the repository using pip:

```bash
pip install --no-deps --editable .
```
