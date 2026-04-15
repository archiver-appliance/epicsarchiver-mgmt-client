# Installation

**This package requires Python 3.12 or above.**

## Install

```console
pip install epicsarchiver-mgmt -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple
```

To avoid passing the PyPI repository URL on every command, create a `~/.pip/pip.conf`:

```ini
[global]
index-url = https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple
```

The `pypi-virtual` repository aggregates packages from the local `ics-pypi` repository and the remote
`pypi-remote` that serves as a caching proxy for <https://pypi.python.org>.

Once installed, the `arch-mgmt` command is available on your `PATH`.
