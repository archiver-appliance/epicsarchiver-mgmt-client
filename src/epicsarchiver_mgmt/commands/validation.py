"""Provide validation functions for the archiver management operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from epicsarchiver.mgmt.archiver_mgmt_info import ArchivingStatus

from epicsarchiver_mgmt.archiver.mgmt import ArchiverMgmt, EpicsProto
from epicsarchiver_mgmt.commands.statuses import get_statuses_from_archiver
from epicsarchiver_mgmt.mgmt_exception import BaseMgmtError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, InfoResultList
    from requests import HTTPError

    from epicsarchiver_mgmt.archiver.mgmt import (
        OperationResult,
        OperationResultList,
    )

LOG: logging.Logger = logging.getLogger(__name__)
OPERATION_RESULT_STATUS = "status"
OPERATION_RESULT_OK = "ok"

CONFIRMATION_PROMPT = "Are you sure you want to proceed?"


class ValidOperationResultsError(BaseMgmtError):
    """Exception for when the operation results are not valid."""

    def __init__(self, action_results: dict[str, OperationResult | OperationResultList], operation_name: str) -> None:
        """Error for when the operation results are not valid.

        Args:
            action_results (dict[str, OperationResult  |  OperationResultList]): The results of the operation.
            operation_name (str): The name of the operation.
        """
        super().__init__(f"Operation results for {operation_name} were not valid for PVs {action_results.keys()}.")
        self.action_results = action_results
        self.operation_name = operation_name


def validate_operation_results(
    pvs: Sequence[str],
    action_results: list[OperationResult] | OperationResultList,
    operation_name: str,
    *,
    expected_operation_results: dict[str, list[str]] | None = None,
) -> None:
    """Validate the results of an operation.

    Args:
        pvs (Sequence[str]): The PVs that were acted on.
        action_results (list[OperationResult  |  OperationResultList]): The results of the operation.
        operation_name (str): The name of the operation.
        expected_operation_results (dict[str, list[str]]): The expected statuses.
            Defaults to {OPERATION_RESULT_STATUS: [OPERATION_RESULT_OK]}.

    Raises:
        ValidOperationResultsError: If the results are not valid.
    """
    if expected_operation_results is None:
        expected_operation_results = {OPERATION_RESULT_STATUS: [OPERATION_RESULT_OK]}
    invalid_pvs: dict[str, OperationResult | OperationResultList] = {}
    for pv, result in zip(pvs, action_results, strict=False):
        LOG.debug("PV %s result %s for operation %s", pv, result, operation_name)
        for key, expected_results in expected_operation_results.items():
            if key not in result:
                LOG.error("Result for PV %s is missing key %s", pv, key)
                invalid_pvs[pv] = result
                continue
            if result.get(key, "false") not in expected_results:
                invalid_pvs[pv] = result
    if invalid_pvs != {}:
        raise ValidOperationResultsError(invalid_pvs, operation_name)
    LOG.info("Operation %s succeeded for PVs %s", operation_name, pvs)


class ValidPVStatusError(BaseMgmtError):
    """Exception for when a PV is not in the expected status."""

    def __init__(
        self, pv: str, archiving_status: ArchivingStatus | None, expected_statuses: list[ArchivingStatus]
    ) -> None:
        """Initialize the exception.

        Args:
            pv (str): The PV that is not in the expected status.
            archiving_status (ArchivingStatus | None): The status of the PV.
            expected_statuses (list[ArchivingStatus]): The expected statuses of the PV.
        """
        super().__init__(f"PV {pv} archiving status is {archiving_status}, needs to be in {expected_statuses}.")


def validate_pvs_status(
    archiver_info: ArchiverMgmtInfo,
    pvs: Sequence[str],
    expected_statuses: list[ArchivingStatus],
    existing_status_infos: InfoResultList | None = None,
) -> None:
    """Validate the status of PVs.

    Args:
        archiver_info (ArchiverMgmtInfo): The archiver management server.
        pvs (Sequence[str]): The PVs to validate.
        expected_statuses (list[ArchivingStatus]): The allowed statuses for the PVs.
        existing_status_infos (InfoResultList | None, optional): The existing statuses of the PVs. Defaults to None.
    """
    if existing_status_infos is not None:
        validate_pvs_status_from_existing_info(pvs, expected_statuses, existing_status_infos)
        return
    pv_statuses: InfoResultList = get_statuses_from_archiver(archiver_info, pvs)
    validate_pvs_status_from_existing_info(pvs, expected_statuses, pv_statuses)


def validate_pvs_status_from_existing_info(
    pvs: Sequence[str],
    expected_statuses: list[ArchivingStatus],
    existing_status_infos: InfoResultList,
) -> None:
    """Validate the status of PVs from existing information.

    This is used when the status information is already available and
    does not need to be fetched from the archiver.
    This is used to avoid making multiple requests to the archiver.

    Args:.
        pvs (Sequence[str]): The PVs to validate.
        expected_statuses (list[ArchivingStatus]): The allowed statuses for the PVs.
        existing_status_infos (InfoResultList): The existing statuses of the PVs.

    Raises:
        ValidPVStatusError: If a PV is not in the expected status.
    """
    unchecked_pvs = set(pvs)
    for pv_status_info in existing_status_infos:
        if pv_status_info["pvName"] in pvs:
            unchecked_pvs.discard(pv_status_info["pvName"])
            archiving_status = ArchivingStatus.from_str(pv_status_info["status"])
            LOG.debug("PV %s has status %s", pv_status_info["pvName"], archiving_status)
            if archiving_status not in expected_statuses:
                raise ValidPVStatusError(pv_status_info["pvName"], archiving_status, expected_statuses)
    if unchecked_pvs:
        raise ValidPVStatusError(
            ", ".join(unchecked_pvs),
            None,
            expected_statuses,
        )


class RequestHTTPError(BaseMgmtError):
    """Exception for when there is an HTTP error."""

    def __init__(self, http_error: HTTPError) -> None:
        """Error for when there is an HTTP error.

        Args:
            http_error (HTTPError): The HTTP error.
        """
        super().__init__(f"HTTP error: {http_error} occurred. {http_error.response.text}")
        self.http_error = http_error


class NotSamePVError(BaseMgmtError):
    """Exception for when the old and new PVs are the same."""

    def __init__(self, pv: str) -> None:
        """Error for when the old and new PVs are the same.

        Args:
            pv (str): The PV that is the same.
        """
        super().__init__(f"Old and new PVs are the same for PV {pv}.")
        self.pv = pv


def validate_not_same(pairs: Sequence[tuple[str, str]]) -> None:
    """Validate the rename operation.

    Args:
        pairs (Sequence[tuple[str, str]]): The pairs of PVs.

    Raises:
        NotSamePVError: If the old and new PVs are the same.
    """
    for old_pv, new_pv in pairs:
        if old_pv == new_pv:
            raise NotSamePVError(old_pv)


class AlreadyNewProtocolError(BaseMgmtError):
    """Exception for when a PV is already in the new protocol."""

    def __init__(self, pvs: set[str], protocol: EpicsProto) -> None:
        """Initialize the exception.

        Args:
            pvs (set[str]): The PVs that are already in the new protocol.
            protocol (EpicsProto): The new protocol.
        """
        super().__init__(f"PVs {pvs} archiving protocol is {protocol}.")
        self.pvs = pvs
        self.protocol = protocol


def validate_current_protocol(
    archiver_info: ArchiverMgmtInfo,
    pvs: Sequence[str],
    new_protocol: EpicsProto,
) -> None:
    """Validate the current protocol of the pvs is not the new protocol.

    Args:
        archiver_info (ArchiverMgmtInfo): The archiver management server.
        pvs (Sequence[str]): The PVs to validate.
        new_protocol (EpicsProto): The new protocol.

    Raises:
        AlreadyNewProtocolError: If a PV is already in the new protocol.
    """
    protocol_pvs: set[str] = set()
    for pv in pvs:
        archiving_details = archiver_info.get_pv_details(pv)
        archiving_protocol = EpicsProto.CA
        for archiving_detail in archiving_details:
            if archiving_detail["name"] == "Are we using PVAccess?":
                archiving_protocol = EpicsProto.PVA if archiving_detail["value"] == "Yes" else EpicsProto.CA
                break
        LOG.debug("PV %s has proto %s", pv, archiving_protocol)
        if archiving_protocol == new_protocol:
            protocol_pvs.add(pv)
    if protocol_pvs:
        raise AlreadyNewProtocolError(protocol_pvs, new_protocol)


class DifferentArchiverClusterError(BaseMgmtError):
    """Exception for when the archiver FQDNs are not part of the same cluster."""

    def __init__(self, archiver_fqdn: str) -> None:
        """Initialize the exception.

        Args:
            archiver_fqdn (str): The archiver FQDN that is not part of the cluster.
        """
        super().__init__(f"Archiver {archiver_fqdn} is not part of the cluster.")
        self.archiver_fqdn = archiver_fqdn


def validate_archiver_fqdns(archiver_fqdns: Sequence[str]) -> None:
    """Validate the archiver FQDNs.

    Args:
        archiver_fqdns (Sequence[str]): The archiver FQDNs to validate.

    Raises:
        DifferentArchiverClusterError: If the archiver FQDNs are not part of the same cluster.
    """
    if len(archiver_fqdns) == 1:
        return
    identities_in_cluster: list[str] = []
    for archiver_fqdn in archiver_fqdns:
        archiver = ArchiverMgmt(archiver_fqdn)
        if not identities_in_cluster:
            identities_in_cluster = [appliance["identity"] for appliance in archiver.appliances_in_cluster]
        if archiver.info["identity"] not in identities_in_cluster:
            raise DifferentArchiverClusterError(archiver_fqdn)
