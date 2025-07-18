import logging
from unittest.mock import MagicMock, patch

import pytest
from epicsarchiver.mgmt.archiver_mgmt_info import ArchiverMgmtInfo, ArchivingStatus
from requests import HTTPError, Response

from epicsarchiver_mgmt.archiver.mgmt import (
    ArchivePVRequest,
    ArchiverMgmt,
)
from epicsarchiver_mgmt.commands.archive import (
    ARCHIVE_OPERATION_EXPECTED_STATUS,
    ARCHIVE_OPERATION_RESULT_STATUS_OK,
    ArchivePolicyNotFoundError,
    archive,
    validate_policy_names,
)
from epicsarchiver_mgmt.commands.validation import RequestHTTPError


def test_archive_success(caplog: pytest.LogCaptureFixture) -> None:
    """Test successful archive operation."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pv_requests = [ArchivePVRequest(pv="PV1", policy="policy1")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    mock_archiver.archive_pv_requests.return_value = {"PV1": ARCHIVE_OPERATION_RESULT_STATUS_OK}

    with (
        patch("epicsarchiver_mgmt.commands.archive.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.archive.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.archive.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.archive.validate_policy_names") as mock_validate_policy_names,
        patch("epicsarchiver_mgmt.commands.archive.validate_operation_results") as mock_validate_operation_results,
    ):
        archive(archiver_fqdn, pv_requests)

        mock_validate_pvs_status.assert_called_once_with(
            archiver_info=mock_archiver_info, pvs=["PV1"], expected_statuses=[ArchivingStatus.NotBeingArchived]
        )
        mock_validate_policy_names.assert_called_once_with(mock_archiver, pv_requests)
        mock_archiver.archive_pv_requests.assert_called_once_with(pv_requests)
        mock_validate_operation_results.assert_called_once_with(
            ["PV1"],
            {"PV1": ARCHIVE_OPERATION_RESULT_STATUS_OK},
            "archived",
            expected_operation_results=ARCHIVE_OPERATION_EXPECTED_STATUS,
        )
        assert "Archiving PVs" in caplog.text
        assert "Using archiver" in caplog.text


def test_archive_dry_run(caplog: pytest.LogCaptureFixture) -> None:
    """Test archive operation with dry run."""
    caplog.set_level(logging.INFO)
    archiver_fqdn = "archiver.example.com"
    pv_requests = [ArchivePVRequest(pv="PV1", policy="policy1")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"

    with (
        patch("epicsarchiver_mgmt.commands.archive.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.archive.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.archive.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.archive.validate_policy_names") as mock_validate_policy_names,
    ):
        archive(archiver_fqdn, pv_requests, dry_run=True)

        mock_validate_pvs_status.assert_called_once_with(
            archiver_info=mock_archiver_info, pvs=["PV1"], expected_statuses=[ArchivingStatus.NotBeingArchived]
        )
        mock_validate_policy_names.assert_called_once_with(mock_archiver, pv_requests)
        mock_archiver.archive_pv_requests.assert_not_called()
        assert "Archiving PVs" in caplog.text
        assert "Using archiver" in caplog.text


def test_archive_http_error(caplog: pytest.LogCaptureFixture) -> None:
    """Test archive operation with HTTP error."""
    caplog.set_level(logging.DEBUG)
    archiver_fqdn = "archiver.example.com"
    pv_requests = [ArchivePVRequest(pv="PV1", policy="policy1")]
    mock_archiver_info = MagicMock(spec=ArchiverMgmtInfo)
    mock_archiver = MagicMock(spec=ArchiverMgmt)
    mock_archiver.info = "Archiver Info"
    request_response = Response()
    request_response.status_code = 500
    request_response.reason = "HTTP Error"
    mock_archiver.archive_pv_requests.side_effect = HTTPError(response=request_response)

    with (
        patch("epicsarchiver_mgmt.commands.archive.ArchiverMgmtInfo", return_value=mock_archiver_info),
        patch("epicsarchiver_mgmt.commands.archive.ArchiverMgmt", return_value=mock_archiver),
        patch("epicsarchiver_mgmt.commands.archive.validate_pvs_status") as mock_validate_pvs_status,
        patch("epicsarchiver_mgmt.commands.archive.validate_policy_names") as mock_validate_policy_names,
    ):
        with pytest.raises(RequestHTTPError) as exc_info:
            archive(archiver_fqdn, pv_requests)

        mock_validate_pvs_status.assert_called_once_with(
            archiver_info=mock_archiver_info, pvs=["PV1"], expected_statuses=[ArchivingStatus.NotBeingArchived]
        )
        mock_validate_policy_names.assert_called_once_with(mock_archiver, pv_requests)
        mock_archiver.archive_pv_requests.assert_called_once_with(pv_requests)
        assert "Error archiving PVs" in caplog.text
        assert "HTTPError" in caplog.text
        assert exc_info.value.__cause__ is not None


def test_validate_policy_names_success() -> None:
    """Test validate_policy_names with valid policy."""
    archiver = MagicMock(spec=ArchiverMgmt)
    archiver.get_policy_list.return_value = {"policy1": {}}
    pv_requests = [ArchivePVRequest(pv="PV1", policy="policy1")]
    validate_policy_names(archiver, pv_requests)  # Should not raise an exception


def test_validate_policy_names_not_found() -> None:
    """Test validate_policy_names with invalid policy."""
    archiver = MagicMock(spec=ArchiverMgmt)
    archiver.get_policy_list.return_value = {"policy1": {}}
    pv_requests = [ArchivePVRequest(pv="PV1", policy="policy2")]
    with pytest.raises(ArchivePolicyNotFoundError) as exc_info:
        validate_policy_names(archiver, pv_requests)
    assert exc_info.value.pv_request == pv_requests[0]
    assert exc_info.value.policy_names == {"policy1"}


def test_validate_policy_names_no_policy() -> None:
    """Test validate_policy_names when no policy is specified in the request."""
    archiver = MagicMock(spec=ArchiverMgmt)
    archiver.get_policy_list.return_value = {"policy1": {}}
    pv_requests = [ArchivePVRequest(pv="PV1", policy=None)]
    validate_policy_names(archiver, pv_requests)  # Should not raise an exception
