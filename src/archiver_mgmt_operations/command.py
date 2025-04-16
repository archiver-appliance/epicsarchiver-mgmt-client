"""Command line tool for doing mgmt operations with the archiver."""

import logging
import sys
from io import TextIOWrapper

import click
from epicsarchiver.common import ArchDbrType

from archiver_mgmt_operations.commands import change_type as ct
from archiver_mgmt_operations.commands import pause_resume
from archiver_mgmt_operations.logging import CURRENT_COMMAND_LOG
from archiver_mgmt_operations.mgmt_exception import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli() -> None:
    """Command line tool for doing mgmt operations with the archiver."""


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, default=None, help="Archiver where PVs reside.")
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.pass_context
def pause(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper) -> None:
    """Pause PVs in the archiver.

    ARGUMENT file csv file of what pvs to pause.

    Example usage:

    .. code-block:: console

        archiver_mgmt -a archiver.example.com pause pvs.csv

    """
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = file.read().split()

    try:
        pause_resume.pause(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error pausing PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error pausing PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, default=None, help="Archiver where PVs reside.")
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.pass_context
def resume(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper) -> None:
    """Resume Archiving PVs in the archiver.

    ARGUMENT file csv file of what pvs to resume.

    Example usage:

    .. code-block:: console

        archiver_mgmt -a archiver.example.com resume pvs.csv

    """
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = file.read().split()

    try:
        pause_resume.resume(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error resuming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error resuming PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


def archdbrtype_from_param(value: str) -> ArchDbrType | None:
    """Convert a string to a ArchDbrType.

    Args:
        value (str): The value to convert.

    Returns:
        ArchDbrType: The ArchDbrType.
    """
    try:
        return ct.archdbrtype_from_str(value)
    except ct.InvalidArchDbrTypeError as e:
        LOG.error("Invalid ArchDbrType: %s", str(e))  # noqa: TRY400
        LOG.debug("Invalid ArchDbrType.", exc_info=True)
    return None


@click.command(context_settings={"show_default": True})
@click.option("--archiver_fqdn", "-a", type=str, default=None, help="Archiver where PVs reside.")
@click.option(
    "--new-type",
    type=str,
    default=None,
    help="Type to change PVs to.",
    callback=lambda _c, _p, v: archdbrtype_from_param(v),
)
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.pass_context
def change_type(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper, new_type: ArchDbrType | None) -> None:
    """Pause PVs in the archiver.

    ARGUMENT file csv file of what pvs to pause.

    Example usage:

    .. code-block:: console

        archiver_mgmt -f archiver.example.com pause pvs.csv

    """
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    if new_type is None:
        LOG.error("Invalid arch dbr type. Please provide a valid type.")
        ctx.exit(1)

    # Read input
    pvs = file.read().split()

    try:
        ct.change_type(archiver_fqdn, pvs, new_type)
    except BaseMgmtError as e:
        LOG.error("Error changing type of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing type of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


cli.add_command(change_type)
cli.add_command(pause)
cli.add_command(resume)
