"""Archiver Mgmt information module."""

from __future__ import annotations

import logging
import urllib.parse
from collections.abc import Collection
from enum import Enum, auto
from typing import Any, cast

import requests
from requests import Response

LOG: logging.Logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

TypeInfo = dict[str, Collection[str]]
InfoResult = dict[str, str]
InfoResultList = list[InfoResult]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ArchiverError(Exception):
    """Base class for all exceptions raised by the archiver."""


class ArchiverConnectionError(ArchiverError):
    """Exception raised when there is a connection error with the archiver."""

    def __init__(self, base_url: str, message: str | None = None):
        """Initialize the ArchiverConnectionError.

        Args:
            base_url (str): The base URL of the archiver.
            message (str | None, optional): A custom error message. Defaults to None.
        """
        self.base_url = base_url
        if message is None:
            message = f"Failed to connect to archiver at {base_url}"
        super().__init__(message)


class ArchiverResponseError(ArchiverError):
    """Exception raised when the archiver returns an unexpected response."""

    def __init__(
        self,
        base_url: str,
        url: str | None = None,
        response: str | None = None,
        message: str | None = None,
    ):
        """Initialize the ArchiverResponseError.

        Args:
            base_url (str): The base URL of the archiver.
            url (str | None, optional): The specific URL that caused the error.
                Defaults to None.
            response (str | None, optional): The response received from the archiver.
                Defaults to None.
            message (str | None, optional): A custom error message. Defaults to None.
        """
        self.base_url = base_url
        if url is None:
            url = base_url
        self.url = url
        self.response = response
        if message is None:
            message = (
                f"Received an unexpected response '{response}' "
                f"from the archiver {self.base_url} for URL: {self.url}"
            )
        super().__init__(message)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ArchivingStatus(str, Enum):
    """Enum of archiving status in the archiver."""

    Paused = "Paused"
    BeingArchived = "Being archived"
    NotBeingArchived = "Not being archived"

    @classmethod
    def from_str(cls, desc: str) -> ArchivingStatus | None:
        """Convert from a string to ArchivingStatus.

        Args:
            desc (str): input string

        Returns:
            ArchivingStatus | None: An enum representation.
        """
        for e in ArchivingStatus:
            if e.value == desc:
                return e
        return None


class ArchDbrType(Enum):
    """List of Dbr Types that the archiver uses."""

    DBR_SCALAR_STRING = auto()
    DBR_SCALAR_SHORT = auto()
    DBR_SCALAR_FLOAT = auto()
    DBR_SCALAR_ENUM = auto()
    DBR_SCALAR_BYTE = auto()
    DBR_SCALAR_INT = auto()
    DBR_SCALAR_DOUBLE = auto()
    DBR_WAVEFORM_STRING = auto()
    DBR_WAVEFORM_SHORT = auto()
    DBR_WAVEFORM_FLOAT = auto()
    DBR_WAVEFORM_ENUM = auto()
    DBR_WAVEFORM_BYTE = auto()
    DBR_WAVEFORM_INT = auto()
    DBR_WAVEFORM_DOUBLE = auto()
    DBR_V4_GENERIC_BYTES = auto()


# ---------------------------------------------------------------------------
# Base HTTP client
# ---------------------------------------------------------------------------


def mgmt_url(hostname: str, port: int) -> str:
    """Generate the mgmt url from a hostname and a port number.

    Args:
        hostname (str): fqdn of service
        port (int): Port number

    Returns:
        str: Completed url, for example "http://localhost:17665/mgmt/bpl/"
    """
    return f"http://{hostname}:{port}/mgmt/bpl/"


class BaseArchiverAppliance:
    """Base EPICS Archiver Appliance client.

    Hold a session to the Archiver Appliance web application.

    Args:
        hostname: EPICS Archiver Appliance hostname [default: localhost]
        port: EPICS Archiver Appliance management port [default: 17665]
    """

    def __init__(self, hostname: str = "localhost", port: int = 17665):
        """Create Archiver Appliance object.

        Args:
            hostname (str, optional): hostname of archiver. Defaults to "localhost".
            port (int, optional): port number of mgmt interface. Defaults to 17665.
        """
        self.hostname = hostname
        self.port = port
        self.mgmt_url = mgmt_url(hostname, port)
        self._info: dict[str, str] = {}
        self._data_retrieval_url: str | None = None
        self.session = requests.Session()

    def __repr__(self) -> str:
        """String representation of Archiver Appliance.

        Returns:
            str: details including hostname of Archiver appliance.
        """
        return f"ArchiverAppliance({self.hostname}, {self.port})"

    def _request(self, method: str, *args: Any, **kwargs: Any) -> Response:
        """Send a request using the session.

        Args:
            method: HTTP method
            *args: Optional arguments
            **kwargs: Optional keyword arguments

        Returns:
            :class:`requests.Response <Response>` object

        Raises:
            ArchiverConnectionError: If there is a connection error.
            ArchiverResponseError: If the response is not successful.
        """
        try:
            r = self.session.request(method, *args, **kwargs)
            r.raise_for_status()
        except requests.ConnectionError as e:
            raise ArchiverConnectionError(
                base_url=self.mgmt_url,
            ) from e
        except requests.HTTPError as e:
            raise ArchiverResponseError(
                base_url=self.mgmt_url,
                url=args[0] if args else None,
                response=e.response.text if e.response else None,
            ) from e
        else:
            return r

    def _get(self, endpoint: str, **kwargs: Any) -> Response:
        r"""Send a GET request to the given endpoint.

        Args:
            endpoint: API endpoint (relative or absolute)
            **kwargs: Optional arguments to be sent

        Returns:
            :class:`requests.Response <Response>` object
        """
        url = urllib.parse.urljoin(self.mgmt_url, endpoint.lstrip("/"))
        LOG.debug("GET url: %s", url)
        return self._request("GET", url, **kwargs)

    def _post(self, endpoint: str, **kwargs: Any) -> Response:
        r"""Send a POST request to the given endpoint.

        Args:
            endpoint: API endpoint (relative or absolute)
            **kwargs: Optional arguments to be sent

        Returns:
            :class:`requests.Response <Response>` object
        """
        url = urllib.parse.urljoin(self.mgmt_url, endpoint.lstrip("/"))
        return self._request("POST", url, **kwargs)

    @property
    def info(self) -> dict[str, str]:
        """EPICS Archiver Appliance information."""
        if not self._info:
            r = self._get("/getApplianceInfo")
            self._info = r.json()
        return self._info

    @property
    def identity(self) -> str | None:
        """EPICS Archiver Appliance identity."""
        return self.info.get("identity")

    @property
    def version(self) -> str | None:
        """EPICS Archiver Appliance version."""
        return self.info.get("version")

    def _get_or_post(self, endpoint: str, pv: str) -> Any:
        """Send a GET or POST if pv is a comma separated list.

        Args:
            endpoint (str): API endpoint
            pv (str): name of the pv. Can be a GLOB wildcards or a list of
                comma separated names.

        Returns:
            Any: list of submitted PVs
        """
        r = (
            self._post(endpoint, data=pv)
            if "," in pv
            else self._get(endpoint, params={"pv": pv})
        )
        return r.json()


# ---------------------------------------------------------------------------
# Mgmt info client
# ---------------------------------------------------------------------------


class ArchiverMgmtInfo(BaseArchiverAppliance):
    """Mgmt Info EPICS Archiver Appliance client.

    Hold a session to the Archiver Appliance web application and use the mgmt interface.

    Args:
        hostname: EPICS Archiver Appliance hostname [default: localhost]
        port: EPICS Archiver Appliance management port [default: 17665]

    Examples:
    .. code-block:: python

        from epicsarchiver_mgmt.archiver.info import ArchiverMgmtInfo

        archappl = ArchiverMgmtInfo("archiver-01.tn.esss.lu.se")
        print(archappl.version)
        archappl.get_pv_status(pv="BPM*")
    """

    # EPICS Archiver Appliance documentation of mgmt endpoints:
    # https://epicsarchiver.readthedocs.io/en/latest/developer/mgmt_scriptables.html

    def get_all_expanded_pvs(self) -> list[str]:
        """Return all expanded PV names in the cluster.

        This is targeted at automation and should return the PVs
        being archived, the fields, .VAL's, aliases and PV's in
        the archive workflow.
        Note this call can return 10's of millions of names.

        Returns:
            list of expanded PV names
        """
        r = self._get("/getAllExpandedPVNames")
        return cast("list[str]", r.json())

    def get_all_pvs(
        self,
        pv_query: str | None = None,
        regex: str | None = None,
        limit: int = 500,
    ) -> list[str]:
        """Return all the PVs in the cluster.

        Args:
            pv_query (str): An optional argument that can contain a GLOB wildcard.
                Will return PVs that match this GLOB. For example:
                pv=KLYS*
            regex (str): An optional argument that can contain a Java regex
                wildcard. Will return PVs that match this regex.
            limit (int): number of matched PV's that are returned. To get all
                the PV names, (potentially in the millions), set limit
                to -1. Default to 500.

        Returns:
            list[str]: list of PV names
        """
        params: dict[str, str] = {"limit": str(limit)}
        if pv_query is not None:
            params["pv"] = pv_query
        if regex is not None:
            params["regex"] = regex
        r = self._get("/getAllPVs", params=params)
        return cast("list[str]", r.json())

    def get_pv_status(self, pv: str | list[str]) -> InfoResultList:
        """Return the status of a PV.

        Args:
            pv: name(s) of the pv for which the status is to be
                determined. Can be a GLOB wildcards or multiple PVs as a
                comma separated list.

        Returns:
            list of dict with the status of the matching PVs
        """
        r = self._get("/getPVStatus", params={"pv": pv})
        return cast("InfoResultList", r.json())

    def get_archiving_status(self, pv: str) -> ArchivingStatus | None:
        """Return the status of a PV.

        Args:
            pv: name of the pv.

        Returns:
            string representing the status
        """
        return ArchivingStatus.from_str(self.get_pv_status(pv)[0]["status"])

    def get_pv_details(self, pv: str | list[str]) -> InfoResultList:
        """Return the details of a PV.

        Args:
            pv: name(s) of the pv for which the details are to be
                determined. Can be a GLOB wildcards or multiple PVs as a
                comma separated list.

        Returns:
            list of dict with the details of the matching PVs
        """
        r = self._get("/getPVDetails", params={"pv": pv})
        return cast("InfoResultList", r.json())

    def get_unarchived_pvs(self, pvs: str | list[str]) -> list[str]:
        """Return the list of unarchived PVs out of PVs specified in pvs.

        Args:
            pvs: a list of PVs either in CSV format or as a python
                string list

        Returns:
            list of unarchived PV names
        """
        if isinstance(pvs, list):
            pvs = ",".join(pvs)
        r = self._post("/unarchivedPVs", data={"pv": pvs})
        return cast("list[str]", r.json())

    def get_archived_pvs(self, pvs: str | list[str]) -> list[str]:
        """Return the list of archived PVs out of PVs specified in pvs.

        Args:
            pvs: a list of PVs either in CSV format or as a python
                string list

        Returns:
            list of archived PV names
        """
        if isinstance(pvs, list):
            pvs = ",".join(pvs)
        r = self._post("/archivedPVs", data={"pv": pvs})
        return cast("list[str]", r.json())

    def get_pv_type_info(self, pv: str) -> TypeInfo:
        """Return the type info of a PV.

        Args:
            pv: name of the pv.

        Returns:
            dict with the type info of the matching PVs.
        """
        r = self._get("/getPVTypeInfo", params={"pv": pv})
        return cast("TypeInfo", r.json())
