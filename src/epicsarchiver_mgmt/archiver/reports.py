"""Archiver Statistics Service."""

from __future__ import annotations

import logging

from epicsarchiver_mgmt.archiver.base import BaseArchiverAppliance
from epicsarchiver_mgmt.models.pv_details import Details
from epicsarchiver_mgmt.models.stat_responses import (
    DisconnectedPV,
    DroppedPVResponse,
    DroppedReason,
    HighStorageRate,
    LostConnections,
    PausedPVResponse,
    SilentPV,
)

LOG: logging.Logger = logging.getLogger(__name__)

DEFAULT_QUERY_LIMIT = 10_000


class ArchiverReports(BaseArchiverAppliance):
    """Responses from the reports of the archiver appliance."""

    def __init__(self, hostname: str = "localhost", port: int = 17665) -> None:
        """Create Archiver Appliance object.

        Args:
            hostname (str, optional): hostname of archiver. Defaults to "localhost".
            port (int, optional): port number of mgmt interface. Defaults to 17665.
        """
        super().__init__(hostname, port)

    def get_pvs_dropped(
        self,
        reason: DroppedReason,
        limit: int | None = DEFAULT_QUERY_LIMIT,
    ) -> list[DroppedPVResponse]:
        """Gets the pvs ordered by dropped events.

        Returns:
            list[DroppedPVResponse]: List of responses
        """
        params = None
        if limit:
            params = {"limit": str(limit)}
        try:
            r = self._get_json(reason.value, params=params)
        except Exception:
            LOG.exception("Failed to get a response from archiver")
            return []
        return [DroppedPVResponse.from_json(rs, reason) for rs in r]

    def get_disconnected_pvs(self) -> list[DisconnectedPV]:
        """Gets the list of disconnected pvs.

        Returns:
            list[DisconnectedPV]: List of responses
        """
        try:
            r = self._get_json("/getCurrentlyDisconnectedPVs")
        except Exception:
            LOG.exception("Failed to get a response from archiver")
            return []
        return [DisconnectedPV.from_json(rs) for rs in r]

    def get_silent_pvs(self, limit: int | None = DEFAULT_QUERY_LIMIT) -> list[SilentPV]:
        """Gets the list of pvs with no events.

        Returns:
            list[SilentPVsResponse]: List of responses
        """
        params = None
        if limit:
            params = {"limit": str(limit)}
        try:
            r = self._get_json("/getSilentPVsReport", params=params)
        except Exception:
            LOG.exception("Failed to get a response from archiver")
            return []
        return [SilentPV.from_json(rs) for rs in r]

    def get_lost_connections_pvs(
        self,
        limit: int | None = DEFAULT_QUERY_LIMIT,
    ) -> list[LostConnections]:
        """Gets the list of pvs with lost connections.

        Returns:
            list[LostConnectionsResponse]: List of responses
        """
        params = None
        if limit:
            params = {"limit": str(limit)}
        try:
            r = self._get_json("/getLostConnectionsReport", params=params)
        except Exception:
            LOG.exception("Failed to get a response from archiver")
            return []
        return [LostConnections.from_json(rs) for rs in r]

    def get_storage_rates(self, limit: int | None = DEFAULT_QUERY_LIMIT) -> list[HighStorageRate]:
        """Gets the list of pvs with highest storage rates.

        Returns:
            list[StorageRatesResponse]: List of responses
        """
        params = None
        if limit:
            params = {"limit": str(limit)}
        try:
            r = self._get_json("/getStorageRateReport", params=params)
        except Exception:
            LOG.exception("Failed to get a response from archiver")
            return []
        return [HighStorageRate.from_json(rs) for rs in r]

    def get_paused_pvs(self) -> list[PausedPVResponse]:
        """Gets the list of paused pvs.

        Returns:
            list[PausedPVResponse]: List of responses
        """
        try:
            r = self._get_json("/getPausedPVsReport")
        except Exception:
            LOG.exception("Failed to get a response from archiver")
            return []
        return [PausedPVResponse.from_json(rs) for rs in r]

    def get_pv_detail(self, pv: str) -> Details:
        """Get the details of a PV.

        Args:
            pv (str): name of the pv for which the details are to be
                determined.

        Returns:
            Details: details of the matching PV
        """
        data = self._get_json("/getPVDetails", params={"pv": pv})
        return Details.from_json(data)
