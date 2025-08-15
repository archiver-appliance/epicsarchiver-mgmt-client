"""Command line tool for doing mgmt operations with the archiver."""

import logging
import sys
from io import TextIOWrapper
from typing import TextIO

import click
from epicsarchiver.common import ArchDbrType

from epicsarchiver_mgmt.archiver.mgmt import ArchivePVRequest, EpicsProto, SamplingMethod
from epicsarchiver_mgmt.commands import alias as cmd_alias
from epicsarchiver_mgmt.commands import archive as cmd_archive
from epicsarchiver_mgmt.commands import basic_commands
from epicsarchiver_mgmt.commands import change_parameter as c_param
from epicsarchiver_mgmt.commands import change_protocol as cp
from epicsarchiver_mgmt.commands import change_type as ct
from epicsarchiver_mgmt.commands import clear_queue as cmd_clear_queue
from epicsarchiver_mgmt.commands import rename as cmd_rename
from epicsarchiver_mgmt.commands import repolicy as repol
from epicsarchiver_mgmt.commands import statuses as gs
from epicsarchiver_mgmt.input_parsing import ParseCSVRowError, double_column_csv, single_column_csv
from epicsarchiver_mgmt.logging import setup_file_handler

LOG: logging.Logger = logging.getLogger(__name__)


def validate_str_input(ctx: click.Context, param: click.Parameter, value: str | None) -> str:
    """Check if the command input is provided.

    Args:
        ctx (click.Context): The click context.
        param (click.Parameter): The click parameter.
        value (str | None): The value of the parameter.

    Returns:
        str | None: The value if it is valid, otherwise raises click.BadParameter.

    Raises:
        click.BadParameter: If the value is None or empty.
    """
    if not value:
        msg = f"{param.name} is required."
        raise click.BadParameter(msg, ctx=ctx, param=param)
    return value


def validate_file_input(ctx: click.Context, param: click.Parameter, value: TextIOWrapper) -> TextIOWrapper:
    """Check if the command input is provided.

    Args:
        ctx (click.Context): The click context.
        param (click.Parameter): The click parameter.
        value (str | None): The value of the parameter.

    Returns:
        str | None: The value if it is valid, otherwise raises click.BadParameter.

    Raises:
        click.BadParameter: If the value is None or empty.
    """
    if not value:
        msg = f"{param.name} is required."
        raise click.BadParameter(msg, ctx=ctx, param=param)
    return value


@click.group()
@click.version_option()
def cli() -> None:
    """Command line tool for doing mgmt operations with the archiver."""


archiver_fqdn_option = click.option(
    "--archiver-fqdn", "-a", type=str, callback=validate_str_input, help="Archiver where PVs reside."
)
archiver_fqdns_option = click.option(
    "--archiver-fqdns", "-a", type=str, multiple=True, callback=validate_str_input, help="Archiver where PVs reside."
)

file_argument = click.argument(
    "file",
    type=click.File(),
    callback=validate_file_input,
    default=sys.stdin,
)


@click.command(context_settings={"show_default": True})
@archiver_fqdns_option
@file_argument
@click.pass_context
def pause(ctx: click.Context, archiver_fqdns: list[str], file: TextIOWrapper) -> None:
    """Pause PVs in the archiver.

    ARGUMENT file csv file of what pvs to pause.

    Example usage:

    .. code-block:: console

        arch-mgmt pause -a archiver.example.com pvs.csv

    """
    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        basic_commands.PauseCommand().run_command(archiver_fqdns, pvs)
    except Exception as e:
        LOG.error("Error pausing PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error pausing PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@archiver_fqdns_option
@file_argument
@click.pass_context
def delete(ctx: click.Context, archiver_fqdns: list[str], file: TextIOWrapper) -> None:
    """Delete PVs in the archiver.

    ARGUMENT file csv file of what pvs to delete.

    Example usage:

    .. code-block:: console

        arch-mgmt delete -a archiver.example.com pvs.csv

    """
    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        basic_commands.DeleteCommand().run_command(archiver_fqdns, pvs)
    except Exception as e:
        LOG.error("Error deleting PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error deleting PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@archiver_fqdn_option
@file_argument
@click.option(
    "--output-file",
    "-o",
    type=click.File(mode="w"),
    help="Output file.",
    default=sys.stdout,
)
@click.pass_context
def statuses(
    ctx: click.Context,
    archiver_fqdn: str,
    file: TextIOWrapper,
    output_file: TextIOWrapper,
) -> None:
    """Get the status of PVs in the archiver.

    ARGUMENT file csv file of what pvs to get status.

    Example usage:

    .. code-block:: console

        arch-mgmt statuses -a archiver.example.com pvs.csv

    """
    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        status_pvs = gs.get_statuses(archiver_fqdn, pvs)
        output_file.write("PV Statuses:\n")
        for status, pv_list in status_pvs.items():
            output_file.write(f"{status}:\n")
            output_file.writelines(f"{pv}\n" for pv in pv_list)
    except Exception as e:
        LOG.error("Error getting status of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error getting status of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@archiver_fqdns_option
@file_argument
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
    archiver_fqdns: list[str],
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

        arch-mgmt rename -a archiver.example.com -a archiver.example.com pvs.csv

    """
    # Check input

    # Read input
    try:
        pv_pairs = double_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        if and_append:
            cmd_rename.rename_and_append(archiver_fqdns, pv_pairs, dry_run=dry_run)
        else:
            cmd_rename.rename(archiver_fqdns, pv_pairs, dry_run=dry_run)
    except Exception as e:
        LOG.error("Error renaming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error renaming PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@archiver_fqdns_option
@file_argument
@click.pass_context
def resume(ctx: click.Context, archiver_fqdns: list[str], file: TextIOWrapper) -> None:
    """Resume Archiving PVs in the archiver.

    ARGUMENT file csv file of what pvs to resume.

    Example usage:

    .. code-block:: console

        arch-mgmt resume -a archiver.example.com pvs.csv

    """
    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        basic_commands.ResumeCommand().run_command(archiver_fqdns, pvs)
    except Exception as e:
        LOG.error("Error resuming PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error resuming PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


def _parse_archive_requests(file: TextIO, appliance: str | None) -> list[ArchivePVRequest]:
    requests = double_column_csv(file)
    return [ArchivePVRequest(pv, policy=policy, appliance=appliance) for pv, policy in requests]


@click.command(context_settings={"show_default": True})
@archiver_fqdn_option
@click.option("--dry-run", "-d", is_flag=True, help="Do a dry run.", default=False)
@click.option("--appliance", "-ap", type=str, help="Appliance to archive to.", default=None)
@file_argument
@click.pass_context
def archive(ctx: click.Context, archiver_fqdn: str, dry_run: bool, appliance: str | None, file: TextIOWrapper) -> None:  # noqa: FBT001
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

        arch-mgmt archive -a archiver.example.com pvs.csv

    """
    # Read input
    try:
        pv_requests = _parse_archive_requests(file, appliance)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    if not pv_requests:
        msg = "No PVs found in the input file. Please provide a valid CSV file with PVs to archive."
        raise click.BadParameter(
            msg,
            ctx=ctx,
            param_hint="file",
        )
    setup_file_handler(ctx.command_path)

    try:
        cmd_archive.archive(archiver_fqdn, pv_requests, dry_run=dry_run)
    except Exception as e:
        LOG.error("Error archiving PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error archiving PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@archiver_fqdn_option
@click.option(
    "--new-type",
    "-t",
    type=click.Choice(ArchDbrType, case_sensitive=False),
    help="Type to change PVs to.",
    required=True,
)
@file_argument
@click.pass_context
def change_type(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper, new_type: ArchDbrType | None) -> None:
    """Change the type of PVs in the archiver.

    ARGUMENT file csv file of what pvs to change type.

    Example usage:

    .. code-block:: console

        arch-mgmt change-type -a archiver.example.com --new-type DBR_SCALAR_DOUBLE pvs.csv

    """
    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        ct.change_type(archiver_fqdn, pvs, new_type)  # type: ignore[arg-type] # Ignoring because of the check in the function
    except Exception as e:
        LOG.error("Error changing type of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing type of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@archiver_fqdn_option
@click.option(
    "--protocol",
    "-p",
    type=click.Choice(EpicsProto, case_sensitive=False),
    help="Protocol to change PVs to.",
    required=True,
)
@file_argument
@click.pass_context
def change_protocol(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper, protocol: EpicsProto | None) -> None:
    """Change the protocol of PVs in the archiver.

    ARGUMENT file csv file of what pvs to change protocol.

    Example usage:

    .. code-block:: console

        arch-mgmt change-protocol -a archiver.example.com --new-protocol ca pvs.csv

    """
    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        cp.change_protocol(archiver_fqdn, pvs, protocol)  # type: ignore[arg-type] # Ignoring because of the check in the function
    except Exception as e:
        LOG.error("Error changing protocol of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing protocol of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@archiver_fqdn_option
@file_argument
@click.pass_context
def repolicy(ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper) -> None:
    """Re choose the policy of PVs in the archiver.

    ARGUMENT file csv file of what pvs to change protocol.

    Example usage:

    .. code-block:: console

        arch-mgmt repolicy -a archiver.example.com pvs.csv

    """
    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        repol.repolicy(archiver_fqdn, pvs)
    except Exception as e:
        LOG.error("Error repolicy of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error repolicy of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archivers where PVs reside.")
@click.option(
    "--method",
    "-m",
    type=click.Choice(SamplingMethod, case_sensitive=False),
    help="Sampling method swap to.",
)
@click.option(
    "--period",
    "-p",
    type=float,
    help="Sampling period swap to.",
)
@file_argument
@click.pass_context
def change_parameter(
    ctx: click.Context, archiver_fqdn: str, file: TextIOWrapper, method: SamplingMethod | None, period: float | None
) -> None:
    """Change the archiving parameters of PVs in the archiver.

    ARGUMENT file csv file of what pvs to change archiving parameters.

    Example usage:

    .. code-block:: console

        arch-mgmt change-parameter -a archiver.example.com --method SCAN --period 10.0 pvs.csv

    """
    if method is None and period is None:
        param = method or period
        msg = "At least one of method or period must be defined"
        raise click.BadParameter(msg, ctx=ctx, param=param)

    # Read input
    try:
        pvs = single_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    try:
        c_param.change_parameter(archiver_fqdn, pvs, method, period)
    except Exception as e:
        LOG.error("Error changing parameter of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing parameter of PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command(context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archivers where PVs reside.")
@click.pass_context
def clear_queue(ctx: click.Context, archiver_fqdn: str) -> None:
    """Clear Queue of already archiving PVs in the archiver.

    Example usage:

    .. code-block:: console

        arch-mgmt clear-queue -a archiver.example.com
    """
    setup_file_handler(ctx.command_path)
    try:
        cmd_clear_queue.clear_queue(archiver_fqdn)
    except Exception as e:
        LOG.error("Error clearing queue: %s", str(e))  # noqa: TRY400
        LOG.debug("Error clearing queue.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.group()
def alias() -> None:
    """Alias PVs in the archiver."""


@click.command("add", context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archivers where PVs reside.")
@file_argument
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

        arch-mgmt alias add -a archiver.example.com pvs.csv

    """
    # Read input
    try:
        pv_pairs = double_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        cmd_alias.add_aliases(archiver_fqdn, pv_pairs)
    except Exception as e:
        LOG.error("Error adding alias PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error adding alias PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


@click.command("remove", context_settings={"show_default": True})
@click.option("--archiver-fqdn", "-a", type=str, help="Archivers where PVs reside.")
@file_argument
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

        arch-mgmt alias remove -a archiver.example.com pvs.csv
    """
    # Read input
    try:
        pv_pairs = double_column_csv(file)
    except ParseCSVRowError as err:
        _parse_error_to_bad_param(ctx, err)

    setup_file_handler(ctx.command_path)
    try:
        cmd_alias.remove_aliases(archiver_fqdn, pv_pairs)
    except Exception as e:
        LOG.error("Error removing alias PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error removing alias PVs.", exc_info=True)
        ctx.exit(1)

    ctx.exit(0)


def _parse_error_to_bad_param(ctx: click.Context, err: ParseCSVRowError) -> None:
    """Convert a ParseCSVRowError to a click.BadParameter.

    Args:
        ctx (click.Context): The click context.
        err (ParseCSVRowError): The error to convert.

    Raises:
        click.BadParameter: If the error is a ParseCSVRowError.
    """
    msg = "Invalid CSV format."
    raise click.BadParameter(
        msg,
        ctx=ctx,
        param_hint="file",
    ) from err


alias.add_command(add_alias)
alias.add_command(remove_alias)

cli.add_command(change_type)
cli.add_command(change_protocol)
cli.add_command(change_parameter)
cli.add_command(pause)
cli.add_command(delete)
cli.add_command(resume)
cli.add_command(archive)
cli.add_command(rename)
cli.add_command(alias)
cli.add_command(repolicy)
cli.add_command(clear_queue)
cli.add_command(statuses)
