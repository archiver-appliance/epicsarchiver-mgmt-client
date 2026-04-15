"""Base Archiver HTTP client module."""

from __future__ import annotations

import logging
import urllib.parse
from typing import Any

import requests
from requests import Response

from epicsarchiver_mgmt.exceptions import BaseMgmtError

LOG: logging.Logger = logging.getLogger(__name__)


def mgmt_url(hostname: str, port: int) -> str:
    """Generate the mgmt url from a hostname and a port number.

    Args:
        hostname (str): fqdn of service
        port (int): Port number

    Returns:
        str: Completed url, for example "http://localhost:17665/mgmt/bpl/"
    """
    return f"http://{hostname}:{port}/mgmt/bpl/"


class ArchiverError(BaseMgmtError):
    """Base class for all exceptions raised by the archiver HTTP client."""


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
