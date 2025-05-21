"""Change the sampling method or sampling period of PVs in the archiver."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
    SamplingMethod,
)
from epicsarchiver_mgmt.commands.validation import (
    RequestHTTPError,
    validate_operation_results,
    validate_pvs_status,
)
from epicsarchiver_mgmt.mgmt_exception import BaseMgmtError

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG: logging.Logger = logging.getLogger(__name__)


class InvalidSamplingMethodError(BaseMgmtError):
    """Exception for when the sampling method is invalid."""

    def __init__(self, parameter: str) -> None:
        """Error for when the rename type is invalid.

        Args:
            parameter (str): The invalid sampling method.
        """
        super().__init__(f"Invalid sampling method {parameter}.")
        self.parameter = parameter


def samplingmethod_from_str(value: str) -> SamplingMethod:
    """Convert a string to a SamplingMethod.

    Args:
        value (str): The value to convert.

    Returns:
        SamplingMethod: The SamplingMethod.

    Raises:
        InvalidSamplingMethodError: If the value is invalid.
    """
    for t in SamplingMethod:
        if t.name.lower() == value.lower():
            return t
    raise InvalidSamplingMethodError(value)


def change_parameter(
    archiver_fqdn: str,
    pvs: Sequence[str],
    sampling_method: SamplingMethod | None = None,
    sampling_period: float | None = None,
) -> None:
    """Change the sampling method or sampling period of PVs in the archiver.

    Args:
        archiver_fqdn (str): The url of the archiver.
        pvs (list[str]): The PVs to change type.
        sampling_method (str): The sampling method to use.
        sampling_period (float): The sampling period to use.

    Raises:
        RequestHTTPError: If the request fails.
    """
    # Validate input
    archiver_info = ArchiverMgmtInfo(archiver_fqdn)
    validate_pvs_status(
        archiver_info=archiver_info,
        pvs=pvs,
        expected_statuses=[
            ArchivingStatus.BeingArchived,
        ],
    )

    archiver = ArchiverMgmt(archiver_fqdn)

    # Action
    LOG.info("Using archiver %s", archiver.info)
    LOG.info("Changing sampling method and period of the PVs %s to %s, %s", pvs, sampling_method, sampling_period)
    try:
        results = [
            archiver.update_pv(
                pv,
                samplingmethod=sampling_method,
                samplingperiod=sampling_period,
            )
            for pv in pvs
        ]
    except HTTPError as e:
        LOG.error("Error changing sampling method and period of PVs: %s", str(e))  # noqa: TRY400
        LOG.debug("Error changing sampling method and period of PVs.", exc_info=True)
        raise RequestHTTPError(e) from e

    # Validate output
    validate_operation_results(pvs, results, "changed parameters")
