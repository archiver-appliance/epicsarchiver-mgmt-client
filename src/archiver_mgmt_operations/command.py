"""Command line tool for doing mgmt operations with the archiver."""

import logging
import sys
from io import TextIOWrapper
from typing import TextIO

import click
from epicsarchiver.common import ArchDbrType

from archiver_mgmt_operations.commands import alias as cmd_alias
from archiver_mgmt_operations.commands import archive as cmd_archive
from archiver_mgmt_operations.commands import change_type as ct
from archiver_mgmt_operations.commands import pause_resume
from archiver_mgmt_operations.commands import rename as cmd_rename
from archiver_mgmt_operations.input_parsing import double_column_csv, single_column_csv
from archiver_mgmt_operations.logging import CURRENT_COMMAND_LOG
from archiver_mgmt_operations.mgmt.archiver_mgmt_operations import ArchivePVRequest
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
    pvs = single_column_csv(file)

    try:
        pause_resume.pause(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error pausing PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error pausing PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, default=None, help="Archivers where PVs reside.", multiple=True)
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.option(
    "--and-append",
    "-aa",
    type=bool,
    is_flag=True,
    default=False,
    required=True,
    help="Append the data of the new PV to the old PV and rename them.",
)
@click.pass_context
def rename(ctx: click.Context, archiver_fqdn: list[str], file: TextIOWrapper, and_append: bool = False) -> None:  # noqa: FBT001, FBT002
    """Rename PVs in the archiver.

    ARGUMENT file csv file of what pvs to rename.

    Example file:

    .. code-block:: console

        old_pv,new_pv
        pv1,pv2
        pv3,pv4

    Example usage:

    .. code-block:: console

        archiver_mgmt -f archiver.example.com -f archiver.example.com rename pvs.csv

    """
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = double_column_csv(file)

    try:
        if and_append:
            cmd_rename.rename_and_append(archiver_fqdn, pvs)
        else:
            cmd_rename.rename(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error renaming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error renaming PVs.", exc_info=True)
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
    pvs = single_column_csv(file)

    try:
        pause_resume.resume(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error resuming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error resuming PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


def _parse_archive_requests(file: TextIO) -> list[ArchivePVRequest]:
    requests = double_column_csv(file)
    return [ArchivePVRequest(pv, policy=policy) for pv, policy in requests]


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, default=None, help="Archiver where PVs reside.")
@click.option("--dry-run", "-d", is_flag=True, help="Do a dry run.", default=False)
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.pass_context
def archive(ctx: click.Context, archiver_fqdn: str, dry_run: bool, file: TextIOWrapper) -> None:  # noqa: FBT001
    """Archive PVs in the archiver.

    ARGUMENT file csv file of what pvs to archive. The csv file should have the following format:

    Example:
    PV,policy
    mypv1,
    mypv2,1Hz
    mypv3,1HzSCAN

    Policy is optional. If not provided, the default policy will be used. You can find the options at
    archiver.example.com/mgmt/bpl/getPolicyList.

    Example usage:

    .. code-block:: console

        archiver_mgmt -f archiver.example.com archive pvs.csv

    """
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pv_requests = _parse_archive_requests(file)

    try:
        cmd_archive.archive(archiver_fqdn, pv_requests, dry_run=dry_run)
    except BaseMgmtError as e:
        LOG.error("Error archiving PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error archiving PVs.", exc_info=True)
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
@click.option("--archiver-fqdn", "-a", type=str, default=None, help="Archiver where PVs reside.")
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
    """Change the type of PVs in the archiver.

    ARGUMENT file csv file of what pvs to change type.

    Example usage:

    .. code-block:: console

        archiver_mgmt -f archiver.example.com change_type --new-type DBR_SCALAR_DOUBLE pvs.csv

    """
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    if new_type is None:
        LOG.error("Invalid arch dbr type. Please provide a valid type.")
        ctx.exit(1)

    # Read input
    pvs = single_column_csv(file)

    try:
        ct.change_type(archiver_fqdn, pvs, new_type)
    except BaseMgmtError as e:
        LOG.error("Error changing type of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing type of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.group()
def alias() -> None:
    """Alias PVs in the archiver."""


@click.command("add", context_settings={"show_default": True})
@click.option("--archiver_fqdn", "-a", type=str, default=None, help="Archivers where PVs reside.")
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.pass_context
def add_alias(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper) -> None:
    """Add alias to PVs in the archiver.

    ARGUMENT file csv file of what pvs to alias.

    Example file:

    .. code-block:: console

        original_pv,alias_pv_name
        pv1,pv2
        pv3,pv4

    Example usage:

    .. code-block:: console

        archiver_mgmt -f archiver.example.com alias add pvs.csv

    """
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = double_column_csv(file)

    try:
        cmd_alias.add_aliases(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error adding alias PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error adding alias PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command("remove", context_settings={"show_default": True})
@click.option("--archiver_fqdn", "-a", type=str, default=None, help="Archivers where PVs reside.")
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.pass_context
def remove_alias(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper) -> None:
    """Remove aliases to PVs in the archiver.

    ARGUMENT file csv file of what pvs to alias.

    Example file:

    .. code-block:: console

        original_pv,alias_pv_name
        pv1,pv2
        pv3,pv4

    Example usage:

    .. code-block:: console

        archiver_mgmt -f archiver.example.com alias remove pvs.csv

    """
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = double_column_csv(file)

    try:
        cmd_alias.remove_aliases(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error removing alias PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error removing alias PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


alias.add_command(add_alias)
alias.add_command(remove_alias)

cli.add_command(change_type)
cli.add_command(pause)
cli.add_command(resume)
cli.add_command(archive)
cli.add_command(rename)
cli.add_command(alias)
