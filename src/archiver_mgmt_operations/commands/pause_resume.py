from __future__ import annotations

import logging

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus

from archiver_mgmt_operations.mgmt.archiver_mgmt_operations import (
    ArchiverMgmtOperations,
    OperationResult,
    OperationResultList,
)

LOG: logging.Logger = logging.getLogger(__name__)

OPERATION_RESULT_STATUS = "status"


def validate_operation_results(
    pvs: list[str],
    action_results: list[OperationResult | OperationResultList],
    operation_name: str,
) -> bool:
    operation_valid = True
    for pv, result in zip(pvs, action_results):
        if isinstance(result, dict) and result.get(OPERATION_RESULT_STATUS, "false") != "ok":
            LOG.error("PV %s was not %s, result was %s.", pv, operation_name, result)
            operation_valid = False
        else:
            LOG.info("PV %s was %s.", pv, operation_name)
    return operation_valid


def validate_pvs_status(
    archiver_info: ArchiverMgmtInfo,
    pvs: list[str],
    expected_statuses: list[ArchivingStatus],
) -> bool:
    input_valid = True
    for pv in pvs:
        archiving_status = archiver_info.get_archiving_status(pv)
        if archiving_status not in expected_statuses:
            LOG.error("PV %s is %s.", pv, archiving_status)
            input_valid = False
    return input_valid


def pause(archiver_fqdn: str, pvs: list[str]) -> bool:
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    input_valid = validate_pvs_status(
        archiver_info,
        pvs,
        [
            ArchivingStatus.BeingArchived,
            ArchivingStatus.NotBeingArchived,
            ArchivingStatus.Paused,
        ],
    )
    if not input_valid:
        LOG.info("Input was not valid. Exiting.")
        return False

    # Action
    LOG.info("Pausing PVs %s", pvs)
    archiver = ArchiverMgmtOperations(archiver_fqdn)
    LOG.info("Using archiver %s", archiver.info)
    pause_results = [archiver.pause_pv(pv) for pv in pvs]

    # Validate output
    output_valid = validate_operation_results(pvs, pause_results, "paused")

    if not output_valid:
        LOG.info("There was a problem pausing the PVs. Exiting.")
        return False
    return True
