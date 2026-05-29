"""Parse the input csv file."""

import csv
import logging
from collections.abc import Sequence
from typing import TextIO

from epicsarchiver_mgmt.exceptions import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)


class ParseCSVRowError(BaseMgmtError):
    """Exception for when the csv file is invalid."""

    def __init__(self, row: list[str] | None = None) -> None:
        """Error for when the csv file is invalid.

        Args:
            row (str): The bad row.
        """
        super().__init__(f"Invalid row {row} in csv file")
        self.row = row


def parse_csv(file: TextIO, expected_columns: int) -> dict[str, list[str]]:
    """Parse the csv file.

    Args:
        file (TextIOWrapper): The file to parse.
        expected_columns (int): The expected number of columns in csv file

    Returns:
        list[tuple[str, ...]]: The list of tuples of PVs.

    Raises:
        ParseCSVRowError: If the file is invalid.
    """
    csv_rows = csv.reader(file)
    if not csv_rows:
        LOG.error("Empty csv file")
        raise ParseCSVRowError
    result: dict[str, list[str]] = {}
    for row in csv_rows:
        pvs = row
        if len(pvs) != expected_columns:
            LOG.error("Invalid row in csv file: %s", row)
            raise ParseCSVRowError(row)
        result[pvs[0]] = pvs[1:]
    return result


def single_column_csv(file: TextIO) -> Sequence[str]:
    """Parse the csv file with a single column.

    Args:
        file (TextIOWrapper): The file to parse.

    Returns:
        list[str]: The list of PVs.
    """
    return tuple(parse_csv(file, 1).keys())


def double_column_csv(file: TextIO) -> Sequence[tuple[str, str]]:
    """Parse the csv file with two columns.

    Args:
        file (TextIOWrapper): The file to parse.

    Returns:
        dict[str, str]: The dictionary of PVs.
    """
    return [(x, y[0]) for x, y in parse_csv(file, 2).items()]
