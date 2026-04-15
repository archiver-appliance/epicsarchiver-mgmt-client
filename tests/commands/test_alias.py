import logging
from unittest.mock import MagicMock, patch

import pytest
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.info import ArchiverMgmtInfo
from epicsarchiver_mgmt.archiver.mgmt import (
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands.alias import (
    add_aliases,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


def test_alias_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful alias operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    aliases = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    mock_archiver.add_alias.return_value = {"status": "ok", "desc": "aliased"}

    with (
        patch("epicsarchiver_mgmt.commands.alias.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.alias.ArchiverMgmt", side_effect=mock_archiver),
        patch("epicsarchiver_mgmt.commands.alias.validate_not_same") as mock_validate_not_same,
        patch("epicsarchiver_mgmt.commands.alias.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.alias.validate_operation_results") as mock_validate_operation_results,
    ):
        add_aliases(archiver_fqdn, aliases)

        mock_validate_not_same.assert_called_once_with(aliases)
        mock_validate_pvs_status.assert_called()
        assert mock_validate_pvs_status.call_count == 2
        mock_validate_operation_results.assert_called_once()
        assert "Adding aliases" in caplog.text
        assert "Using archiver" in caplog.text


def test_alias_http_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test alias operation with HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    aliases = [("old_pv1", "new_pv1"), ("old_pv2", "new_pv2")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "HTTP Error"
    mock_archiver.add_alias.side_effect = HTTPError(response=request_response)

    with (
        patch("epicsarchiver_mgmt.commands.alias.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.alias.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.alias.validate_not_same") as mock_validate_not_same,
        patch("epicsarchiver_mgmt.commands.alias.validate_pvs_status") as mock_validate_pvs_status,
    ):
        with pytest.raises(RequestHTTPError):
            add_aliases(archiver_fqdn, aliases)

        mock_validate_not_same.assert_called_once_with(aliases)
        mock_validate_pvs_status.assert_called()
        mock_archiver.add_alias.assert_called_once_with("old_pv1", "new_pv1")
        assert mock_validate_pvs_status.call_count == 2
        assert "Error adding alias PVs" in caplog.text
        assert "HTTPError" in caplog.text
