# mgmt_operations

Project for tracking changes to the archiver via the mgmt operations interface. For example, change types, complicated renames, adding aliases.

## Installation

```console
pip install epicsarchiver-mgmt -i https://artifactory.esss.lu.se/artifactory/api/pypi/pypi-virtual/simple
```

## Usage

```console
Usage: arch-mgmt [OPTIONS] COMMAND [ARGS]...

  Command line tool for doing mgmt operations with the archiver.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  alias             Alias PVs in the archiver.
  archive           Archive PVs in the archiver.
  change-parameter  Change the archiving parameters of PVs in the archiver.
  change-protocol   Change the protocol of PVs in the archiver.
  change-type       Change the type of PVs in the archiver.
  delete            Delete PVs in the archiver.
  pause             Pause PVs in the archiver.
  rename            Rename PVs in the archiver.
  resume            Resume Archiving PVs in the archiver.
```

## Development

The package is built and packaged with [Hatch](https://hatch.pypa.io/latest/).

```console
pip install hatch
```

Run all checks and code coverage:

```console
hatch run all
```

Run tests:

```console
hatch test
```

Run formatting and check:

```console
hatch fmt
```
