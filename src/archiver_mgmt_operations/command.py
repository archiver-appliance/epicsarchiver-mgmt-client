"""Command line tool for doing mgmt operations with the archiver."""

import logging
import sys
from io import TextIOWrapper

import click

from archiver_mgmt_operations.commands import pause_resume
from archiver_mgmt_operations.logging import CURRENT_COMMAND_LOG
from archiver_mgmt_operations.mgmt_exception import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli() -> None:
    """Command line tool for doing mgmt operations with the archiver."""


@click.command(context_settings={"show_default": True})
@click.option("--archiver_fqdn", "-a", type=str, default=None, help="Archiver where PVs reside.")
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
@click.option("--archiver_fqdn", "-a", type=str, default=None, help="Archiver where PVs reside.")
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


cli.add_command(pause)
cli.add_command(resume)
