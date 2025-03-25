import logging
import sys
from io import TextIOWrapper

import click

from archiver_mgmt_operations.commands import pause_resume

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
def pause(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper):
    """Pause PVs in the archiver.

    ARGUMENT file csv file of what pvs to pause.

    Example usage:

    .. code-block:: console

        archiver_mgmt -f archiver.example.com pause pvs.csv

    """
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = file.read().split()

    output_valid = pause_resume.pause(archiver_fqdn, pvs)

    if not output_valid:
        ctx.exit(1)
    ctx.exit(0)


cli.add_command(pause)
