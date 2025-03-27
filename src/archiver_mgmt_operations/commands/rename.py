"""Rename PVs in the archiver."""

from __future__ import annotations

import logging
import random
from concurrent.futures import ThreadPoolExecutor
from typing import cast

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from archiver_mgmt_operations.commands.validation import (
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)
from archiver_mgmt_operations.mgmt.archiver_mgmt_operations import (
    ArchiverMgmtOperations,
    OperationResult,
)

LOG: logging.Logger = logging.getLogger(__name__)


def rename(archiver_fqdns: list[str], renames: list[tuple[str, str]]) -> None:
    """Rename PVs in the archiver, runs in parallel on multiple archivers.

    Args:
        archiver_fqdns (list[str]): The urls of the archivers.
        renames (list[tuple[str, str]]): The PVs to rename.

    Raises:
        RequestHTTPError: If there is an error renaming the PVs.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdns[0])
    validate_pvs_status(
        archiver_info,
        [old_pv for old_pv, _new_pv in renames],
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.Paused,
        ],
    )
    validate_pvs_status(
        archiver_info,
        [new_pv for _old_pv, new_pv in renames],
        [
            ArchivingStatus.NotBeingArchived,
        ],
    )

    # Action
    LOG.info("Renaming PVs %s", renames)

    archivers = [ArchiverMgmtOperations(archiver_fqdn) for archiver_fqdn in archiver_fqdns]

    LOG.info("Using archivers %s", [archiver.info for archiver in archivers])

    try:
        # pause all the pvs
        pause_results = [random.choice(archivers).pause_pv(old_pv) for old_pv, _new_pv in renames]  # noqa: S311

        validate_operation_results(
            [old_pv for old_pv, _new_pv in renames],
            [cast("OperationResult", result) for result in pause_results],
            "renamed",
        )

    except HTTPError as e:
        LOG.error("Error archiving PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error archiving PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    try:
        # rename all the pvs, this can take a long time so we do it in parallel
        rename_results = _parallel_execute_rename(archivers, renames)
    except HTTPError as e:
        LOG.error("Error archiving PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error archiving PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(
        [new_pv for _old_pv, new_pv in renames],
        [cast("OperationResult", result) for result in rename_results],
        "renamed",
    )


def _parallel_execute_rename(
    archivers: list[ArchiverMgmtOperations], renames: list[tuple[str, str]]
) -> list[OperationResult]:
    def rename_pv_task(task_input: tuple[ArchiverMgmtOperations, str, str]) -> OperationResult:
        archiver, old_pv, new_pv = task_input
        return archiver.rename_pv(old_pv, new_pv)

    with ThreadPoolExecutor(max_workers=len(archivers)) as executer:
        executer_input = [(archivers[i % len(archivers)], old_pv, new_pv) for i, (old_pv, new_pv) in enumerate(renames)]
        return list(executer.map(rename_pv_task, executer_input))
