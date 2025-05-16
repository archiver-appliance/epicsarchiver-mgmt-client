"""Command line tool for doing mgmt operations with the archiver."""

import logging
import sys
from io import TextIOWrapper
from typing import Any, TextIO

import click
from epicsarchiver.common import ArchDbrType

from epicsarchiver_mgmt.archiver.mgmt import ArchivePVRequest, EpicsProto
from epicsarchiver_mgmt.commands import alias as cmd_alias
from epicsarchiver_mgmt.commands import archive as cmd_archive
from epicsarchiver_mgmt.commands import basic_commands
from epicsarchiver_mgmt.commands import change_protocol as cp
from epicsarchiver_mgmt.commands import change_type as ct
from epicsarchiver_mgmt.commands import rename as cmd_rename
from epicsarchiver_mgmt.input_parsing import double_column_csv, single_column_csv
from epicsarchiver_mgmt.logging import CURRENT_COMMAND_LOG
from epicsarchiver_mgmt.mgmt_exception import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)


def check_command_input(ctx: click.Context, command_input: Any | None, input_name: str) -> None:  # noqa: ANN401
    """Check if the command input is provided.

    Args:
        ctx (click.Context): The click context.
        command_input (Any | None): input to check.
        input_name (str): The name of the command.
    """
    if not command_input:
        LOG.error("No %s provided.", input_name)
        ctx.exit(1)


@click.group()
@click.version_option()
def cli() -> None:
    """Command line tool for doing mgmt operations with the archiver."""


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archiver where PVs reside.")
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

        arch-mgmt -a archiver.example.com pause pvs.csv

    """
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")

    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = single_column_csv(file)
    check_command_input(ctx, pvs, "pvs")

    try:
        basic_commands.PauseCommand().run_command(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error pausing PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error pausing PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archivers where PVs reside.", multiple=True)
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
@click.option("--dry-run", "-d", is_flag=True, help="Do a dry run.", default=False)
@click.pass_context
def rename(
    ctx: click.Context,
    archiver_fqdn: list[str],
    file: TextIOWrapper,
    and_append: bool = False,  # noqa: FBT001, FBT002
    dry_run: bool = False,  # noqa: FBT001, FBT002
) -> None:
    """Rename PVs in the archiver.

    ARGUMENT file csv file of what pvs to rename.

    Example file:

    .. code-block:: console

        old_pv,new_pv
        pv1,pv2
        pv3,pv4

    Example usage:

    .. code-block:: console

        arch-mgmt -f archiver.example.com -f archiver.example.com rename pvs.csv

    """
    # Check input
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = double_column_csv(file)
    check_command_input(ctx, pvs, "pvs")

    try:
        if and_append:
            cmd_rename.rename_and_append(archiver_fqdn, pvs, dry_run=dry_run)
        else:
            cmd_rename.rename(archiver_fqdn, pvs, dry_run=dry_run)
    except BaseMgmtError as e:
        LOG.error("Error renaming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error renaming PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archiver where PVs reside.")
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

        arch-mgmt -a archiver.example.com resume pvs.csv

    """
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = single_column_csv(file)
    check_command_input(ctx, pvs, "pvs")

    try:
        basic_commands.ResumeCommand().run_command(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error resuming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error resuming PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


def _parse_archive_requests(file: TextIO) -> list[ArchivePVRequest]:
    requests = double_column_csv(file)
    return [ArchivePVRequest(pv, policy=policy) for pv, policy in requests]


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archiver where PVs reside.")
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

        arch-mgmt -f archiver.example.com archive pvs.csv

    """
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")

    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pv_requests = _parse_archive_requests(file)
    check_command_input(ctx, pv_requests, "pv_requests")

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
@click.option("--archiver-fqdn", "-a", type=str, help="Archiver where PVs reside.")
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

        arch-mgmt -f archiver.example.com change_type --new-type DBR_SCALAR_DOUBLE pvs.csv

    """
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")
    check_command_input(ctx, new_type, "new type")

    # Read input
    pvs = single_column_csv(file)
    check_command_input(ctx, pvs, "pvs")

    try:
        ct.change_type(archiver_fqdn, pvs, new_type)  # type: ignore[arg-type] # Ignoring because of the check in the function
    except BaseMgmtError as e:
        LOG.error("Error changing type of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing type of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


def epicsproto_from_param(value: str) -> EpicsProto | None:
    """Convert a string to a EpicsProto.

    Args:
        value (str): The value to convert.

    Returns:
        EpicsProto: The EpicsProto.
    """
    try:
        return cp.epicsproto_from_str(value)
    except cp.InvalidEpicsProtoError as e:
        LOG.error("Invalid EpicsProto: %s", str(e))  # noqa: TRY400
        LOG.debug("Invalid EpicsProto.", exc_info=True)
    return None


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archiver where PVs reside.")
@click.option(
    "--protocol",
    "-p",
    type=str,
    default=None,
    help="Protocol to change PVs to.",
    callback=lambda _c, _p, v: epicsproto_from_param(v),
)
@click.argument(
    "file",
    type=click.File(),
    default=sys.stdin,
)
@click.pass_context
def change_protocol(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper, protocol: EpicsProto | None) -> None:
    """Change the protocol of PVs in the archiver.

    ARGUMENT file csv file of what pvs to change protocol.

    Example usage:

    .. code-block:: console

        arch-mgmt -f archiver.example.com change_protocol --new-protocol ca pvs.csv

    """
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")
    check_command_input(ctx, protocol, "new protocol")

    # Read input
    pvs = single_column_csv(file)
    check_command_input(ctx, pvs, "pvs")

    try:
        cp.change_protocol(archiver_fqdn, pvs, protocol)  # type: ignore[arg-type] # Ignoring because of the check in the function
    except BaseMgmtError as e:
        LOG.error("Error changing protocol of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing protocol of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.group()
def alias() -> None:
    """Alias PVs in the archiver."""


@click.command("add", context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archivers where PVs reside.")
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

        arch-mgmt -f archiver.example.com alias add pvs.csv

    """
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = double_column_csv(file)
    check_command_input(ctx, pvs, "pvs")

    try:
        cmd_alias.add_aliases(archiver_fqdn, pvs)
    except BaseMgmtError as e:
        LOG.error("Error adding alias PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error adding alias PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command("remove", context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archivers where PVs reside.")
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

        arch-mgmt -f archiver.example.com alias remove pvs.csv

    """
    check_command_input(ctx, archiver_fqdn, "archiver fqdn")
    # Read input
    LOG.info("Creating LOG file at %s", CURRENT_COMMAND_LOG)
    pvs = double_column_csv(file)
    check_command_input(ctx, pvs, "pvs")

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
cli.add_command(change_protocol)
cli.add_command(pause)
cli.add_command(resume)
cli.add_command(archive)
cli.add_command(rename)
cli.add_command(alias)
